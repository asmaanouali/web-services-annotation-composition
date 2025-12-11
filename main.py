"""
main_classic_composition.py
Démonstration complète du système de composition classique
Cas d'usage: Réservation de voyage complet (Paris → Tokyo)
"""
import sys
import os
from datetime import datetime
import json

# Ajouter le chemin racine
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from composition_system.classic_wsdl_parser import ClassicServiceRegistry
from composition_system.classic_composition_engine import ClassicCompositionEngine


def print_header(title: str):
    """Affiche un en-tête formaté"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")


def print_section(title: str):
    """Affiche une section"""
    print("\n" + "─"*80)
    print(f"  {title}")
    print("─"*80)


def main():
    """
    Démonstration complète du système de composition classique
    """
    
    print_header("SYSTÈME DE COMPOSITION CLASSIQUE DE SERVICES WEB")
    
    print("Description du système:")
    print("   • Parse les fichiers WSDL pour découvrir les services disponibles")
    print("   • Sélectionne automatiquement les meilleurs services selon des règles prédéfinies")
    print("   • Compose un workflow complet pour réserver un voyage")
    print("   • Mappe intelligemment les paramètres entre services hétérogènes")
    
    # =========================================================================
    # ÉTAPE 1 : Chargement des services
    # =========================================================================
    print_section("ÉTAPE 1: Chargement des Services Disponibles")
    
    print("Scanning du répertoire: services/wsdl/original/")
    registry = ClassicServiceRegistry()
    
    if not registry.services:
        print("\n ERREUR: Aucun service trouvé!")
        print("   Assurez-vous que les fichiers WSDL existent dans services/wsdl/original/")
        return
    
    print(f"\n {len(registry.services)} services chargés avec succès:\n")
    
    # Grouper par catégorie
    services_by_category = {}
    for service_name, service in registry.services.items():
        category = service.get_category()
        if category not in services_by_category:
            services_by_category[category] = []
        services_by_category[category].append(service_name)
    
    for category, services in sorted(services_by_category.items()):
        print(f"   {category.upper()}: {len(services)} service(s)")
        for service in services:
            print(f"      • {service}")
    
    # =========================================================================
    # ÉTAPE 2 : Définition du scénario utilisateur
    # =========================================================================
    print_section("ÉTAPE 2: Scénario Utilisateur")
    
    scenario = {
        "description": "Voyage d'affaires Paris → Tokyo",
        "user_profile": {
            "name": "Jean Dupont",
            "company": "TechCorp International",
            "budget": "3500 EUR",
            "preferences": "Vol direct préféré, hôtel 4-5 étoiles près du centre"
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
    
    print(f"\nUtilisateur: {scenario['user_profile']['name']}")
    print(f"   Entreprise: {scenario['user_profile']['company']}")
    print(f"   Budget maximum: {scenario['user_profile']['budget']}")
    
    print(f"\nDétails du voyage:")
    print(f"   • Trajet: {scenario['trip_details']['origin']} → {scenario['trip_details']['destination']}")
    print(f"   • Départ: {scenario['trip_details']['departureDate']}")
    print(f"   • Retour: {scenario['trip_details']['returnDate']}")
    print(f"   • Voyageurs: {scenario['trip_details']['passengers']} personne(s)")
    
    # =========================================================================
    # ÉTAPE 3 : Initialisation du moteur de composition
    # =========================================================================
    print_section("ÉTAPE 3: Initialisation du Moteur de Composition")
    
    engine = ClassicCompositionEngine(registry)
    
    print("Configuration du moteur:")
    print("   • Mode: Composition classique (règles prédéfinies)")
    print("   • Sélection: Basée sur priorités hardcodées")
    print("   • Mapping: Correspondance exacte + règles de mapping")
    print("   • Workflow: Template prédéfini 'book_complete_travel'")
    
    print("\nWorkflow 'book_complete_travel':")
    print("   1.  Recherche de vols")
    print("   2.  Recherche d'hôtels")
    print("   3.  Traitement du paiement")
    
    # =========================================================================
    # ÉTAPE 4 : Exécution de la composition
    # =========================================================================
    print_section("ÉTAPE 4: Exécution de la Composition")
    
    print("Lancement de la composition...\n")
    
    # Préparer les données d'entrée
    user_input = {
        "origin": scenario['trip_details']['origin'],
        "destination": scenario['trip_details']['destination'],
        "departureDate": scenario['trip_details']['departureDate'],
        "returnDate": scenario['trip_details']['returnDate'],
        "passengers": scenario['trip_details']['passengers'],
        "currency": scenario['trip_details']['currency'],
        "maxPrice": 3500.00,
        # Paramètres additionnels pour l'hôtel
        "checkInDate": scenario['trip_details']['departureDate'],
        "checkOutDate": scenario['trip_details']['returnDate'],
        "guests": scenario['trip_details']['passengers'],
        "rooms": 1,
        "minStars": 4
    }
    
    # Exécuter la composition
    result = engine.compose(
        goal="book_complete_travel",
        user_input=user_input
    )
    
    # =========================================================================
    # ÉTAPE 5 : Affichage des résultats
    # =========================================================================
    print_section("ÉTAPE 5: Résultats de la Composition")
    
    engine.print_result(result)
    
    # =========================================================================
    # ÉTAPE 6 : Analyse et statistiques
    # =========================================================================
    print_section("ÉTAPE 6: Analyse des Résultats")
    
    if result.success:
        print("STATUT: Composition réussie\n")
        
        # Statistiques globales
        print("STATISTIQUES GLOBALES:")
        print(f"   • Nombre d'étapes: {len(result.steps)}/{result.total_steps}")
        print(f"   • Services distincts utilisés: {len(set(s.selected_service for s in result.steps))}")
        
        # Couverture des mappings
        avg_coverage = sum(s.mapping_coverage for s in result.steps) / len(result.steps) if result.steps else 0
        print(f"   • Couverture moyenne des paramètres: {avg_coverage*100:.1f}%")
        
        # Paramètres manquants
        total_missing = sum(len(s.missing_parameters) for s in result.steps)
        print(f"   • Paramètres manquants totaux: {total_missing}")
        
        # Analyse par étape
        print("\nANALYSE PAR ÉTAPE:")
        for step in result.steps:
            coverage_status = "✅" if step.mapping_coverage >= 0.7 else "⚠️" if step.mapping_coverage >= 0.5 else "❌"
            print(f"\n   {coverage_status} Étape {step.step_number} - {step.category.upper()}")
            print(f"      Service: {step.selected_service}")
            print(f"      Couverture: {step.mapping_coverage*100:.0f}% ({len(step.input_parameters)}/{len(step.input_parameters)+len(step.missing_parameters)} paramètres)")
            
            if step.missing_parameters:
                print(f"      Manquants: {', '.join(step.missing_parameters)}")
            
            if step.alternatives_rejected:
                print(f"      Alternatives: {', '.join(step.alternatives_rejected)}")
        
        # Points forts / Points faibles
        print("\nÉVALUATION:")
        print("\n   POINTS FORTS:")
        print("      • Workflow complet généré automatiquement")
        print("      • Sélection transparente avec justifications")
        print("      • Mapping automatique des paramètres compatibles")
        print("      • Traçabilité complète des décisions")
        
        print("\n   LIMITATIONS:")
        print("      • Règles de sélection hardcodées (pas d'adaptation contextuelle)")
        print("      • Mapping limité aux correspondances exactes prédéfinies")
        if avg_coverage < 0.8:
            print(f"      • Couverture des paramètres limitée ({avg_coverage*100:.0f}%)")
        if total_missing > 0:
            print(f"      • {total_missing} paramètre(s) nécessitent une intervention manuelle")
        
    else:
        print("STATUT: Composition échouée\n")
        print("ERREURS DÉTECTÉES:")
        for i, error in enumerate(result.errors, 1):
            print(f"   {i}. {error}")
    
    # =========================================================================
    # ÉTAPE 7 : Sauvegarde
    # =========================================================================
    print_section("ÉTAPE 7: Sauvegarde des Résultats")
    
    output_dir = "composition_system/results"
    engine.save_result(result, output_dir)
    
    print(f"\nRésultat sauvegardé dans: {output_dir}/")
    print(f"   Fichier: {result.workflow_id}_classic.json")
    
    # =========================================================================
    # CONCLUSION
    # =========================================================================
    print_header("CONCLUSION")
    
    print("Ce système de composition classique démontre:")
    print("\n1. DÉCOUVERTE AUTOMATIQUE:")
    print("   • Parsing des WSDL pour identifier les services disponibles")
    print("   • Classification automatique par catégorie (flight, hotel, payment)")
    
    print("\n2. SÉLECTION DÉTERMINISTE:")
    print("   • Règles de priorité prédéfinies pour choisir entre services concurrents")
    print("   • Justification explicite de chaque choix")
    
    print("\n3. COMPOSITION SÉQUENTIELLE:")
    print("   • Workflow prédéfini avec étapes fixes")
    print("   • Propagation des données entre services")
    
    print("\n4. MAPPING DE PARAMÈTRES:")
    print("   • Résolution des incompatibilités de nommage")
    print("   • Identification des paramètres manquants")
    
    
    print("\n" + "="*80)
    print(f"  Démonstration terminée - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDémonstration interrompue par l'utilisateur")
    except Exception as e:
        print(f"\n\nERREUR FATALE: {e}")
        import traceback
        traceback.print_exc()