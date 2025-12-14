"""
composition_system/hybrid_composition_engine.py
Moteur de composition hybride combinant services classiques + services LLM
"""
import sys
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from composition_system.intelligent_composition_engine import (
    IntelligentCompositionEngine, IntelligentWorkflowStep
)
from composition_system.intelligent_service_registry import IntelligentServiceRegistry

# Import des services LLM
try:
    # Ajouter le chemin absolu vers services/implementations
    services_impl_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'services', 'implementations')
    )
    if services_impl_path not in sys.path:
        sys.path.insert(0, services_impl_path)
    
    from services.implementations.llm_recommendation_service import IntelligentRecommendationService 
    from services.implementations.llm_travel_summary_service import IntelligentTravelSummaryService
    
    LLM_SERVICES_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Services LLM non trouvés: {e}")
    print(f"   Chemin recherché: {services_impl_path if 'services_impl_path' in locals() else 'N/A'}")
    LLM_SERVICES_AVAILABLE = False
    IntelligentRecommendationService = None
    IntelligentTravelSummaryService = None


@dataclass
class HybridWorkflowStep:
    """Étape hybride combinant service classique et service LLM"""
    step_number: int
    step_type: str  # "classic", "llm", "hybrid"
    
    # Service classique (si applicable)
    classic_service: Optional[str] = None
    classic_operation: Optional[str] = None
    classic_result: Optional[Dict] = None
    
    # Service LLM (si applicable)
    llm_service: Optional[str] = None
    llm_operation: Optional[str] = None
    llm_result: Optional[Any] = None
    
    # Métadonnées
    description: str = ""
    inputs: Dict[str, Any] = None
    outputs: Dict[str, Any] = None
    execution_time_ms: int = 0


@dataclass
class HybridCompositionResult:
    """Résultat de composition hybride"""
    workflow_id: str
    goal: str
    steps: List[HybridWorkflowStep]
    success: bool
    created_at: datetime
    
    # Métriques
    total_classic_steps: int
    total_llm_steps: int
    total_hybrid_steps: int
    avg_execution_time: float
    
    # Résultats finaux
    final_recommendation: Optional[Any] = None
    final_summary: Optional[Any] = None
    
    errors: List[str] = None


