"""
evaluation_suite.py
Suite complète d'évaluation et de tests pour le système de composition
"""
import sys
import os
import time
import json
from typing import Dict, List, Any, Tuple
from datetime import datetime
from dataclasses import dataclass
print("Script démarré...")

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from composition_system.classic_wsdl_parser import ClassicServiceRegistry
from composition_system.classic_composition_engine import ClassicCompositionEngine
from composition_system.intelligent_service_registry import IntelligentServiceRegistry
from composition_system.intelligent_composition_engine import IntelligentCompositionEngine
from composition_system.adaptive_executor import AdaptiveExecutor
from annotation_system.annotation_enricher import AnnotationEnricher


@dataclass
class TestScenario:
    """Scénario de test"""
    name: str
    description: str
    user_input: Dict[str, Any]
    user_context: Dict[str, Any]
    constraints: Dict[str, Any]
    expected_steps: int
    difficulty: str  # "easy", "medium", "hard"


@dataclass
class EvaluationMetrics:
    """Métriques d'évaluation"""
    scenario_name: str
    approach: str  # "classic" ou "intelligent_adaptive"
    
    # Succès
    success: bool
    steps_completed: int
    
    # Couverture
    avg_coverage: float
    total_missing_params: int
    
    # Performance
    execution_time_ms: int
    
    # Adaptation (uniquement pour intelligent_adaptive)
    adaptations_count: int = 0
    retries_count: int = 0
    fallbacks_count: int = 0
    
    # Qualité
    service_score: float = 0.0


