"""
main_comparison.py
Démonstration complète et comparaison des deux approches :
- Solution A : Composition Classique (règles hardcodées)
- Solution B : Composition Intelligente (annotations LLM)
"""
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Solution A - Classique
from composition_system.classic_wsdl_parser import ClassicServiceRegistry
from composition_system.classic_composition_engine import ClassicCompositionEngine

# Solution B - Intelligente
from composition_system.intelligent_service_registry import IntelligentServiceRegistry
from composition_system.intelligent_composition_engine import IntelligentCompositionEngine


def print_header(title: str, char: str = "="):
    """Affiche un en-tête"""
    print("\n" + char*80)
    print(f"  {title}")
    print(char*80 + "\n")


def print_section(title: str):
    """Affiche une section"""
    print("\n" + "─"*80)
    print(f"  {title}")
    print("─"*80)


def main():
    """Démonstration complète avec comparaison"""
    
    print_header("SYSTÈME DE COMPOSITION DE SERVICES WEB - COMPARAISON COMPLÈTE")
    
    print("Ce programme compare deux approches de composition de services :")
    print("   • Solution A : Composition CLASSIQUE (règles prédéfinies)")
    print("   • Solution B : Composition INTELLIGENTE (annotations LLM)")
    
    # =========================================================================
    # SCÉNARIO COMMUN
    # =========================================================================
    print_section("SCÉNARIO DE TEST")
    
    scenario = {
        "description": "Voyage d'affaires urgent Paris → Tokyo",
        "user_profile": {
            "name": "Jean Dupont",
            "company": "TechCorp International",
            "role": "Business Traveler",
            "budget": "3500 EUR",
            "priority": "Qualité de service > Prix"
        },
        "trip_details": {
            "origin": "Paris",
            "destination": "Tokyo",
            "departureDate": "2025-08-10",
            "returnDate": "2025-08-17",
            "passengers": 1,
            "currency": "EUR"
        }
    }
    
    print(f"\nProfil utilisateur:")
    print(f"   • Nom: {scenario['user_profile']['name']}")
    print(f"   • Entreprise: {scenario['user_profile']['company']}")
    print(f"   • Type: {scenario['user_profile']['role']}")
    print(f"   • Budget: {scenario['user_profile']['budget']}")
    print(f"   • Priorité: {scenario['user_profile']['priority']}")
    
    print(f"\nDétails du voyage:")
    print(f"   • {scenario['trip_details']['origin']} → {scenario['trip_details']['destination']}")
    print(f"   • Départ: {scenario['trip_details']['departureDate']}")
    print(f"   • Retour: {scenario['trip_details']['returnDate']}")
    print(f"   • Voyageurs: {scenario['trip_details']['passengers']}")
    
    # Préparer les données communes
    user_input = {
        "origin": scenario['trip_details']['origin'],
        "destination": scenario['trip_details']['destination'],
        "departureDate": scenario['trip_details']['departureDate'],
        "returnDate": scenario['trip_details']['returnDate'],
        "passengers": scenario['trip_details']['passengers'],
        "currency": scenario['trip_details']['currency'],
        "maxPrice": 3500.00,
        "checkInDate": scenario['trip_details']['departureDate'],
        "checkOutDate": scenario['trip_details']['returnDate'],
        "guests": scenario['trip_details']['passengers'],
        "rooms": 1,
        "minStars": 4
    }
    
    # =========================================================================
    # SOLUTION A : COMPOSITION CLASSIQUE
    # =========================================================================
    print_header("SOLUTION A : COMPOSITION CLASSIQUE", "=")
    
    print("Chargement du registre classique...")
    classic_registry = ClassicServiceRegistry()
    
    if not classic_registry.services:
        print("Erreur : Aucun service WSDL trouvé")
        return
    
    print(f"{len(classic_registry.services)} services chargés depuis WSDL")
    
    print("\nInitialisation du moteur classique...")
    classic_engine = ClassicCompositionEngine(classic_registry)
    
    print("   • Mode: Règles hardcodées")
    print("   • Sélection: Priorité fixe (Amadeus > Skyscanner)")
    print("   • Mapping: Dictionnaire prédéfini")
    
    print("\nExécution de la composition classique...")
    classic_result = classic_engine.compose(
        goal="book_complete_travel",
        user_input=user_input
    )
    
    # Afficher résultat abrégé
    print("\n" + "─"*80)
    print("RÉSULTAT SOLUTION A")
    print("─"*80)
    
    if classic_result.success:
        print(f"Statut: Composition réussie")
        print(f"Étapes: {len(classic_result.steps)}/{classic_result.total_steps}")
        
        avg_coverage = sum(s.mapping_coverage for s in classic_result.steps) / len(classic_result.steps)
        total_missing = sum(len(s.missing_parameters) for s in classic_result.steps)
        
        print(f"Couverture moyenne: {avg_coverage*100:.1f}%")
        print(f"Paramètres manquants: {total_missing}")
        
        print(f"\nServices sélectionnés:")
        for step in classic_result.steps:
            print(f"   {step.step_number}. {step.selected_service}")
            print(f"      Raison: {step.selection_reason}")
    else:
        print(f"Statut: Échec")
    
    # =========================================================================
    # SOLUTION B : COMPOSITION INTELLIGENTE
    # =========================================================================
    print_header("SOLUTION B : COMPOSITION INTELLIGENTE", "=")
    
    print("Chargement du registre intelligent...")
    intelligent_registry = IntelligentServiceRegistry()
    
    if not intelligent_registry.services:
        print("Erreur : Aucune annotation trouvée")
        print("   Exécutez d'abord: python annotation_system/batch_annotate.py")
        return
    
    print(f"{len(intelligent_registry.services)} services chargés avec annotations LLM")
    
    print("\nInitialisation du moteur intelligent...")
    intelligent_engine = IntelligentCompositionEngine(intelligent_registry)
    
    print("   • Mode: Sélection basée sur annotations")
    print("   • Sélection: Multi-critères adaptatif")
    print("   • Mapping: Sémantique + interaction")
    
    # Contexte enrichi pour solution B
    user_context = {
        "location": "EU",
        "mission_critical": True,  # Voyage d'affaires urgent
        "needs_multi_currency": True,
        "needs_24_7": True,
        "budget_conscious": False  # Priorité qualité
    }
    
    constraints = {
        "max_cost": 0.05,
        "min_quality": 0.90
    }
    
    print("\nContexte utilisateur enrichi:")
    for key, value in user_context.items():
        print(f"   • {key}: {value}")
    
    print("\nExécution de la composition intelligente...")
    intelligent_result = intelligent_engine.compose(
        goal="book_complete_travel",
        user_input=user_input,
        user_context=user_context,
        constraints=constraints
    )
    
    # Afficher résultat abrégé
    print("\n" + "─"*80)
    print("RÉSULTAT SOLUTION B")
    print("─"*80)
    
    if intelligent_result.success:
        print(f"Statut: Composition réussie")
        print(f"Étapes: {len(intelligent_result.steps)}/{intelligent_result.total_steps}")
        print(f"Score moyen services: {intelligent_result.avg_service_score:.3f}")
        print(f"Couverture moyenne: {intelligent_result.avg_mapping_coverage*100:.1f}%")
        print(f"Paramètres manquants: {intelligent_result.total_missing_params}")
    
        print(f"\nServices sélectionnés:")
        for step in intelligent_result.steps:
            print(f"   {step.step_number}. {step.selected_service}")
            print(f"      Score: {step.service_score.total_score:.3f}")
            print(f"      Raison principale: {step.service_score.reasons[0]}")
    else:
        print(f"Statut: Échec")
    
    # =========================================================================
    # COMPARAISON DÉTAILLÉE
    # =========================================================================
    print_header("COMPARAISON DÉTAILLÉE DES DEUX APPROCHES")
    
    # Tableau comparatif
    print("\n" + "="*80)
    print(f"{'CRITÈRE':<30} | {'SOLUTION A (Classique)':<20} | {'SOLUTION B (Intelligente)':<20}")
    print("="*80)
    
    # Succès
    classic_status = "Succès" if classic_result.success else "Échec"
    intel_status = "Succès" if intelligent_result.success else "Échec"
    print(f"{'Statut':<30} | {classic_status:<20} | {intel_status:<20}")
    
    # Étapes
    classic_steps = f"{len(classic_result.steps)}/{classic_result.total_steps}"
    intel_steps = f"{len(intelligent_result.steps)}/{intelligent_result.total_steps}"
    print(f"{'Étapes complétées':<30} | {classic_steps:<20} | {intel_steps:<20}")
    
    # Couverture
    if classic_result.steps:
        classic_cov = sum(s.mapping_coverage for s in classic_result.steps) / len(classic_result.steps)
        classic_cov_str = f"{classic_cov*100:.1f}%"
    else:
        classic_cov_str = "N/A"
    
    intel_cov_str = f"{intelligent_result.avg_mapping_coverage*100:.1f}%"
    print(f"{'Couverture paramètres':<30} | {classic_cov_str:<20} | {intel_cov_str:<20}")
    
    # Paramètres manquants
    if classic_result.steps:
        classic_missing = sum(len(s.missing_parameters) for s in classic_result.steps)
    else:
        classic_missing = 0
    print(f"{'Paramètres manquants':<30} | {classic_missing:<20} | {intelligent_result.total_missing_params:<20}")
    
    # Score qualité (seulement pour B)
    print(f"{'Score qualité moyen':<30} | {'N/A':<20} | {intelligent_result.avg_service_score:.3f:<20}")
    
    print("="*80)
    
    # =========================================================================
    # ANALYSE PAR ÉTAPE
    # =========================================================================
    print_section("ANALYSE PAR ÉTAPE")
    
    for i in range(min(len(classic_result.steps), len(intelligent_result.steps))):
        classic_step = classic_result.steps[i]
        intel_step = intelligent_result.steps[i]
        
        print(f"\n{'─'*80}")
        print(f"ÉTAPE {i+1}: {classic_step.category.upper()}")
        print(f"{'─'*80}")
        
        print(f"\nSolution A (Classique):")
        print(f"   Service: {classic_step.selected_service}")
        print(f"   Raison: {classic_step.selection_reason}")
        print(f"   Coverage: {classic_step.mapping_coverage*100:.0f}%")
        print(f"   Manquants: {len(classic_step.missing_parameters)}")
        
        print(f"\nSolution B (Intelligente):")
        print(f"   Service: {intel_step.selected_service}")
        print(f"   Score: {intel_step.service_score.total_score:.3f}")
        print(f"   Raisons: {', '.join(intel_step.service_score.reasons[:2])}")
        print(f"   Coverage: {intel_step.mapping_coverage*100:.0f}%")
        print(f"   Manquants: {len(intel_step.missing_parameters)}")
        
        # Comparaison
        if classic_step.selected_service == intel_step.selected_service:
            print(f"\n   Les deux solutions ont sélectionné le même service")
        else:
            print(f"\n   Services différents sélectionnés")
            if intel_step.alternatives_scores:
                for alt in intel_step.alternatives_scores:
                    if alt.service_name == classic_step.selected_service:
                        print(f"      Le choix classique avait un score de: {alt.total_score:.3f}")
                        print(f"      Différence: {intel_step.service_score.total_score - alt.total_score:.3f}")
    
    # =========================================================================
    # POINTS FORTS ET LIMITATIONS
    # =========================================================================
    print_header("ÉVALUATION COMPARATIVE")
    
    print("POINTS FORTS - Solution A (Classique):")
    print("   • Transparence totale des règles")
    print("   • Déterminisme complet (même entrée = même sortie)")
    print("   • Simplicité d'implémentation")
    print("   • Aucune dépendance externe (pas de LLM)")
    print("   • Facile à déboguer")
    
    print("\nLIMITATIONS - Solution A (Classique):")
    print("   • Rigidité : ne s'adapte pas au contexte")
    print(f"   • Couverture limitée : {classic_cov_str}")
    print(f"   • Paramètres manquants : {classic_missing}")
    print("   • Pas d'optimisation qualité/coût")
    print("   • Maintenance : toute modification = code")
    
    print("\nPOINTS FORTS - Solution B (Intelligente):")
    print("   • Adaptation contextuelle (budget, qualité, etc.)")
    print(f"   • Meilleure couverture : {intel_cov_str}")
    print(f"   • Sélection optimisée (score: {intelligent_result.avg_service_score:.3f})")
    print("   • Justifications riches et détaillées")
    print("   • Considère QoS, coûts, compliance")
    
    print("\nLIMITATIONS - Solution B (Intelligente):")
    print("   • Dépendance aux annotations LLM")
    print("   • Moins déterministe (poids adaptatifs)")
    print("   • Complexité accrue")
    print("   • Nécessite annotations à jour")
    
    # =========================================================================
    # GAINS MESURABLES
    # =========================================================================
    print_header("GAINS MESURABLES")
    
    if classic_result.steps and intelligent_result.steps:
        # Amélioration couverture
        if classic_cov_str != "N/A":
            classic_cov_val = float(classic_cov_str.rstrip('%'))
            intel_cov_val = float(intel_cov_str.rstrip('%'))
            improvement_cov = intel_cov_val - classic_cov_val
            
            print(f"\nmélioration de la couverture:")
            print(f"   Classique: {classic_cov_str}")
            print(f"   Intelligente: {intel_cov_str}")
            if improvement_cov > 0:
                print(f"   Gain: +{improvement_cov:.1f}%")
            else:
                print(f"   Différence: {improvement_cov:.1f}%")
        
        # Réduction paramètres manquants
        reduction = classic_missing - intelligent_result.total_missing_params
        print(f"\nRéduction des paramètres manquants:")
        print(f"   Classique: {classic_missing}")
        print(f"   Intelligente: {intelligent_result.total_missing_params}")
        if reduction > 0:
            print(f"   Réduction: -{reduction} paramètres")
            print(f"   Taux: {(reduction/classic_missing*100):.1f}% de moins")
        else:
            print(f"   Différence: {reduction} paramètres")
    
    # =========================================================================
    # CONCLUSION
    # =========================================================================
    print_header("CONCLUSION")
    
    print("Ce projet démontre l'apport des annotations LLM dans la composition de services :\n")
    
    print("1. ANNOTATION AUTOMATIQUE:")
    print("   • Le LLM enrichit les WSDL avec des métadonnées sémantiques")
    print("   • 4 types d'annotations : Fonctionnel, Interaction, Contexte, Politique")
    print("   • Information exploitable pour la composition")
    
    print("\n2. COMPOSITION CLASSIQUE (Baseline):")
    print("   • Approche traditionnelle avec règles hardcodées")
    print("   • Déterministe et simple mais limitée")
    print(f"   • Couverture: {classic_cov_str}, Manquants: {classic_missing}")
    
    print("\n3. COMPOSITION INTELLIGENTE (LLM-Enhanced):")
    print("   • Utilise les annotations pour décisions contextuelles")
    print("   • Sélection multi-critères adaptative")
    print(f"   • Couverture: {intel_cov_str}, Manquants: {intelligent_result.total_missing_params}")
    
    print("\nIMPACT:")
    if classic_result.steps and intelligent_result.steps:
        if intelligent_result.avg_mapping_coverage > (classic_cov if classic_cov_str != "N/A" else 0):
            print("   L'approche intelligente améliore significativement la composition")
            print("   Moins d'intervention manuelle nécessaire")
            print("   Meilleure adaptation aux besoins utilisateur")
    
    print("\nPROCHAINES ÉTAPES:")
    print("   • Évaluation sur des scénarios plus complexes")
    print("   • Mesure de performance (temps d'exécution)")
    print("   • Test avec différents contextes utilisateur")
    print("   • Analyse de la qualité des décisions")
    
    # =========================================================================
    # SAUVEGARDE
    # =========================================================================
    print_section("SAUVEGARDE DES RÉSULTATS")
    
    classic_engine.save_result(classic_result)
    intelligent_engine.save_result(intelligent_result)
    
    print("\nRésultats sauvegardés dans: composition_system/results/")
    print(f"   • {classic_result.workflow_id}_classic.json")
    print(f"   • {intelligent_result.workflow_id}_intelligent.json")
    
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