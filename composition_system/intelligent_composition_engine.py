"""
composition_system/intelligent_composition_engine.py
Moteur de composition intelligent utilisant les annotations LLM
"""
import sys
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from composition_system.intelligent_service_registry import IntelligentServiceRegistry, ServiceScore
from composition_system.intelligent_parameter_mapper import IntelligentParameterMapper


@dataclass
class IntelligentWorkflowStep:
    """Étape dans le workflow intelligent"""
    step_number: int
    category: str
    selected_service: str
    selected_operation: str
    input_parameters: Dict[str, Any]
    expected_outputs: List[str]
    
    # Scores de sélection
    service_score: ServiceScore
    
    # Mapping
    mapping_coverage: float
    mapping_details: List[Dict]
    missing_parameters: List[str]
    parameter_suggestions: Dict[str, Any]
    
    # Alternatives
    alternatives_scores: List[ServiceScore]


@dataclass
class IntelligentCompositionResult:
    """Résultat de composition intelligent"""
    workflow_id: str
    goal: str
    steps: List[IntelligentWorkflowStep]
    success: bool
    total_steps: int
    created_at: datetime
    
    # Métriques globales
    avg_service_score: float
    avg_mapping_coverage: float
    total_missing_params: int
    
    # Contexte utilisé
    user_context: Dict[str, Any]
    constraints: Dict[str, Any]
    
    errors: List[str]


