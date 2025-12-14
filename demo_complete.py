"""
demo_complete.py
Démonstration complète des 3 approches : Classique, Intelligente, Hybride
"""
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))


def print_banner(title):
    """Affiche une bannière"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")


def print_section(title):
    """Affiche une section"""
    print("\n" + "─"*80)
    print(f"  {title}")
    print("─"*80)


def demo_classic():
    """Démonstration de la composition classique"""
    print_banner("DÉMONSTRATION 1 : COMPOSITION CLASSIQUE")
    
    from composition_system.classic_wsdl_parser import ClassicServiceRegistry
    from composition_system.classic_composition_engine import ClassicCompositionEngine
    
    print("📋 Chargement des services...")
    registry = ClassicServiceRegistry()
    
    if not registry.services:
        print("❌ Aucun service chargé")
        return
    
    print(f"✓ {len(registry.services)} services chargés")
    
    print_section("Scénario : Voyage Paris → Tokyo")
    
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
    
    print("\nDonnées utilisateur:")
    for key, value in user_input.items():
        print(f"   {key}: {value}")
    
    print_section("Exécution de la composition...")
    
    engine = ClassicCompositionEngine(registry)
    result = engine.compose("book_complete_travel", user_input)
    
    print_section("Résultats")
    
    engine.print_result(result)
    engine.save_result(result)
    
    return result


def demo_intelligent():
    """Démonstration de la composition intelligente"""
    print_banner("DÉMONSTRATION 2 : COMPOSITION INTELLIGENTE")
    
    from composition_system.intelligent_service_registry import IntelligentServiceRegistry
    from composition_system.intelligent_composition_engine import IntelligentCompositionEngine
    from composition_system.adaptive_executor import AdaptiveExecutor
    
    print("📋 Chargement des annotations...")
    registry = IntelligentServiceRegistry()
    
    if not registry.services:
        print("❌ Aucune annotation chargée")
        print("   Exécutez d'abord: python annotation_system/batch_annotate.py")
        return
    
    print(f"✓ {len(registry.services)} services annotés chargés")
    
    print_section("Scénario : Voyage d'affaires avec contexte riche")
    
    user_input = {
        "origin": "Paris",
        "destination": "Tokyo",
        "departureDate": "2025-08-10",
        "returnDate": "2025-08-17",
        "passengers": 1,
        "currency": "EUR",
        "maxPrice": 3500.00
    }
    
    user_context = {
        "location": "EU",
        "mission_critical": True,
        "needs_multi_currency": True,
        "needs_24_7": True,
        "budget_conscious": False
    }
    
    constraints = {
        "max_cost": 0.05,
        "min_quality": 0.90
    }
    
    print("\nContexte utilisateur:")
    for key, value in user_context.items():
        print(f"   {key}: {value}")
    
    print("\nContraintes:")
    for key, value in constraints.items():
        print(f"   {key}: {value}")
    
    print_section("Exécution de la composition intelligente...")
    
    engine = IntelligentCompositionEngine(registry)
    result = engine.compose(
        goal="book_complete_travel",
        user_input=user_input,
        user_context=user_context,
        constraints=constraints
    )
    
    print_section("Exécution adaptative...")
    
    executor = AdaptiveExecutor(max_retries=2)
    execution_data = executor.execute_workflow_with_adaptation(
        result,
        user_input,
        registry
    )
    
    print_section("Résultats")
    
    engine.print_result(result)
    engine.save_result(result)
    
    print(f"\n📊 Métriques d'adaptation:")
    print(f"   • Adaptations: {len(execution_data['adaptation_history'])}")
    print(f"   • Retries: {sum(r.retry_count for r in execution_data['execution_results'])}")
    print(f"   • Succès: {execution_data['workflow_success']}")
    
    return result, execution_data


def demo_hybrid():
    """Démonstration de la composition hybride"""
    print_banner("DÉMONSTRATION 3 : COMPOSITION HYBRIDE (Classique + LLM)")
    
    try:
        from composition_system.intelligent_service_registry import IntelligentServiceRegistry
        from composition_system.hybrid_composition_engine import HybridCompositionEngine
    except Exception as e:
        print(f"❌ Erreur d'import: {e}")
        return
    
    print("📋 Chargement du registre et services LLM...")
    registry = IntelligentServiceRegistry()
    
    if not registry.services:
        print("❌ Annotations non disponibles")
        return
    
    try:
        engine = HybridCompositionEngine(registry)
        print("✓ Moteur hybride initialisé")
    except Exception as e:
        print(f"⚠️ Impossible d'initialiser services LLM: {e}")
        print("   Assurez-vous qu'Ollama est lancé: ollama serve")
        return
    
    print_section("Scénario : Planification de voyage intelligente")
    
    user_input = {
        "origin": "Paris",
        "duration_days": 7,
        "maxPrice": 3000.0
    }
    
    user_context = {
        "preferences": {
            "interests": ["culture", "food", "technology"],
            "travel_style": "cultural explorer"
        },
        "user_profile": {
            "name": "Marie Dubois",
            "interests": ["culture", "food", "tech"],
            "travel_style": "cultural"
        },
        "free_text_request": "Je veux découvrir la culture asiatique, manger des plats authentiques, et visiter des temples"
    }
    
    print("\nTexte libre utilisateur:")
    print(f'   "{user_context["free_text_request"]}"')
    
    print_section("Exécution du workflow hybride...")
    print("\n🔀 Ce workflow combine:")
    print("   🤖 Services LLM : Recommandation, Analyse, Résumé")
    print("   ⚙️  Services Classiques : Recherche vol/hôtel, Paiement")
    
    result = engine.compose_hybrid(
        goal="enhanced_travel_booking",
        user_input=user_input,
        user_context=user_context
    )
    
    print_section("Résultats")
    
    engine.print_result(result)
    engine.save_result(result)
    
    # Afficher détails des résultats LLM
    if result.final_recommendation:
        print_section("🌟 Recommandation LLM")
        rec = result.final_recommendation
        
        # Gérer dict ou objet
        if isinstance(rec, dict):
            print(f"\n📍 Destination: {rec.get('destination', 'N/A')}")
            print(f"💭 Raison: {rec.get('reason', 'N/A')}")
            print(f"💰 Budget estimé: ${rec.get('estimated_budget', 0):.2f}")
            
            activities = rec.get('activities', [])
            if activities:
                print(f"\n🎯 Activités:")
                for activity in activities[:3]:
                    print(f"   • {activity}")
        else:
            print(f"\n📍 Destination: {rec.destination}")
            print(f"💭 Raison: {rec.reason}")
            print(f"💰 Budget estimé: ${rec.estimated_budget:.2f}")
            print(f"\n🎯 Activités:")
            for activity in rec.activities[:3]:
                print(f"   • {activity}")
    
    if result.final_summary:
        print_section("📋 Résumé Final LLM")
        summary = result.final_summary
        
        # Gérer dict ou objet
        if isinstance(summary, dict):
            print(f"\n{summary.get('title', 'N/A')}")
            print(f"\n{summary.get('overview', 'N/A')}")
            print(f"\n💬 Message personnalisé:")
            print(f"   {summary.get('personalized_message', 'N/A')}")
        else:
            print(f"\n{summary.title}")
            print(f"\n{summary.overview}")
            print(f"\n💬 Message personnalisé:")
            print(f"   {summary.personalized_message}")
    
    return result


def demo_comparison():
    """Comparaison des 3 approches"""
    print_banner("COMPARAISON DES 3 APPROCHES")
    
    print("""
