"""
Script de test pour démontrer le parsing WSDL, l'annotation LLM et l'enrichissement
"""
import sys
import os

# Ajouter le dossier parent au path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.wsdl_parser import WSDLParser
from services.llm_annotator import LLMAnnotator
from services.wsdl_enricher import WSDLEnricher
from config import Config
import json

def test_wsdl_parsing():
    """Test du parsing du fichier WSDL exemple"""
    print("=" * 70)
    print("ÉTAPE 1 : PARSING DU FICHIER WSDL")
    print("=" * 70)
    
    wsdl_path = os.path.join(Config.INPUT_DIR, "exemple_service.wsdl")
    print(f"\n📁 Fichier WSDL : {wsdl_path}")
    
    parser = WSDLParser(wsdl_path)
    print("\n🔍 Parsing en cours...")
    service_info = parser.parse()
    
    print("\n✅ Parsing réussi !\n")
    print(f"🏷️  Nom du service : {service_info['service_name']}")
    print(f"🌐 Namespace : {service_info['target_namespace']}")
    print(f"📍 Endpoint : {service_info['endpoint']}")
    print(f"⚙️  Opérations : {len(service_info['operations'])}")
    print(f"📦 Types : {len(service_info['types'])}")
    
    return service_info

def test_llm_annotation(service_info):
    """Test de la génération d'annotations via LLM"""
    print("\n" + "=" * 70)
    print("ÉTAPE 2 : GÉNÉRATION DES ANNOTATIONS SÉMANTIQUES")
    print("=" * 70)
    
    annotator = LLMAnnotator()
    
    # Vérifier Ollama
    print("\n🔍 Vérification d'Ollama...")
    status = annotator.check_ollama_status()
    
    if status["status"] != "ok":
        print(f"❌ Erreur : {status['message']}")
        print("\n💡 Assure-toi qu'Ollama est lancé !")
        print("   Sur Windows, cherche 'Ollama' dans la barre des tâches")
        print("   Ou lance : ollama serve")
        return None
    
    print(f"✅ Ollama OK - Modèle : {status['current_model']}")
    print(f"📋 Modèles disponibles : {', '.join(status['available_models'])}")
    
    # Générer les annotations
    print("\n🤖 Génération des annotations via LLM...")
    print("   (Cela peut prendre 30-90 secondes...)")
    
    annotations = annotator.generate_annotations(service_info)
    
    print("\n✅ Annotations générées avec succès !\n")
    
    # Afficher les annotations
    print(f"🎯 Domaine : {annotations.get('domain', 'N/A')}")
    print(f"📝 Description : {annotations.get('description', 'N/A')}")
    print(f"🔑 Mots-clés : {', '.join(annotations.get('keywords', []))}")
    
    if 'use_cases' in annotations:
        print(f"\n💡 Cas d'usage :")
        for use_case in annotations['use_cases']:
            print(f"   • {use_case}")
    
    if 'operations' in annotations:
        print(f"\n⚙️  Annotations des opérations :")
        for op_ann in annotations['operations']:
            print(f"\n   📌 {op_ann.get('name', 'N/A')}")
            print(f"      Description : {op_ann.get('semantic_description', 'N/A')}")
            print(f"      Input : {op_ann.get('input_semantic', 'N/A')}")
            print(f"      Output : {op_ann.get('output_semantic', 'N/A')}")
    
    return annotations

def test_wsdl_enrichment(service_info, annotations):
    """Test de l'enrichissement du WSDL"""
    print("\n" + "=" * 70)
    print("ÉTAPE 3 : ENRICHISSEMENT DU WSDL")
    print("=" * 70)
    
    wsdl_path = os.path.join(Config.INPUT_DIR, "exemple_service.wsdl")
    output_path = os.path.join(Config.OUTPUT_DIR, "exemple_service_enriched.wsdl")
    
    print(f"\n📄 WSDL original : {wsdl_path}")
    print(f"📝 WSDL enrichi : {output_path}")
    
    # Créer l'enrichisseur
    enricher = WSDLEnricher(wsdl_path)
    
    print("\n🔧 Enrichissement en cours...")
    
    # Enrichir et sauvegarder
    enricher.enrich(annotations, output_path)
    
    print("\n✅ Enrichissement terminé !")
    print(f"\n📊 Statistiques :")
    print(f"   • Annotations globales : Domaine, Description, Mots-clés")
    print(f"   • Opérations annotées : {len(annotations.get('operations', []))}")
    print(f"   • Documentation enrichie : ✓")
    
    return output_path

