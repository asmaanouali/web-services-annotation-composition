"""
composition_system/classic_composition_engine.py
Moteur de composition classique SANS annotations LLM
Utilise uniquement WSDL + règles hardcodées
"""
import sys
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from composition_system.classic_wsdl_parser import ClassicServiceRegistry, ServiceInfo
from composition_system.classic_service_selector import ClassicServiceSelector, SimpleParameterMapper, SelectionResult


@dataclass
class WorkflowStep:
    """Une étape dans le workflow de composition"""
    step_number: int
    category: str
    selected_service: str
    selected_operation: str
    input_parameters: Dict[str, Any]
    expected_outputs: List[str]
    selection_reason: str
    alternatives_rejected: List[str]
    mapping_coverage: float  # % de paramètres mappés avec succès
    missing_parameters: List[str]


@dataclass
class CompositionResult:
    """Résultat complet de la composition"""
    workflow_id: str
    goal: str
    steps: List[WorkflowStep]
    success: bool
    total_steps: int
    created_at: datetime
    errors: List[str]


class ClassicCompositionEngine:
    """
    Moteur de composition traditionnel
    - Pas d'annotations LLM
    - Règles hardcodées
    - Sélection déterministe
    - Mapping basique de paramètres
    """
    
    # Workflows prédéfinis (hardcodés)
    WORKFLOW_TEMPLATES = {
        "book_complete_travel": [
            {
                "step": 1,
                "category": "flight",
                "function": "search",
                "operation_keyword": "search"
            },
            {
                "step": 2,
                "category": "hotel",
                "function": "search",
                "operation_keyword": "search"
            },
            {
                "step": 3,
                "category": "payment",
                "function": "process",
                "operation_keyword": "process"
            }
        ],
        "search_travel_options": [
            {
                "step": 1,
                "category": "flight",
                "function": "search",
                "operation_keyword": "search"
            },
            {
                "step": 2,
                "category": "hotel",
                "function": "search",
                "operation_keyword": "search"
            }
        ]
    }
    
    def __init__(self, registry: ClassicServiceRegistry):
        """
        Initialise le moteur de composition
        
        Args:
            registry: Registre des services disponibles
        """
        self.registry = registry
        self.selector = ClassicServiceSelector(registry)
        self.mapper = SimpleParameterMapper()
    
    def compose(self, goal: str, user_input: Dict[str, Any]) -> CompositionResult:
        """
        Compose un workflow complet
        
        Args:
            goal: Objectif à atteindre (ex: "book_complete_travel")
            user_input: Données initiales fournies par l'utilisateur
            
        Returns:
            CompositionResult avec tous les détails
        """
        print("\n" + "="*80)
        print(f"COMPOSITION CLASSIQUE - Objectif: {goal}")
        print("="*80)
        
        # Vérifier que le workflow existe
        if goal not in self.WORKFLOW_TEMPLATES:
            print(f"\nWorkflow '{goal}' non reconnu")
            print(f"   Workflows disponibles: {list(self.WORKFLOW_TEMPLATES.keys())}")
            return CompositionResult(
                workflow_id=f"wf_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                goal=goal,
                steps=[],
                success=False,
                total_steps=0,
                created_at=datetime.now(),
                errors=[f"Workflow '{goal}' inconnu"]
            )
        
        template = self.WORKFLOW_TEMPLATES[goal]
        steps = []
        errors = []
        context = user_input.copy()  # Contexte qui s'enrichit à chaque étape
        
        print(f"\nWorkflow: {len(template)} étapes à exécuter")
        print(f"Entrées utilisateur: {list(user_input.keys())}\n")
        
        # Exécuter chaque étape du workflow
        for step_template in template:
            print("\n" + "─"*80)
            print(f"ÉTAPE {step_template['step']}: {step_template['category'].upper()}")
            print("─"*80)
            
            try:
                step_result = self._execute_step(step_template, context)
                
                if step_result:
                    steps.append(step_result)
                    
                    # Enrichir le contexte avec les sorties de cette étape
                    for output in step_result.expected_outputs:
                        context[output] = f"<output_from_{step_result.selected_service}.{output}>"
                    
                    print(f"\nÉtape {step_template['step']} terminée avec succès")
                else:
                    error_msg = f"Échec à l'étape {step_template['step']}"
                    errors.append(error_msg)
                    print(f"\n{error_msg}")
                    
            except Exception as e:
                error_msg = f"Erreur à l'étape {step_template['step']}: {str(e)}"
                errors.append(error_msg)
                print(f"\n{error_msg}")
        
        # Créer le résultat final
        result = CompositionResult(
            workflow_id=f"wf_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            goal=goal,
            steps=steps,
            success=len(errors) == 0,
            total_steps=len(template),
            created_at=datetime.now(),
            errors=errors
        )
        
        return result
    
    def _execute_step(self, step_template: Dict, context: Dict[str, Any]) -> Optional[WorkflowStep]:
        """Exécute une étape du workflow"""
        
        category = step_template["category"]
        
        # 1. Sélectionner le service
        print(f"\nSélection du service pour catégorie: {category}")
        selection = self.selector.select_service(category)
        
        if not selection:
            print(f"   Aucun service disponible pour '{category}'")
            return None
        
        service = selection.service
        print(f"   Service sélectionné: {service.name}")
        print(f"   Raison: {selection.reason}")
        
        # 2. Sélectionner l'opération
        operation_keyword = step_template.get("operation_keyword", "")
        operation_name = self.selector.select_operation(service, operation_keyword)
        
        if not operation_name:
            print(f"   Aucune opération trouvée")
            return None
        
        print(f"   Opération: {operation_name}")
        
        # 3. Récupérer les détails de l'opération
        op_details = self.selector.get_operation_details(service, operation_name)
        
        if not op_details:
            print(f"   Impossible de récupérer les détails de l'opération")
            return None
        
        required_params = op_details["input_params"]
        expected_outputs = op_details["output_params"]
        
        print(f"   Paramètres requis: {required_params}")
        
        # 4. Mapper les paramètres
        print(f"\n🔗 Mapping des paramètres...")
        mapped_params = self.mapper.map_parameters(context, required_params)
        missing_params = self.mapper.find_missing_params(context, required_params)
        
        # Calculer la couverture
        coverage = len(mapped_params) / len(required_params) if required_params else 1.0
        
        print(f"   Mappés: {len(mapped_params)}/{len(required_params)} ({coverage*100:.0f}%)")
        
        for param, value in mapped_params.items():
            print(f"      • {param} = {value}")
        
        if missing_params:
            print(f"   Manquants: {missing_params}")
            print(f"      → Ces paramètres doivent être fournis par l'utilisateur")
        
        # 5. Créer l'étape du workflow
        step = WorkflowStep(
            step_number=step_template["step"],
            category=category,
            selected_service=service.name,
            selected_operation=operation_name,
            input_parameters=mapped_params,
            expected_outputs=expected_outputs,
            selection_reason=selection.reason,
            alternatives_rejected=selection.alternatives,
            mapping_coverage=coverage,
            missing_parameters=missing_params
        )
        
        return step
    
    def print_result(self, result: CompositionResult):
        """Affiche le résultat de manière formatée"""
        
        print("\n\n" + "="*80)
        print("RÉSULTAT DE LA COMPOSITION CLASSIQUE")
        print("="*80)
        
        print(f"\nID: {result.workflow_id}")
        print(f"Objectif: {result.goal}")
        print(f"Date: {result.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Statut: {'SUCCÈS' if result.success else '❌ ÉCHEC'}")
        print(f"Étapes complétées: {len(result.steps)}/{result.total_steps}")
        
        if result.errors:
            print(f"\nErreurs rencontrées:")
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
            print(f"   Raison: {step.selection_reason}")
            
            if step.alternatives_rejected:
                print(f"   Alternatives rejetées: {', '.join(step.alternatives_rejected)}")
            
            print(f"\n   ENTRÉES (coverage: {step.mapping_coverage*100:.0f}%):")
            for param, value in step.input_parameters.items():
                print(f"      • {param} = {value}")
            
            if step.missing_parameters:
                print(f"\n   PARAMÈTRES MANQUANTS:")
                for param in step.missing_parameters:
                    print(f"      • {param} (requis de l'utilisateur)")
            
            print(f"\n   SORTIES ATTENDUES:")
            for output in step.expected_outputs:
                print(f"      • {output}")
        
        print(f"\n{'='*80}\n")
    
    def save_result(self, result: CompositionResult, output_dir: str = "composition_system/results"):
        """Sauvegarde le résultat en JSON"""
        
        os.makedirs(output_dir, exist_ok=True)
        
        filename = f"{result.workflow_id}_classic.json"
        filepath = os.path.join(output_dir, filename)
        
        # Convertir en dict
        result_dict = {
            "workflow_id": result.workflow_id,
            "goal": result.goal,
            "success": result.success,
            "total_steps": result.total_steps,
            "created_at": result.created_at.isoformat(),
            "errors": result.errors,
            "steps": []
        }
        
        for step in result.steps:
            result_dict["steps"].append({
                "step_number": step.step_number,
                "category": step.category,
                "selected_service": step.selected_service,
                "selected_operation": step.selected_operation,
                "input_parameters": step.input_parameters,
                "expected_outputs": step.expected_outputs,
                "selection_reason": step.selection_reason,
                "alternatives_rejected": step.alternatives_rejected,
                "mapping_coverage": step.mapping_coverage,
                "missing_parameters": step.missing_parameters
            })
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result_dict, f, indent=2, ensure_ascii=False)
        
        print(f"Résultat sauvegardé: {filepath}")