class IntelligentCompositionEngine:
    """
    Moteur de composition intelligent
    - Utilise les annotations LLM pour sélection
    - Adaptation contextuelle
    - Mapping sémantique avancé
    """
    
    # Workflows (similaires mais découverte dynamique)
    WORKFLOW_TEMPLATES = {
        "book_complete_travel": [
            {"step": 1, "category": "search", "function": "flights"},
            {"step": 2, "category": "search", "function": "hotels"},
            {"step": 3, "category": "payment", "function": "process"}
        ]
    }
    
    def __init__(self, registry: IntelligentServiceRegistry):
        """
        Initialise le moteur intelligent
        
        Args:
            registry: Registre intelligent avec annotations
        """
        self.registry = registry
        self.mapper = IntelligentParameterMapper(registry)
    
    def compose(self, 
                goal: str,
                user_input: Dict[str, Any],
                user_context: Optional[Dict[str, Any]] = None,
                constraints: Optional[Dict[str, Any]] = None) -> IntelligentCompositionResult:
        """
        Compose un workflow intelligent
        
        Args:
            goal: Objectif à atteindre
            user_input: Données initiales
            user_context: Contexte utilisateur (préférences, contraintes)
            constraints: Contraintes techniques
            
        Returns:
            Résultat de composition intelligent
        """
        print("\n" + "="*80)
        print(f"COMPOSITION INTELLIGENTE - Objectif: {goal}")
        print("="*80)
        
        user_context = user_context or {}
        constraints = constraints or {}
        
        # Vérifier le workflow
        if goal not in self.WORKFLOW_TEMPLATES:
            return IntelligentCompositionResult(
                workflow_id=f"iwf_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                goal=goal,
                steps=[],
                success=False,
                total_steps=0,
                created_at=datetime.now(),
                avg_service_score=0.0,
                avg_mapping_coverage=0.0,
                total_missing_params=0,
                user_context=user_context,
                constraints=constraints,
                errors=[f"Workflow '{goal}' inconnu"]
            )
        
        template = self.WORKFLOW_TEMPLATES[goal]
        steps = []
        errors = []
        context = user_input.copy()
        
        print(f"\nWorkflow: {len(template)} étapes")
        print(f"Contexte utilisateur:")
        for key, value in user_context.items():
            print(f"   • {key}: {value}")
        print()
        
        # Exécuter chaque étape
        for step_template in template:
            print("\n" + "─"*80)
            print(f"ÉTAPE {step_template['step']}: {step_template['category'].upper()}")
            print("─"*80)
            
            try:
                step_result = self._execute_intelligent_step(
                    step_template, context, user_context, constraints, steps
                )
                
                if step_result:
                    steps.append(step_result)
                    
                    # Enrichir le contexte
                    for output in step_result.expected_outputs:
                        context[output] = f"<{step_result.selected_service}.{output}>"
                    
                    print(f"\nÉtape {step_template['step']} terminée")
                else:
                    error_msg = f"Échec étape {step_template['step']}"
                    errors.append(error_msg)
                    print(f"\n{error_msg}")
                    
            except Exception as e:
                error_msg = f"Erreur étape {step_template['step']}: {str(e)}"
                errors.append(error_msg)
                print(f"\n{error_msg}")
        
        # Calculer les métriques
        avg_score = sum(s.service_score.total_score for s in steps) / len(steps) if steps else 0
        avg_coverage = sum(s.mapping_coverage for s in steps) / len(steps) if steps else 0
        total_missing = sum(len(s.missing_parameters) for s in steps)
        
        result = IntelligentCompositionResult(
            workflow_id=f"iwf_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            goal=goal,
            steps=steps,
            success=len(errors) == 0,
            total_steps=len(template),
            created_at=datetime.now(),
            avg_service_score=avg_score,
            avg_mapping_coverage=avg_coverage,
            total_missing_params=total_missing,
            user_context=user_context,
            constraints=constraints,
            errors=errors
        )
        
        return result
    
    def _execute_intelligent_step(self,
                                 step_template: Dict,
                                 context: Dict[str, Any],
                                 user_context: Dict[str, Any],
                                 constraints: Dict[str, Any],
                                 previous_steps: List) -> Optional[IntelligentWorkflowStep]:
        """Exécute une étape intelligente"""
        
        category = step_template["category"]
        
        # 1. Sélection intelligente du service
        print(f"\nSélection intelligente pour: {category}")
        
        service_score = self.registry.select_best_service(
            category=category,
            user_context=user_context,
            constraints=constraints
        )
        
        if not service_score:
            print(f"   Aucun service disponible")
            return None
        
        service_name = service_score.service_name
        annotation = self.registry.get_service_annotation(service_name)
        
        print(f"\nRaisons de sélection:")
        for reason in service_score.reasons:
            print(f"   • {reason}")
        
        # 2. Obtenir les alternatives
        all_candidates = self.registry.discover_by_category(category)
        alternatives = [c for c in all_candidates if c != service_name]
        
        alternatives_scores = []
        if alternatives:
            print(f"\nComparaison avec alternatives:")
            alt_scores = self.registry.compare_services(alternatives, user_context)
            for alt_score in alt_scores:
                print(f"   • {alt_score.service_name}: score {alt_score.total_score:.3f}")
                alternatives_scores.append(alt_score)
        
        # 3. Sélectionner l'opération
        operations = annotation['functional']['output_parameters']
        operation_name = self._select_operation(annotation, step_template['function'])
        
        if not operation_name:
            operation_name = "DefaultOperation"
        
        print(f"\nOpération: {operation_name}")
        
        # 4. Mapping intelligent des paramètres
        print(f"\nMapping intelligent des paramètres...")
        
        required_params = annotation['functional']['input_parameters']
        print(f"   Paramètres requis: {required_params[:5]}...")  # Premier 5
        
        # Déterminer le service source
        source_service = previous_steps[-1].selected_service if previous_steps else None
        
        # Mapper avec contexte
        mapped_params = self.mapper.map_parameters(
            source_data=context,
            target_params=required_params,
            source_service=source_service,
            target_service=service_name
        )
        
        # Obtenir le plan détaillé
        mapping_plan = self.mapper.get_mapping_plan(
            source_data=context,
            target_params=required_params,
            source_service=source_service,
            target_service=service_name
        )
        
        coverage = mapping_plan['coverage']
        missing = mapping_plan['missing_parameters']
        
        print(f"   Mappés: {len(mapped_params)}/{len(required_params)} ({coverage*100:.0f}%)")
        
        if missing:
            print(f"   Manquants: {len(missing)} paramètre(s)")
            # Suggestions pour paramètres manquants
            suggestions = self.mapper.suggest_missing_parameters(missing, user_context)
        else:
            suggestions = {}
        
        # 5. Sorties attendues
        expected_outputs = annotation['functional']['output_parameters']
        
        # 6. Créer l'étape
        step = IntelligentWorkflowStep(
            step_number=step_template['step'],
            category=category,
            selected_service=service_name,
            selected_operation=operation_name,
            input_parameters=mapped_params,
            expected_outputs=expected_outputs,
            service_score=service_score,
            mapping_coverage=coverage,
            mapping_details=mapping_plan['mappings'],
            missing_parameters=missing,
            parameter_suggestions=suggestions,
            alternatives_scores=alternatives_scores
        )
        
        return step
    
    def _select_operation(self, annotation: Dict, function_hint: str) -> str:
        """Sélectionne une opération basée sur les capabilities"""
        capabilities = annotation['functional'].get('capabilities', [])
        
        # Chercher une capacité qui correspond
        for cap in capabilities:
            if function_hint.lower() in cap.lower():
                return cap
        
        # Retourner la première
        return capabilities[0] if capabilities else "DefaultOperation"
    
    def print_result(self, result: IntelligentCompositionResult):
        """Affiche le résultat de manière formatée"""
        
        print("\n\n" + "="*80)
        print("RÉSULTAT DE LA COMPOSITION INTELLIGENTE")
        print("="*80)
        
        print(f"\nID: {result.workflow_id}")
        print(f"Objectif: {result.goal}")
        print(f"Date: {result.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Statut: {'SUCCÈS' if result.success else '❌ ÉCHEC'}")
        
        print(f"\nMÉTRIQUES GLOBALES:")
        print(f"   • Score moyen des services: {result.avg_service_score:.3f}")
        print(f"   • Couverture moyenne: {result.avg_mapping_coverage*100:.1f}%")
        print(f"   • Paramètres manquants totaux: {result.total_missing_params}")
        print(f"   • Étapes complétées: {len(result.steps)}/{result.total_steps}")
        
        if result.errors:
            print(f"\nErreurs:")
            for error in result.errors:
                print(f"   • {error}")
        
        print(f"\n{'='*80}")
        print("WORKFLOW DÉTAILLÉ")
        print("="*80)
        
        for step in result.steps:
            print(f"\nÉTAPE {step.step_number}: {step.category.upper()}")
            print(f"{'─'*80}")
            print(f"   Service: {step.selected_service}")
            print(f"   Opération: {step.selected_operation}")
            
            print(f"\n   SCORES DE SÉLECTION:")
            print(f"      • Total: {step.service_score.total_score:.3f}")
            print(f"      • Fonctionnel: {step.service_score.functional_score:.3f}")
            print(f"      • Qualité: {step.service_score.quality_score:.3f}")
            print(f"      • Coût: {step.service_score.cost_score:.3f}")
            print(f"      • Contexte: {step.service_score.context_score:.3f}")
            
            print(f"\n   RAISONS:")
            for reason in step.service_score.reasons:
                print(f"      • {reason}")
            
            if step.alternatives_scores:
                print(f"\n   ALTERNATIVES COMPARÉES:")
                for alt in step.alternatives_scores[:3]:  # Top 3
                    print(f"      • {alt.service_name}: score {alt.total_score:.3f}")
            
            print(f"\n   📥 MAPPING (coverage: {step.mapping_coverage*100:.0f}%):")
            for detail in step.mapping_details[:5]:  # Premier 5
                print(f"      • {detail['target_param']} ← {detail['source_param']} ({detail['method']})")
            
            if step.missing_parameters:
                print(f"\n   ⚠️  PARAMÈTRES MANQUANTS ({len(step.missing_parameters)}):")
                for param in step.missing_parameters[:5]:
                    print(f"      • {param}")
                    if param in step.parameter_suggestions:
                        sug = step.parameter_suggestions[param]
                        print(f"        → Type: {sug['type']}, {sug.get('description', '')}")
        
        print(f"\n{'='*80}\n")
    
    def save_result(self, result: IntelligentCompositionResult, 
                   output_dir: str = "composition_system/results"):
        """Sauvegarde le résultat"""
        os.makedirs(output_dir, exist_ok=True)
        
        filename = f"{result.workflow_id}_intelligent.json"
        filepath = os.path.join(output_dir, filename)
        
        # Convertir en dict
        result_dict = {
            "workflow_id": result.workflow_id,
            "goal": result.goal,
            "success": result.success,
            "created_at": result.created_at.isoformat(),
            "avg_service_score": result.avg_service_score,
            "avg_mapping_coverage": result.avg_mapping_coverage,
            "total_missing_params": result.total_missing_params,
            "user_context": result.user_context,
            "constraints": result.constraints,
            "steps": []
        }
        
        for step in result.steps:
            result_dict["steps"].append({
                "step_number": step.step_number,
                "category": step.category,
                "selected_service": step.selected_service,
                "service_score": {
                    "total": step.service_score.total_score,
                    "functional": step.service_score.functional_score,
                    "quality": step.service_score.quality_score,
                    "cost": step.service_score.cost_score,
                    "context": step.service_score.context_score
                },
                "reasons": step.service_score.reasons,
                "mapping_coverage": step.mapping_coverage,
                "missing_parameters": step.missing_parameters
            })
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result_dict, f, indent=2, ensure_ascii=False)
        
        print(f"Résultat sauvegardé: {filepath}")


# Test
if __name__ == "__main__":
    print("TEST DE LA COMPOSITION INTELLIGENTE\n")
    
    # Charger le registre
    registry = IntelligentServiceRegistry()
    
    if not registry.services:
        print("❌ Aucune annotation chargée")
        exit(1)
    
    # Créer le moteur
    engine = IntelligentCompositionEngine(registry)
    
    # Contexte enrichi
    user_context = {
        "location": "EU",
        "budget_conscious": True,
        "needs_multi_currency": True,
        "mission_critical": False,
        "needs_24_7": True
    }
    
    # Données utilisateur
    user_input = {
        "origin": "Paris",
        "destination": "Tokyo",
        "departureDate": "2025-08-10",
        "returnDate": "2025-08-17",
        "passengers": 1,
        "currency": "EUR",
        "maxPrice": 3500.00
    }
    
    constraints = {
        "max_cost": 0.05,
        "min_quality": 0.90
    }
    
    # Composer
    result = engine.compose(
        goal="book_complete_travel",
        user_input=user_input,
        user_context=user_context,
        constraints=constraints
    )
    
    # Afficher
    engine.print_result(result)
    engine.save_result(result)