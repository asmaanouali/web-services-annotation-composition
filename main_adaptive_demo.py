"""
main_adaptive_demo.py
Démonstration complète du système avec adaptation et enrichissement
"""
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Imports des systèmes de composition
from composition_system.classic_wsdl_parser import ClassicServiceRegistry
from composition_system.classic_composition_engine import ClassicCompositionEngine
from composition_system.intelligent_service_registry import IntelligentServiceRegistry
from composition_system.intelligent_composition_engine import IntelligentCompositionEngine

# Imports des nouveaux composants
from composition_system.adaptive_executor import AdaptiveExecutor
from annotation_system.annotation_enricher import AnnotationEnricher


def print_header(title: str, char: str = "="):
    """Affiche un en-tête formaté"""
    print("\n" + char*80)
    print(f"  {title}")
    print(char*80 + "\n")


def print_section(title: str):
    """Affiche une section"""
    print("\n" + "─"*80)
    print(f"  {title}")
    print("─"*80)


def main():
    """Démonstration complète avec adaptation et enrichissement"""
    
    print_header("SYSTÈME DE COMPOSITION ADAPTATIF ET AUTO-APPRENANT")
    
    print("Ce programme démontre les capacités avancées du système :")
    print("   1. Self-Configuration : Ajustement automatique des paramètres")
    print("   2. Self-Adaptation : Basculement vers alternatives en cas d'échec")
    print("   3. Self-Protection : Retry, timeout, fallback graceful")
    print("   4. Enrichissement Continu : Apprentissage depuis l'historique")
    
    # =========================================================================
    # PARTIE 1 : COMPOSITION INTELLIGENTE AVEC ADAPTATION
    # =========================================================================
    print_header("PARTIE 1 : COMPOSITION INTELLIGENTE AVEC EXÉCUTION ADAPTATIVE", "=")
    
    print_section("Étape 1.1 : Chargement du Registre Intelligent")
    
    intelligent_registry = IntelligentServiceRegistry()
    
    if not intelligent_registry.services:
        print(" Erreur : Aucune annotation trouvée")
        print("   Exécutez d'abord: python annotation_system/batch_annotate.py")
        return
    
    print(f"{len(intelligent_registry.services)} services chargés avec annotations LLM")
    
    print_section("Étape 1.2 : Définition du Scénario")
    
    # Scénario : Voyage d'affaires urgent
    scenario = {
        "description": "Voyage d'affaires urgent Paris → Tokyo",
        "user_profile": {
            "name": "Jean Dupont",
            "company": "TechCorp International",
            "priority": "Fiabilité maximale"
        }
    }
    
    print(f"Utilisateur: {scenario['user_profile']['name']}")
    print(f"   Entreprise: {scenario['user_profile']['company']}")
    print(f"   Priorité: {scenario['user_profile']['priority']}")
    
    # Contexte enrichi
    user_context = {
        "location": "EU",
        "mission_critical": True,      # Mission critique
        "needs_multi_currency": True,
        "needs_24_7": True,
        "budget_conscious": False      # Priorité à la qualité
    }
    
    constraints = {
        "max_cost": 0.05,
        "min_quality": 0.90
    }
    
    user_input = {
        "origin": "Paris",
        "destination": "Tokyo",
        "departureDate": "2025-08-10",
        "returnDate": "2025-08-17",
        "passengers": 1,
        "currency": "EUR",
        "maxPrice": 3500.00,
        "checkInDate": "2025-08-10",
        "checkOutDate": "2025-08-17",
        "guests": 1,
        "rooms": 1,
        "minStars": 4
    }
    
    print_section("Étape 1.3 : Composition Intelligente")
    
    intelligent_engine = IntelligentCompositionEngine(intelligent_registry)
    
    intelligent_result = intelligent_engine.compose(
        goal="book_complete_travel",
        user_input=user_input,
        user_context=user_context,
        constraints=constraints
    )
    
    print_section("Étape 1.4 : Exécution Adaptative du Workflow")
    
    # Créer l'exécuteur adaptatif
    executor = AdaptiveExecutor(max_retries=3, timeout_seconds=30)
    
    print("Lancement de l'exécution adaptative...")
    print("   Le système va automatiquement :")
    print("      • Configurer les paramètres manquants")
    print("      • Réessayer en cas d'échec (retry)")
    print("      • Basculer vers des alternatives si nécessaire")
    print("      • Activer le fallback en dernier recours")
    
    # Exécuter avec adaptation
    execution_data = executor.execute_workflow_with_adaptation(
        intelligent_result,
        user_input,
        intelligent_registry
    )
    
    # Sauvegarder le rapport d'exécution
    executor.save_execution_report(execution_data)
    
    # =========================================================================
    # PARTIE 2 : ENRICHISSEMENT DES ANNOTATIONS
    # =========================================================================
    print_header("PARTIE 2 : ENRICHISSEMENT DES ANNOTATIONS", "=")
    
    print_section("Étape 2.1 : Enregistrement des Feedbacks")
    
    # Créer l'enrichisseur
    enricher = AnnotationEnricher()
    
    print("Enregistrement des feedbacks d'exécution...")
    
    # Enregistrer chaque résultat d'exécution
    for result in execution_data["execution_results"]:
        enricher.record_execution_feedback(
            result,
            workflow_id=intelligent_result.workflow_id
        )
    
    print(f"{len(execution_data['execution_results'])} feedbacks enregistrés")
    
    # Sauvegarder l'historique
    enricher.save_feedback_history()
    
    print_section("Étape 2.2 : Enrichissement des Annotations")
    
    print("Enrichissement des annotations avec les données d'exécution réelles...")
    
    # Enrichir les annotations des services utilisés
    services_used = set(r.service_name for r in execution_data["execution_results"])
    
    for service_name in services_used:
        enricher.enrich_annotation(service_name)
    
    print_section("Étape 2.3 : Génération du Rapport d'Enrichissement")
    
    report = enricher.generate_enrichment_report()
    
    print("\nStatistiques des services après enrichissement:")
    for service, stats in report['services'].items():
        print(f"\n   {service}:")
        print(f"      • Exécutions totales: {stats['total_executions']}")
        print(f"      • Taux de succès: {stats['success_rate']:.1%}")
        print(f"      • Temps moyen: {stats['avg_response_time_ms']:.0f}ms")
        print(f"      • Retries: {stats['total_retries']}")
    
    # =========================================================================
    # PARTIE 3 : ANALYSE DES CAPACITÉS ADAPTATIVES
    # =========================================================================
    print_header("PARTIE 3 : ANALYSE DES CAPACITÉS ADAPTATIVES", "=")
    
    print_section("Résumé des Adaptations")
    
    if execution_data["adaptation_history"]:
        print(f"\n{len(execution_data['adaptation_history'])} événements d'adaptation détectés:\n")
        
        for event in execution_data["adaptation_history"]:
            status = "✅" if event.success else "⚠️"
            print(f"{status} Étape {event.step_number}: {event.reason}")
            if event.adapted_to:
                print(f"   {event.original_service} → {event.adapted_to}")
            print(f"   Timestamp: {event.timestamp.strftime('%H:%M:%S')}")
            print()
    else:
        print("Aucune adaptation nécessaire - tous les services ont fonctionné parfaitement")
    
    print_section("Self-Configuration")
    
    total_params_configured = 0
    for step in intelligent_result.steps:
        configured = len(step.input_parameters)
        total_params_configured += configured
    
    print(f"{total_params_configured} paramètres auto-configurés au total")
    print("   Exemples de configuration automatique :")
    print("      • cabinClass = 'economy' (valeur par défaut)")
    print("      • directFlightsOnly = False (valeur par défaut)")
    print("      • children = 0 (valeur par défaut)")
    
    print_section("Self-Protection")
    
    total_retries = sum(r.retry_count for r in execution_data["execution_results"])
    fallbacks_used = sum(1 for r in execution_data["execution_results"] if r.used_fallback)
    
    print(f"Mécanismes de protection activés :")
    print(f"   • Tentatives de retry: {total_retries}")
    print(f"   • Fallbacks utilisés: {fallbacks_used}")
    print(f"   • Timeouts configurés: {executor.timeout_seconds}s par service")
    
    # =========================================================================
    # PARTIE 4 : COMPARAISON AVANT/APRÈS ENRICHISSEMENT
    # =========================================================================
    print_header("PARTIE 4 : IMPACT DE L'ENRICHISSEMENT", "=")
    
    print_section("Annotations Enrichies")
    
    print("Les annotations ont été mises à jour avec :")
    print("   1. Métriques de qualité réelles (temps de réponse observé)")
    print("   2. Taux de succès calculé depuis les exécutions")
    print("   3. Historique des compositions réussies/échouées")
    print("   4. Patterns d'utilisation des paramètres")
    
    print("\nAvantages pour les prochaines compositions :")
    print("   • Sélection de services basée sur des performances réelles")
    print("   • Priorisation des services les plus fiables")
    print("   • Anticipation des paramètres fréquemment utilisés")
    print("   • Apprentissage continu à chaque exécution")
    
    # =========================================================================
    # PARTIE 5 : COMPARAISON AVEC APPROCHE CLASSIQUE
    # =========================================================================
    print_header("PARTIE 5 : COMPARAISON RAPIDE AVEC APPROCHE CLASSIQUE", "=")
    
    print_section("Exécution Classique (pour comparaison)")
    
    classic_registry = ClassicServiceRegistry()
    classic_engine = ClassicCompositionEngine(classic_registry)
    
    classic_result = classic_engine.compose(
        goal="book_complete_travel",
        user_input=user_input
    )
    
    # Tableau comparatif
    print("\n" + "┌" + "─"*78 + "┐")
    print("│" + " "*20 + "COMPARAISON DES APPROCHES" + " "*33 + "│")
    print("├" + "─"*38 + "┬" + "─"*39 + "┤")
    print(f"│ {'FONCTIONNALITÉ':<36} │ {'CLASSIQUE vs ADAPTATIF':<37} │")
    print("├" + "─"*38 + "┼" + "─"*39 + "┤")
    
    # Ligne 1: Self-configuration
    print(f"│ {'Self-Configuration':<36} │ {'❌ Non    vs    ✅ Oui':<37} │")
    
    # Ligne 2: Self-adaptation
    print(f"│ {'Self-Adaptation':<36} │ {'❌ Non    vs    ✅ Oui':<37} │")
    
    # Ligne 3: Self-protection
    print(f"│ {'Self-Protection (Retry/Fallback)':<36} │ {'❌ Non    vs    ✅ Oui':<37} │")
    
    # Ligne 4: Enrichissement
    print(f"│ {'Enrichissement des Annotations':<36} │ {'❌ Non    vs    ✅ Oui':<37} │")
    
    # Ligne 5: Couverture
    classic_cov = sum(s.mapping_coverage for s in classic_result.steps) / len(classic_result.steps)
    intel_cov = intelligent_result.avg_mapping_coverage
    print(f"│ {'Couverture Paramètres':<36} │ {f'{classic_cov:.1%} vs {intel_cov:.1%}':<37} │")
    
    # Ligne 6: Adaptation runtime
    adaptations = len(execution_data["adaptation_history"])
    print(f"│ {'Adaptations Runtime':<36} │ {f'0        vs    {adaptations}':<37} │")
    
    print("└" + "─"*38 + "┴" + "─"*39 + "┘")
    
    # =========================================================================
    # CONCLUSION
    # =========================================================================
    print_header("CONCLUSION", "=")
    
    print("Ce système démontre un niveau avancé d'intelligence :\n")
    
    print("1.COMPOSITION INTELLIGENTE")
    print("   • Sélection multi-critères adaptative")
    print("   • Prise en compte du contexte utilisateur")
    print("   • Optimisation qualité/coût/contexte")
    
    print("\n2.EXÉCUTION ADAPTATIVE")
    print("   • Self-Configuration : Paramètres automatiques")
    print("   • Self-Adaptation : Basculement vers alternatives")
    print("   • Self-Protection : Retry, timeout, fallback")
    
    print("\n3.APPRENTISSAGE CONTINU")
    print("   • Enregistrement de chaque exécution")
    print("   • Enrichissement automatique des annotations")
    print("   • Amélioration des décisions futures")
    
    print("\n4.TRAÇABILITÉ COMPLÈTE")
    print("   • Historique des adaptations")
    print("   • Rapports d'exécution détaillés")
    print("   • Statistiques par service")
    
    print("\nIMPACT MESURABLE:")
    workflow_success = execution_data["workflow_success"]
    print(f"   • Workflow complété: {'OUI' if workflow_success else '❌ NON'}")
    print(f"   • Services enrichis: {len(services_used)}")
    print(f"   • Feedbacks enregistrés: {len(execution_data['execution_results'])}")
    print(f"   • Adaptations effectuées: {adaptations}")
    
    print("\nVALEUR AJOUTÉE:")
    print("   • Robustesse : Continue même si des services échouent")
    print("   • Intelligence : Apprend de chaque exécution")
    print("   • Autonomie : Minimal d'intervention manuelle")
    print("   • Traçabilité : Historique complet des décisions")
    
    # =========================================================================
    # FICHIERS GÉNÉRÉS
    # =========================================================================
    print_section("Fichiers Générés")
    
    print("\nRésultats de composition:")
    print(f"   • composition_system/results/{intelligent_result.workflow_id}_intelligent.json")
    
    print("\nExécution adaptative:")
    print(f"   • composition_system/results/execution_*.json")
    
    print("\nEnrichissement:")
    print(f"   • services/wsdl/annotated/feedback_history.json")
    print(f"   • services/wsdl/annotated/enrichment_report_*.json")
    print(f"   • services/wsdl/annotated/*_annotated.json (mis à jour)")
    
    print("\n" + "="*80)
    print(f"  Démonstration terminée - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDémonstration interrompue")
    except Exception as e:
        print(f"\n\nERREUR: {e}")
        import traceback
        traceback.print_exc()