class HybridCompositionEngine:
    """
    Moteur de composition hybride
    
    Combine :
    - Services classiques (WSDL, règles fixes)
    - Services LLM (recommandation, résumé, analyse)
    
    Workflows disponibles :
    - enhanced_travel_booking : Classique + recommandations LLM
    - intelligent_travel_planning : Tout LLM-assisted
    """
    
    # Workflows hybrides prédéfinis
    HYBRID_WORKFLOWS = {
        "enhanced_travel_booking": [
            {"step": 1, "type": "llm", "service": "recommendation", "function": "analyze_preferences"},
            {"step": 2, "type": "classic", "category": "search", "function": "flights"},
            {"step": 3, "type": "hybrid", "classic_category": "search", "classic_function": "hotels", 
             "llm_service": "summary", "llm_function": "compare"},
            {"step": 4, "type": "classic", "category": "payment", "function": "process"},
            {"step": 5, "type": "llm", "service": "summary", "function": "generate_summary"}
        ],
        
        "intelligent_travel_planning": [
            {"step": 1, "type": "llm", "service": "recommendation", "function": "recommend_destination"},
            {"step": 2, "type": "llm", "service": "recommendation", "function": "generate_itinerary"},
            {"step": 3, "type": "classic", "category": "search", "function": "flights"},
            {"step": 4, "type": "classic", "category": "search", "function": "hotels"},
            {"step": 5, "type": "hybrid", "classic_category": "payment", 
             "llm_service": "summary", "llm_function": "analyze_feasibility"},
            {"step": 6, "type": "llm", "service": "summary", "function": "create_document"}
        ]
    }
    
    def __init__(self, intelligent_registry: IntelligentServiceRegistry):
        """
        Initialise le moteur hybride
        
        Args:
            intelligent_registry: Registre des services classiques annotés
        """
        self.intelligent_registry = intelligent_registry
        self.intelligent_engine = IntelligentCompositionEngine(intelligent_registry)
        
        # Initialiser les services LLM
        if LLM_SERVICES_AVAILABLE:
            try:
                self.recommendation_service = IntelligentRecommendationService()
                self.summary_service = IntelligentTravelSummaryService()
                print("✓ Services LLM initialisés")
            except Exception as e:
                print(f"⚠️  Services LLM non disponibles: {e}")
                self.recommendation_service = None
                self.summary_service = None
        else:
            print("⚠️  Services LLM non chargés (module non trouvé)")
            self.recommendation_service = None
            self.summary_service = None
    
    def compose_hybrid(self,
                      goal: str,
                      user_input: Dict[str, Any],
                      user_context: Optional[Dict[str, Any]] = None) -> HybridCompositionResult:
        """
        Compose un workflow hybride
        
        Args:
            goal: Objectif (enhanced_travel_booking, intelligent_travel_planning)
            user_input: Données utilisateur
            user_context: Contexte utilisateur
            
        Returns:
            HybridCompositionResult
        """
        print("\n" + "="*80)
        print(f"COMPOSITION HYBRIDE - Objectif: {goal}")
        print("="*80)
        
        user_context = user_context or {}
        
        if goal not in self.HYBRID_WORKFLOWS:
            return HybridCompositionResult(
                workflow_id=f"hwf_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                goal=goal,
                steps=[],
                success=False,
                created_at=datetime.now(),
                total_classic_steps=0,
                total_llm_steps=0,
                total_hybrid_steps=0,
                avg_execution_time=0,
                errors=[f"Workflow '{goal}' inconnu"]
            )
        
        workflow_template = self.HYBRID_WORKFLOWS[goal]
        steps = []
        errors = []
        context = user_input.copy()
        
        # Compteurs
        classic_count = 0
        llm_count = 0
        hybrid_count = 0
        
        print(f"\nWorkflow: {len(workflow_template)} étapes (hybride)")
        
        # Exécuter chaque étape
        for step_def in workflow_template:
            print(f"\n{'─'*80}")
            print(f"ÉTAPE {step_def['step']}: {step_def['type'].upper()}")
            print(f"{'─'*80}")
            
            start_time = datetime.now()
            
            try:
                if step_def['type'] == 'llm':
                    step_result = self._execute_llm_step(step_def, context, user_context)
                    llm_count += 1
                    
                elif step_def['type'] == 'classic':
                    step_result = self._execute_classic_step(step_def, context, user_context)
                    classic_count += 1
                    
                elif step_def['type'] == 'hybrid':
                    step_result = self._execute_hybrid_step(step_def, context, user_context)
                    hybrid_count += 1
                
                else:
                    raise ValueError(f"Type inconnu: {step_def['type']}")
                
                # Calculer temps d'exécution
                execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
                step_result.execution_time_ms = execution_time
                
                steps.append(step_result)
                
                # Enrichir le contexte avec les sorties
                if step_result.outputs:
                    context.update(step_result.outputs)
                
                print(f"✓ Étape {step_def['step']} terminée ({execution_time}ms)")
                
            except Exception as e:
                error_msg = f"Erreur étape {step_def['step']}: {str(e)}"
                errors.append(error_msg)
                print(f"✗ {error_msg}")
        
        # Calculer temps moyen
        avg_time = sum(s.execution_time_ms for s in steps) / len(steps) if steps else 0
        
        # Extraire résultats finaux
        final_recommendation = None
        final_summary = None
        
        for step in steps:
            if step.llm_service == "recommendation" and step.llm_result:
                final_recommendation = step.llm_result
            elif step.llm_service == "summary" and "summary" in step.llm_operation.lower():
                final_summary = step.llm_result
        
        result = HybridCompositionResult(
            workflow_id=f"hwf_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            goal=goal,
            steps=steps,
            success=len(errors) == 0,
            created_at=datetime.now(),
            total_classic_steps=classic_count,
            total_llm_steps=llm_count,
            total_hybrid_steps=hybrid_count,
            avg_execution_time=avg_time,
            final_recommendation=final_recommendation,
            final_summary=final_summary,
            errors=errors
        )
        
        return result
    
    def _execute_llm_step(self, step_def: Dict, context: Dict, user_context: Dict) -> HybridWorkflowStep:
        """Exécute une étape purement LLM"""
        
        service_name = step_def['service']
        function_name = step_def['function']
        
        print(f"🤖 Service LLM: {service_name}.{function_name}")
        
        llm_result = None
        outputs = {}
        
        # Vérifier que les services sont disponibles
        if not self.recommendation_service and service_name == "recommendation":
            print("   ⚠️ Service de recommandation non disponible")
            return HybridWorkflowStep(
                step_number=step_def['step'],
                step_type='llm',
                llm_service=service_name,
                llm_operation=function_name,
                llm_result=None,
                description=f"Service LLM (indisponible): {service_name}.{function_name}",
                inputs=context.copy(),
                outputs={}
            )
        
        if not self.summary_service and service_name == "summary":
            print("   ⚠️ Service de résumé non disponible")
            return HybridWorkflowStep(
                step_number=step_def['step'],
                step_type='llm',
                llm_service=service_name,
                llm_operation=function_name,
                llm_result=None,
                description=f"Service LLM (indisponible): {service_name}.{function_name}",
                inputs=context.copy(),
                outputs={}
            )
        
        if service_name == "recommendation":
            if function_name == "recommend_destination":
                preferences = user_context.get('preferences', {})
                budget = context.get('maxPrice', 2000.0)
                duration = context.get('duration_days', 7)
                
                llm_result = self.recommendation_service.recommend_destination(
                    user_preferences=preferences,
                    budget=budget,
                    duration_days=duration,
                    season=user_context.get('season', 'any')
                )
                
                if llm_result:
                    # Convertir en dict pour faciliter la sérialisation
                    outputs['recommended_destination'] = llm_result.destination
                    outputs['recommendation_reason'] = llm_result.reason
                    outputs['estimated_budget'] = llm_result.estimated_budget
                    
                    # Stocker aussi l'objet complet
                    # mais convertir en dict pour éviter les problèmes d'attributs
                    outputs['_recommendation_full'] = {
                        'destination': llm_result.destination,
                        'reason': llm_result.reason,
                        'best_season': llm_result.best_season,
                        'estimated_budget': llm_result.estimated_budget,
                        'activities': llm_result.activities,
                        'tips': llm_result.tips,
                        'confidence_score': llm_result.confidence_score
                    }
            
            elif function_name == "generate_itinerary":
                destination = context.get('recommended_destination', context.get('destination', 'Paris'))
                duration = context.get('duration_days', 7)
                interests = user_context.get('interests', ['culture'])
                
                llm_result = self.recommendation_service.generate_personalized_itinerary(
                    destination=destination,
                    duration_days=duration,
                    interests=interests,
                    budget_per_day=150.0
                )
                
                if llm_result:
                    outputs['itinerary'] = [
                        {
                            'day_number': day.day_number,
                            'date': day.date,
                            'morning': day.morning,
                            'afternoon': day.afternoon,
                            'evening': day.evening,
                            'estimated_cost': day.estimated_cost
                        }
                        for day in llm_result
                    ]
                    outputs['itinerary_days'] = len(llm_result)
            
            elif function_name == "analyze_preferences":
                free_text = user_context.get('free_text_request', '')
                if free_text:
                    llm_result = self.recommendation_service.analyze_user_preferences(free_text)
                    outputs['analyzed_preferences'] = llm_result
        
        elif service_name == "summary":
            if function_name == "generate_summary":
                flight_info = context.get('flight_details', {})
                hotel_info = context.get('hotel_details', {})
                user_profile = user_context.get('user_profile', {})
                
                llm_result = self.summary_service.generate_trip_summary(
                    flight_details=flight_info,
                    hotel_details=hotel_info,
                    user_profile=user_profile
                )
                
                if llm_result:
                    # Convertir en dict
                    outputs['trip_summary'] = {
                        'title': llm_result.title,
                        'overview': llm_result.overview,
                        'highlights': llm_result.highlights,
                        'personalized_message': llm_result.personalized_message
                    }
                    outputs['total_estimated_cost'] = llm_result.estimated_costs_breakdown.get('total', 0)
            
            elif function_name == "compare":
                options = context.get('options_to_compare', [])
                priorities = user_context.get('priorities', {})
                
                if options:
                    llm_result = self.summary_service.compare_service_options(options, priorities)
                    if llm_result:
                        outputs['best_choice'] = llm_result.best_choice
                        outputs['comparison_reason'] = llm_result.reason
        
        return HybridWorkflowStep(
            step_number=step_def['step'],
            step_type='llm',
            llm_service=service_name,
            llm_operation=function_name,
            llm_result=llm_result,
            description=f"Service LLM: {service_name}.{function_name}",
            inputs=context.copy(),
            outputs=outputs
        )
    
    def _execute_classic_step(self, step_def: Dict, context: Dict, user_context: Dict) -> HybridWorkflowStep:
        """Exécute une étape classique via le moteur intelligent"""
        
        category = step_def['category']
        
        print(f"⚙️  Service classique: {category}")
        
        # Utiliser le moteur intelligent pour sélectionner le service
        service_score = self.intelligent_registry.select_best_service(
            category=category,
            user_context=user_context,
            constraints={}
        )
        
        outputs = {}
        if service_score:
            service_name = service_score.service_name
            
            # Simuler l'exécution (dans un vrai système, appel réel au service)
            if "Flight" in service_name:
                outputs = {
                    "flight_details": {
                        "service": service_name,
                        "price": 450.0,
                        "from": context.get('origin', 'Paris'),
                        "to": context.get('destination', 'Tokyo')
                    }
                }
            elif "Hotel" in service_name:
                outputs = {
                    "hotel_details": {
                        "service": service_name,
                        "name": "Selected Hotel",
                        "price_per_night": 120.0
                    }
                }
            elif "Payment" in service_name:
                outputs = {
                    "payment_result": {
                        "transaction_id": f"TXN_{int(datetime.now().timestamp())}",
                        "status": "completed"
                    }
                }
        
        return HybridWorkflowStep(
            step_number=step_def['step'],
            step_type='classic',
            classic_service=service_score.service_name if service_score else None,
            classic_operation=category,
            classic_result=outputs,
            description=f"Service classique: {category}",
            inputs=context.copy(),
            outputs=outputs
        )
    
    def _execute_hybrid_step(self, step_def: Dict, context: Dict, user_context: Dict) -> HybridWorkflowStep:
        """Exécute une étape hybride (classique + LLM)"""
        
        print(f"🔀 Étape hybride: classique + LLM")
        
        # 1. Partie classique
        classic_result = self._execute_classic_step(step_def, context, user_context)
        
        # 2. Partie LLM (analyse du résultat classique)
        llm_service = step_def.get('llm_service')
        llm_function = step_def.get('llm_function')
        
        llm_result = None
        combined_outputs = classic_result.outputs.copy()
        
        if llm_service == "summary" and llm_function == "compare":
            # Le LLM analyse les résultats du service classique
            options = [classic_result.classic_result] if classic_result.classic_result else []
            priorities = user_context.get('priorities', {})
            
            if options:
                llm_result = self.summary_service.compare_service_options(options, priorities)
                if llm_result:
                    combined_outputs['llm_analysis'] = {
                        "best_choice": llm_result.best_choice,
                        "reason": llm_result.reason,
                        "confidence": llm_result.recommendation_strength
                    }
        
        return HybridWorkflowStep(
            step_number=step_def['step'],
            step_type='hybrid',
            classic_service=classic_result.classic_service,
            classic_operation=classic_result.classic_operation,
            classic_result=classic_result.classic_result,
            llm_service=llm_service,
            llm_operation=llm_function,
            llm_result=llm_result,
            description=f"Hybride: {classic_result.classic_service} + LLM analysis",
            inputs=context.copy(),
            outputs=combined_outputs
        )
    
    def print_result(self, result: HybridCompositionResult):
        """Affiche le résultat de manière formatée"""
        
        print("\n\n" + "="*80)
        print("RÉSULTAT DE LA COMPOSITION HYBRIDE")
        print("="*80)
        
        print(f"\nID: {result.workflow_id}")
        print(f"Objectif: {result.goal}")
        print(f"Statut: {'✅ SUCCÈS' if result.success else '❌ ÉCHEC'}")
        
        print(f"\nSTATISTIQUES:")
        print(f"   • Étapes classiques: {result.total_classic_steps}")
        print(f"   • Étapes LLM: {result.total_llm_steps}")
        print(f"   • Étapes hybrides: {result.total_hybrid_steps}")
        print(f"   • Temps moyen: {result.avg_execution_time:.0f}ms")
        
        print(f"\n{'='*80}")
        print("WORKFLOW DÉTAILLÉ")
        print("="*80)
        
        for step in result.steps:
            icon = "🤖" if step.step_type == "llm" else "⚙️" if step.step_type == "classic" else "🔀"
            print(f"\n{icon} ÉTAPE {step.step_number}: {step.step_type.upper()}")
            print(f"{'─'*80}")
            print(f"   {step.description}")
            print(f"   Temps: {step.execution_time_ms}ms")
            
            if step.outputs:
                print(f"   Sorties: {list(step.outputs.keys())}")
        
        if result.final_recommendation:
            print(f"\n{'='*80}")
            print("RECOMMANDATION FINALE")
            print("="*80)
            rec = result.final_recommendation
            
            # Gérer dict ou objet
            if isinstance(rec, dict):
                print(f"\n📍 {rec.get('destination', 'N/A')}")
                print(f"💭 {rec.get('reason', 'N/A')}")
            else:
                print(f"\n📍 {rec.destination}")
                print(f"💭 {rec.reason}")
        
        if result.final_summary:
            print(f"\n{'='*80}")
            print("RÉSUMÉ FINAL")
            print("="*80)
            summary = result.final_summary
            
            # Gérer dict ou objet
            if isinstance(summary, dict):
                print(f"\n📋 {summary.get('title', 'N/A')}")
                print(f"\n{summary.get('overview', 'N/A')}")
            else:
                print(f"\n📋 {summary.title}")
                print(f"\n{summary.overview}")
        
        print(f"\n{'='*80}\n")
    
    def save_result(self, result: HybridCompositionResult, 
                   output_dir: str = "composition_system/results"):
        """Sauvegarde le résultat"""
        os.makedirs(output_dir, exist_ok=True)
        
        filename = f"{result.workflow_id}_hybrid.json"
        filepath = os.path.join(output_dir, filename)
        
        result_dict = {
            "workflow_id": result.workflow_id,
            "goal": result.goal,
            "success": result.success,
            "created_at": result.created_at.isoformat(),
            "total_classic_steps": result.total_classic_steps,
            "total_llm_steps": result.total_llm_steps,
            "total_hybrid_steps": result.total_hybrid_steps,
            "avg_execution_time": result.avg_execution_time,
            "steps": [
                {
                    "step_number": s.step_number,
                    "step_type": s.step_type,
                    "description": s.description,
                    "execution_time_ms": s.execution_time_ms
                }
                for s in result.steps
            ],
            "errors": result.errors
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result_dict, f, indent=2, ensure_ascii=False)
        
        print(f"Résultat sauvegardé: {filepath}")


# Test
if __name__ == "__main__":
    print("TEST DE LA COMPOSITION HYBRIDE\n")
    
    # Charger le registre
    from composition_system.intelligent_service_registry import IntelligentServiceRegistry
    
    registry = IntelligentServiceRegistry()
    
    if not registry.services:
        print("❌ Registre vide")
        exit(1)
    
    # Créer le moteur
    engine = HybridCompositionEngine(registry)
    
    # Test
    user_input = {
        "origin": "Paris",
        "destination": "Tokyo",
        "duration_days": 7,
        "maxPrice": 3000.0
    }
    
    user_context = {
        "preferences": {
            "interests": ["culture", "food", "technology"],
            "travel_style": "cultural"
        },
        "user_profile": {
            "name": "Test User",
            "interests": ["culture", "food"]
        }
    }
    
    result = engine.compose_hybrid(
        goal="enhanced_travel_booking",
        user_input=user_input,
        user_context=user_context
    )
    
    engine.print_result(result)
    engine.save_result(result)