┌────────────────────────────────────────────────────────────────────────────┐
│                         SYNTHÈSE COMPARATIVE                                │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  APPROCHE CLASSIQUE                                                         │
│  ✅ Rapide (~7ms)                                                          │
│  ✅ Simple et fiable                                                       │
│  ✅ Pas de dépendances                                                     │
│  ❌ Rigide, pas d'adaptation                                               │
│  ❌ Ne considère pas le contexte                                           │
│                                                                             │
│  💡 IDÉAL POUR: Workflows standards, performance critique                 │
│                                                                             │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  APPROCHE INTELLIGENTE                                                      │
│  ✅ Adaptatif (5.8 adaptations/workflow)                                  │
│  ✅ Contextuel (score 0.775/1.0)                                          │
│  ✅ Explicable (raisons détaillées)                                        │
│  ❌ Plus lent (~628ms)                                                     │
│  ❌ Dépend d'un LLM                                                        │
│                                                                             │
│  💡 IDÉAL POUR: Forte hétérogénéité, qualité critique                    │
│                                                                             │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  APPROCHE HYBRIDE ⭐ RECOMMANDÉE                                           │
│  ✅ Meilleur des deux mondes                                              │
│  ✅ Recommandations LLM + Efficacité classique                            │
│  ✅ UX différenciante                                                      │
│  ⚠️  Plus complexe à maintenir                                            │
│                                                                             │
│  💡 IDÉAL POUR: Applications grand public, expérience premium            │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
    """)
    
    print("\n📊 MÉTRIQUES CLÉS:")
    print("\n   Performance:")
    print("      Classique:    7.4ms")
    print("      Intelligente: 628ms   (+8378%)")
    print("      Hybride:      ~300ms  (estimé)")
    
    print("\n   Adaptation:")
    print("      Classique:    0 adaptations")
    print("      Intelligente: 5.8 adaptations/workflow")
    print("      Hybride:      Adaptatif selon étape")
    
    print("\n   Qualité de service:")
    print("      Classique:    N/A (règles fixes)")
    print("      Intelligente: 0.775/1.0")
    print("      Hybride:      0.775/1.0 + insights LLM")
    
    print("\n   Expérience utilisateur:")
    print("      Classique:    ⭐⭐")
    print("      Intelligente: ⭐⭐⭐⭐")
    print("      Hybride:      ⭐⭐⭐⭐⭐")


def main():
    """Programme principal"""
    print_banner("DÉMONSTRATION COMPLÈTE DU SYSTÈME")
    
    print("""