def save_results(service_info, annotations, enriched_wsdl_path):
    """Sauvegarde les résultats"""
    print("\n" + "=" * 70)
    print("SAUVEGARDE DES RÉSULTATS")
    print("=" * 70)
    
    # Sauvegarder les infos du service
    service_file = os.path.join(Config.OUTPUT_DIR, "parsed_service_info.json")
    with open(service_file, 'w', encoding='utf-8') as f:
        json.dump(service_info, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Service info → {service_file}")
    
    # Sauvegarder les annotations
    if annotations:
        annotations_file = os.path.join(Config.OUTPUT_DIR, "generated_annotations.json")
        with open(annotations_file, 'w', encoding='utf-8') as f:
            json.dump(annotations, f, indent=2, ensure_ascii=False)
        print(f"💾 Annotations → {annotations_file}")
    
    # Sauvegarder le résultat complet
    complete_result = {
        "service_info": service_info,
        "annotations": annotations,
        "enriched_wsdl_path": enriched_wsdl_path
    }
    
    complete_file = os.path.join(Config.OUTPUT_DIR, "complete_analysis.json")
    with open(complete_file, 'w', encoding='utf-8') as f:
        json.dump(complete_result, f, indent=2, ensure_ascii=False)
    print(f"💾 Analyse complète → {complete_file}")
    
    print(f"\n📁 Tous les fichiers sont dans : {Config.OUTPUT_DIR}")

def display_summary(enriched_wsdl_path):
    """Affiche un résumé final"""
    print("\n" + "=" * 70)
    print("📋 RÉSUMÉ DE LA DÉMO")
    print("=" * 70)
    
    print("\n✅ Pipeline complet exécuté avec succès :")
    print("   1. ✓ Parsing du WSDL original")
    print("   2. ✓ Génération d'annotations sémantiques via LLM")
    print("   3. ✓ Enrichissement du WSDL avec les annotations")
    
    print(f"\n📂 Fichiers générés :")
    print(f"   • WSDL enrichi : {os.path.basename(enriched_wsdl_path)}")
    print(f"   • Annotations JSON : generated_annotations.json")
    print(f"   • Info du service : parsed_service_info.json")
    print(f"   • Analyse complète : complete_analysis.json")
    
    print("\n🎯 Prochaines étapes possibles :")
    print("   • Comparer le WSDL original vs enrichi")
    print("   • Utiliser les annotations pour la composition de services")
    print("   • Intégrer dans un registre de services UDDI")

def main():
    """Fonction principale"""
    print("\n" + "🚀" * 35)
    print("   DEMO : ANNOTATION SÉMANTIQUE DE SERVICES SOAP")
    print("🚀" * 35 + "\n")
    
    try:
        # Étape 1 : Parser le WSDL
        service_info = test_wsdl_parsing()
        
        # Étape 2 : Générer les annotations
        annotations = test_llm_annotation(service_info)
        
        if annotations is None:
            print("\n⚠️  Impossible de générer les annotations (Ollama non accessible)")
            print("   La démo s'arrête ici.")
            return
        
        # Étape 3 : Enrichir le WSDL
        enriched_wsdl_path = test_wsdl_enrichment(service_info, annotations)
        
        # Sauvegarder les résultats
        save_results(service_info, annotations, enriched_wsdl_path)
        
        # Afficher le résumé
        display_summary(enriched_wsdl_path)
        
        print("\n" + "=" * 70)
        print("✅ DEMO TERMINÉE AVEC SUCCÈS")
        print("=" * 70 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERREUR : {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()