# Test complet
if __name__ == "__main__":
    print("TEST COMPLET DE LA COMPOSITION CLASSIQUE\n")
    
    # Charger les services
    registry = ClassicServiceRegistry()
    
    if not registry.services:
        print("Aucun service chargé")
        exit(1)
    
    # Créer le moteur
    engine = ClassicCompositionEngine(registry)
    
    # Données utilisateur
    user_input = {
        "origin": "Paris",
        "destination": "New York",
        "departureDate": "2025-07-15",
        "returnDate": "2025-07-22",
        "passengers": 2,
        "currency": "EUR",
        "maxPrice": 2000.00
    }
    
    # Exécuter la composition
    result = engine.compose(
        goal="book_complete_travel",
        user_input=user_input
    )
    
    # Afficher le résultat
    engine.print_result(result)
    
    # Sauvegarder
    engine.save_result(result)
    
    # Statistiques finales
    if result.success:
        print("Composition réussie!")
        print(f"   • {len(result.steps)} étapes complétées")
        
        # Calculer la couverture moyenne des mappings
        avg_coverage = sum(s.mapping_coverage for s in result.steps) / len(result.steps)
        print(f"   • Couverture moyenne des paramètres: {avg_coverage*100:.1f}%")
        
        # Compter les paramètres manquants
        total_missing = sum(len(s.missing_parameters) for s in result.steps)
        if total_missing > 0:
            print(f"   {total_missing} paramètre(s) manquant(s) au total")
    else:
        print("❌ Composition échouée")
        print(f"   • {len(result.errors)} erreur(s)")