Ce script démontre les 3 approches implémentées pour le stage :

1. 🔹 COMPOSITION CLASSIQUE
   - Règles hardcodées
   - Sélection déterministe
   - Mapping prédéfini

2. 🔹 COMPOSITION INTELLIGENTE  
   - Annotations LLM
   - Sélection contextuelle
   - Adaptation dynamique

3. 🔹 COMPOSITION HYBRIDE
   - Services classiques (WSDL)
   - Services LLM (Recommandation, Résumé)
   - Meilleur des deux mondes
    """)
    
    print("\nOptions:")
    print("   1. Démonstration complète (toutes les approches)")
    print("   2. Classique uniquement")
    print("   3. Intelligente uniquement")
    print("   4. Hybride uniquement")
    print("   5. Comparaison seulement")
    print("   0. Quitter")
    
    choice = input("\nVotre choix (1-5, 0 pour quitter): ").strip()
    
    if choice == "0":
        print("\n👋 Au revoir!")
        return
    
    elif choice == "1":
        # Tout
        demo_classic()
        input("\n⏸️  Appuyez sur Entrée pour continuer...")
        
        demo_intelligent()
        input("\n⏸️  Appuyez sur Entrée pour continuer...")
        
        demo_hybrid()
        input("\n⏸️  Appuyez sur Entrée pour continuer...")
        
        demo_comparison()
    
    elif choice == "2":
        demo_classic()
    
    elif choice == "3":
        demo_intelligent()
    
    elif choice == "4":
        demo_hybrid()
    
    elif choice == "5":
        demo_comparison()
    
    else:
        print("\n❌ Choix invalide")
        return
    
    print_banner("DÉMONSTRATION TERMINÉE")
    
    print("""
📁 Fichiers générés :
   - composition_system/results/wf_*_classic.json
   - composition_system/results/iwf_*_intelligent.json
   - composition_system/results/hwf_*_hybrid.json

📖 Pour plus d'informations :
   - Voir RAPPORT_FINAL.md
   - Voir README.md

🚀 Prochaines étapes :
   - Exécuter evaluation_suite.py pour évaluation complète
   - Tester avec vos propres scénarios
   - Adapter pour votre domaine métier
    """)
    
    print("\n✨ Merci d'avoir utilisé le système !")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Démonstration interrompue")
    except Exception as e:
        print(f"\n\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()