class EvaluationSuite:
    """Suite d'évaluation complète du système"""
    
    def __init__(self):
        """Initialise la suite d'évaluation"""
        self.classic_registry = ClassicServiceRegistry()
        self.intelligent_registry = IntelligentServiceRegistry()
        self.classic_engine = ClassicCompositionEngine(self.classic_registry)
        self.intelligent_engine = IntelligentCompositionEngine(self.intelligent_registry)
        self.executor = AdaptiveExecutor(max_retries=3)
        self.enricher = AnnotationEnricher()
        
        self.results: List[EvaluationMetrics] = []
    
    def get_test_scenarios(self) -> List[TestScenario]:
        """Définit les scénarios de test"""
        
        scenarios = [
            # Scénario 1 : Cas nominal simple
            TestScenario(
                name="Voyage Standard",
                description="Voyage simple Paris → Tokyo avec toutes les données",
                user_input={
                    "origin": "Paris",
                    "destination": "Tokyo",
                    "departureDate": "2025-08-10",
                    "returnDate": "2025-08-17",
                    "passengers": 2,
                    "currency": "EUR",
                    "maxPrice": 3000.00,
                    "checkInDate": "2025-08-10",
                    "checkOutDate": "2025-08-17",
                    "guests": 2,
                    "rooms": 1,
                    "minStars": 4
                },
                user_context={
                    "location": "EU",
                    "budget_conscious": False,
                    "mission_critical": False
                },
                constraints={
                    "max_cost": 0.05,
                    "min_quality": 0.85
                },
                expected_steps=3,
                difficulty="easy"
            ),
            
            # Scénario 2 : Budget serré
            TestScenario(
                name="Voyage Budget",
                description="Voyage avec budget très limité",
                user_input={
                    "origin": "Paris",
                    "destination": "Berlin",
                    "departureDate": "2025-07-01",
                    "returnDate": "2025-07-05",
                    "passengers": 1,
                    "currency": "EUR",
                    "maxPrice": 500.00,
                    "checkInDate": "2025-07-01",
                    "checkOutDate": "2025-07-05",
                    "guests": 1,
                    "rooms": 1,
                    "minStars": 2
                },
                user_context={
                    "location": "EU",
                    "budget_conscious": True,
                    "mission_critical": False
                },
                constraints={
                    "max_cost": 0.02,
                    "min_quality": 0.80
                },
                expected_steps=3,
                difficulty="medium"
            ),
            
            # Scénario 3 : Mission critique
            TestScenario(
                name="Voyage d'Affaires Urgent",
                description="Voyage d'affaires avec exigences de qualité maximale",
                user_input={
                    "origin": "Paris",
                    "destination": "New York",
                    "departureDate": "2025-06-15",
                    "returnDate": "2025-06-20",
                    "passengers": 3,
                    "currency": "USD",
                    "maxPrice": 10000.00,
                    "checkInDate": "2025-06-15",
                    "checkOutDate": "2025-06-20",
                    "guests": 3,
                    "rooms": 2,
                    "minStars": 5
                },
                user_context={
                    "location": "EU",
                    "budget_conscious": False,
                    "mission_critical": True,
                    "needs_24_7": True,
                    "needs_multi_currency": True
                },
                constraints={
                    "max_cost": 0.10,
                    "min_quality": 0.95
                },
                expected_steps=3,
                difficulty="medium"
            ),
            
            # Scénario 4 : Données minimales (teste la self-configuration)
            TestScenario(
                name="Données Minimales",
                description="Très peu de données fournies - teste auto-configuration",
                user_input={
                    "origin": "Paris",
                    "destination": "London",
                    "departureDate": "2025-09-01",
                    "passengers": 1
                },
                user_context={
                    "location": "EU"
                },
                constraints={},
                expected_steps=3,
                difficulty="hard"
            ),
            
            # Scénario 5 : Voyage de groupe
            TestScenario(
                name="Voyage de Groupe",
                description="Grand groupe avec besoins complexes",
                user_input={
                    "origin": "Paris",
                    "destination": "Barcelona",
                    "departureDate": "2025-10-10",
                    "returnDate": "2025-10-15",
                    "passengers": 8,
                    "currency": "EUR",
                    "maxPrice": 5000.00,
                    "checkInDate": "2025-10-10",
                    "checkOutDate": "2025-10-15",
                    "guests": 8,
                    "rooms": 4,
                    "minStars": 3
                },
                user_context={
                    "location": "EU",
                    "budget_conscious": True
                },
                constraints={
                    "max_cost": 0.03,
                    "min_quality": 0.85
                },
                expected_steps=3,
                difficulty="hard"
            )
        ]
        
        return scenarios
    
    def evaluate_classic(self, scenario: TestScenario) -> EvaluationMetrics:
        """Évalue l'approche classique sur un scénario"""
        
        print(f"\n   Évaluation CLASSIQUE...")
        
        start_time = time.time()
        
        # Composer
        result = self.classic_engine.compose(
            goal="book_complete_travel",
            user_input=scenario.user_input
        )
        
        execution_time = int((time.time() - start_time) * 1000)
        
        # Calculer les métriques
        if result.steps:
            avg_coverage = sum(s.mapping_coverage for s in result.steps) / len(result.steps)
            total_missing = sum(len(s.missing_parameters) for s in result.steps)
        else:
            avg_coverage = 0.0
            total_missing = 0
        
        metrics = EvaluationMetrics(
            scenario_name=scenario.name,
            approach="classic",
            success=result.success,
            steps_completed=len(result.steps),
            avg_coverage=avg_coverage,
            total_missing_params=total_missing,
            execution_time_ms=execution_time
        )
        
        print(f"      Succès: {metrics.success}")
        print(f"      Couverture: {metrics.avg_coverage:.1%}")
        print(f"      Temps: {metrics.execution_time_ms}ms")
        
        return metrics
    
    def evaluate_intelligent_adaptive(self, scenario: TestScenario) -> EvaluationMetrics:
        """Évalue l'approche intelligente avec adaptation"""
        
        print(f"\n   Évaluation INTELLIGENTE + ADAPTATIVE...")
        
        start_time = time.time()
        
        # Composer
        result = self.intelligent_engine.compose(
            goal="book_complete_travel",
            user_input=scenario.user_input,
            user_context=scenario.user_context,
            constraints=scenario.constraints
        )
        
        # Exécuter avec adaptation
        execution_data = self.executor.execute_workflow_with_adaptation(
            result,
            scenario.user_input,
            self.intelligent_registry
        )
        
        execution_time = int((time.time() - start_time) * 1000)
        
        # Enregistrer les feedbacks
        for exec_result in execution_data["execution_results"]:
            self.enricher.record_execution_feedback(exec_result, result.workflow_id)
        
        # Calculer les métriques
        adaptations = len(execution_data["adaptation_history"])
        retries = sum(r.retry_count for r in execution_data["execution_results"])
        fallbacks = sum(1 for r in execution_data["execution_results"] if r.used_fallback)
        
        metrics = EvaluationMetrics(
            scenario_name=scenario.name,
            approach="intelligent_adaptive",
            success=execution_data["workflow_success"],
            steps_completed=len(execution_data["execution_results"]),
            avg_coverage=result.avg_mapping_coverage,
            total_missing_params=result.total_missing_params,
            execution_time_ms=execution_time,
            adaptations_count=adaptations,
            retries_count=retries,
            fallbacks_count=fallbacks,
            service_score=result.avg_service_score
        )
        
        print(f"      Succès: {metrics.success}")
        print(f"      Couverture: {metrics.avg_coverage:.1%}")
        print(f"      Score services: {metrics.service_score:.3f}")
        print(f"      Adaptations: {metrics.adaptations_count}")
        print(f"      Temps: {metrics.execution_time_ms}ms")
        
        return metrics
    
    def run_evaluation(self):
        """Lance l'évaluation complète"""
        
        print("="*80)
        print("SUITE D'ÉVALUATION COMPLÈTE")
        print("="*80)
        
        scenarios = self.get_test_scenarios()
        
        print(f"\n{len(scenarios)} scénarios de test définis:")
        for i, scenario in enumerate(scenarios, 1):
            print(f"   {i}. {scenario.name} ({scenario.difficulty})")
            print(f"      {scenario.description}")
        
        # Évaluer chaque scénario
        for i, scenario in enumerate(scenarios, 1):
            print(f"\n{'='*80}")
            print(f"SCÉNARIO {i}/{len(scenarios)}: {scenario.name}")
            print(f"{'='*80}")
            print(f"Difficulté: {scenario.difficulty.upper()}")
            print(f"Description: {scenario.description}")
            
            # Approche classique
            classic_metrics = self.evaluate_classic(scenario)
            self.results.append(classic_metrics)
            
            # Approche intelligente + adaptative
            intelligent_metrics = self.evaluate_intelligent_adaptive(scenario)
            self.results.append(intelligent_metrics)
            
            # Comparaison rapide
            print(f"\n   📊 Comparaison:")
            print(f"      Couverture: {classic_metrics.avg_coverage:.1%} → {intelligent_metrics.avg_coverage:.1%}")
            print(f"      Paramètres manquants: {classic_metrics.total_missing_params} → {intelligent_metrics.total_missing_params}")
            print(f"      Adaptations: 0 → {intelligent_metrics.adaptations_count}")
        
        # Sauvegarder les feedbacks
        self.enricher.save_feedback_history()
        
        # Enrichir les annotations
        print(f"\n{'='*80}")
        print("ENRICHISSEMENT DES ANNOTATIONS")
        print(f"{'='*80}")
        
        self.enricher.enrich_all_annotations()
    
    def generate_report(self):
        """Génère un rapport détaillé d'évaluation"""
        
        print("\n" + "="*80)
        print("RAPPORT D'ÉVALUATION DÉTAILLÉ")
        print("="*80)
        
        # Séparer les résultats par approche
        classic_results = [r for r in self.results if r.approach == "classic"]
        intelligent_results = [r for r in self.results if r.approach == "intelligent_adaptive"]
        
        # 1. Taux de succès
        print("\n1️⃣  TAUX DE SUCCÈS")
        print("─"*80)
        
        classic_success = sum(1 for r in classic_results if r.success)
        intelligent_success = sum(1 for r in intelligent_results if r.success)
        
        print(f"   Classique: {classic_success}/{len(classic_results)} ({classic_success/len(classic_results):.1%})")
        print(f"   Intelligent + Adaptatif: {intelligent_success}/{len(intelligent_results)} ({intelligent_success/len(intelligent_results):.1%})")
        
        # 2. Couverture moyenne
        print("\n2️⃣  COUVERTURE DES PARAMÈTRES")
        print("─"*80)
        
        classic_avg_cov = sum(r.avg_coverage for r in classic_results) / len(classic_results)
        intelligent_avg_cov = sum(r.avg_coverage for r in intelligent_results) / len(intelligent_results)
        
        print(f"   Classique: {classic_avg_cov:.1%}")
        print(f"   Intelligent + Adaptatif: {intelligent_avg_cov:.1%}")
        print(f"   Amélioration: +{(intelligent_avg_cov - classic_avg_cov)*100:.1f} points")
        
        # 3. Paramètres manquants
        print("\n3️⃣  PARAMÈTRES MANQUANTS (total)")
        print("─"*80)
        
        classic_missing = sum(r.total_missing_params for r in classic_results)
        intelligent_missing = sum(r.total_missing_params for r in intelligent_results)
        
        print(f"   Classique: {classic_missing}")
        print(f"   Intelligent + Adaptatif: {intelligent_missing}")
        if classic_missing > 0:
            reduction = (classic_missing - intelligent_missing) / classic_missing * 100
            print(f"   Réduction: -{reduction:.1f}%")
        
        # 4. Performance
        print("\n4️⃣  PERFORMANCE (temps d'exécution moyen)")
        print("─"*80)
        
        classic_avg_time = sum(r.execution_time_ms for r in classic_results) / len(classic_results)
        intelligent_avg_time = sum(r.execution_time_ms for r in intelligent_results) / len(intelligent_results)
        
        print(f"   Classique: {classic_avg_time:.0f}ms")
        print(f"   Intelligent + Adaptatif: {intelligent_avg_time:.0f}ms")
        overhead = ((intelligent_avg_time - classic_avg_time) / classic_avg_time) * 100
        print(f"   Overhead: +{overhead:.1f}% (dû à l'adaptation et scoring)")
        
        # 5. Capacités adaptatives (uniquement intelligent)
        print("\n5️⃣  CAPACITÉS ADAPTATIVES (Intelligent + Adaptatif)")
        print("─"*80)
        
        total_adaptations = sum(r.adaptations_count for r in intelligent_results)
        total_retries = sum(r.retries_count for r in intelligent_results)
        total_fallbacks = sum(r.fallbacks_count for r in intelligent_results)
        
        print(f"   Adaptations effectuées: {total_adaptations}")
        print(f"   Tentatives de retry: {total_retries}")
        print(f"   Fallbacks utilisés: {total_fallbacks}")
        
        # 6. Score qualité des services
        print("\n6️⃣  QUALITÉ DES SERVICES SÉLECTIONNÉS")
        print("─"*80)
        
        avg_score = sum(r.service_score for r in intelligent_results) / len(intelligent_results)
        print(f"   Score moyen: {avg_score:.3f}/1.000")
        print(f"   (La sélection classique n'a pas de scoring)")
        
        # 7. Tableau récapitulatif par scénario
        print("\n7️⃣  RÉCAPITULATIF PAR SCÉNARIO")
        print("─"*80)
        
        scenarios = list(set(r.scenario_name for r in self.results))
        
        for scenario in scenarios:
            classic = next(r for r in classic_results if r.scenario_name == scenario)
            intelligent = next(r for r in intelligent_results if r.scenario_name == scenario)
            
            print(f"\n   {scenario}:")
            print(f"      Succès: {classic.success} → {intelligent.success}")
            print(f"      Couverture: {classic.avg_coverage:.1%} → {intelligent.avg_coverage:.1%}")
            print(f"      Manquants: {classic.total_missing_params} → {intelligent.total_missing_params}")
            print(f"      Adaptations: 0 → {intelligent.adaptations_count}")
        
        # 8. Analyse par difficulté
        print("\n8️⃣  ANALYSE PAR DIFFICULTÉ")
        print("─"*80)
        
        scenarios_list = self.get_test_scenarios()
        difficulties = {"easy": [], "medium": [], "hard": []}
        
        for scenario in scenarios_list:
            classic = next(r for r in classic_results if r.scenario_name == scenario.name)
            intelligent = next(r for r in intelligent_results if r.scenario_name == scenario.name)
            difficulties[scenario.difficulty].append((classic, intelligent))
        
        for difficulty, pairs in difficulties.items():
            if not pairs:
                continue
            
            print(f"\n   {difficulty.upper()}:")
            
            classic_success = sum(1 for c, _ in pairs if c.success)
            intel_success = sum(1 for _, i in pairs if i.success)
            
            classic_cov = sum(c.avg_coverage for c, _ in pairs) / len(pairs)
            intel_cov = sum(i.avg_coverage for _, i in pairs) / len(pairs)
            
            print(f"      Succès: {classic_success}/{len(pairs)} vs {intel_success}/{len(pairs)}")
            print(f"      Couverture moyenne: {classic_cov:.1%} vs {intel_cov:.1%}")
        
        # 9. Conclusion
        print("\n" + "="*80)
        print("CONCLUSION")
        print("="*80)
        
        print("\n✅ AVANTAGES DE L'APPROCHE INTELLIGENTE + ADAPTATIVE:")
        
        if intelligent_avg_cov > classic_avg_cov:
            print(f"   • Meilleure couverture: +{(intelligent_avg_cov - classic_avg_cov)*100:.1f} points")
        
        if intelligent_missing < classic_missing:
            print(f"   • Moins de paramètres manquants: -{classic_missing - intelligent_missing}")
        
        if intelligent_success >= classic_success:
            print(f"   • Taux de succès égal ou supérieur")
        
        if total_adaptations > 0:
            print(f"   • Capacité d'adaptation: {total_adaptations} adaptations effectuées")
        
        print(f"   • Intelligence contextuelle: Score moyen {avg_score:.3f}")
        print(f"   • Auto-configuration: Self-configuration des paramètres")
        print(f"   • Robustesse: {total_retries} retries, {total_fallbacks} fallbacks")
        
        print("\n  COÛT:")
        print(f"   • Overhead de performance: +{overhead:.1f}%")
        print(f"   • Complexité accrue du système")
        print(f"   • Dépendance aux annotations LLM")
        
        # Sauvegarder le rapport
        self.save_report()
    
    def save_report(self):
        """Sauvegarde le rapport en JSON"""
        
        output_dir = "evaluation_results"
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = os.path.join(output_dir, f"evaluation_report_{timestamp}.json")
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "scenarios_count": len(self.get_test_scenarios()),
            "results": [
                {
                    "scenario_name": r.scenario_name,
                    "approach": r.approach,
                    "success": r.success,
                    "steps_completed": r.steps_completed,
                    "avg_coverage": r.avg_coverage,
                    "total_missing_params": r.total_missing_params,
                    "execution_time_ms": r.execution_time_ms,
                    "adaptations_count": r.adaptations_count,
                    "retries_count": r.retries_count,
                    "fallbacks_count": r.fallbacks_count,
                    "service_score": r.service_score
                }
                for r in self.results
            ]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Rapport sauvegardé: {filepath}")


def main():
    """Lance la suite d'évaluation complète"""
    
    print("="*80)
    print("SUITE D'ÉVALUATION COMPLÈTE DU SYSTÈME")
    print("="*80)
    
    print("\nCette suite va :")
    print("   1. Tester 5 scénarios variés (facile, moyen, difficile)")
    print("   2. Comparer approche classique vs intelligente+adaptative")
    print("   3. Mesurer : succès, couverture, performance, adaptations")
    print("   4. Enrichir les annotations avec les feedbacks")
    print("   5. Générer un rapport détaillé")
    
    input("\n⏸️  Appuyez sur Entrée pour démarrer l'évaluation...")
    
    # Créer et lancer la suite
    suite = EvaluationSuite()
    
    # Lancer l'évaluation
    suite.run_evaluation()
    
    # Générer le rapport
    suite.generate_report()
    
    print("\n" + "="*80)
    print("ÉVALUATION TERMINÉE")
    print("="*80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Évaluation interrompue")
    except Exception as e:
        print(f"\n\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()