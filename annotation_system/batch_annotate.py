"""
annotation_system/batch_annotate.py
Script pour annoter tous les services WSDL en batch
"""
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from annotation_system.annotation_generator import AnnotationGenerator


def annotate_all_services(wsdl_dir: str = "services/wsdl/original",
                          output_dir: str = "services/wsdl/annotated",
                          ollama_model: str = "llama3.2:3b"):
    """
    Annote tous les services WSDL d'un répertoire
    
    Args:
        wsdl_dir: Répertoire contenant les fichiers WSDL
        output_dir: Répertoire de sortie pour les annotations
        ollama_model: Modèle Ollama à utiliser
    """
    print("="*80)
    print("ANNOTATION BATCH DE TOUS LES SERVICES")
    print("="*80)
    
    # Vérifier que le répertoire existe
    if not os.path.exists(wsdl_dir):
        print(f"Répertoire non trouvé: {wsdl_dir}")
        return
    
    # Créer le répertoire de sortie
    os.makedirs(output_dir, exist_ok=True)
    
    # Lister tous les fichiers WSDL
    wsdl_files = [f for f in os.listdir(wsdl_dir) if f.endswith('.wsdl')]
    
    if not wsdl_files:
        print(f"Aucun fichier WSDL trouvé dans {wsdl_dir}")
        return
    
    print(f"\n{len(wsdl_files)} services à annoter:")
    for i, filename in enumerate(wsdl_files, 1):
        print(f"   {i}. {filename}")
    
    # Créer le générateur
    try:
        generator = AnnotationGenerator(ollama_model=ollama_model)
        print(f"\nGénérateur initialisé (modèle: {ollama_model})")
    except ConnectionError as e:
        print(f"\n{e}")
        print("Lancez Ollama avec: ollama serve")
        return
    
    # Annoter chaque service
    results = {
        "success": [],
        "failed": []
    }
    
    for i, filename in enumerate(wsdl_files, 1):
        wsdl_path = os.path.join(wsdl_dir, filename)
        
        print(f"\n{'='*80}")
        print(f"[{i}/{len(wsdl_files)}] Traitement de: {filename}")
        print(f"{'='*80}")
        
        try:
            # Générer l'annotation
            annotation = generator.generate_annotation(wsdl_path)
            
            if annotation:
                # Sauvegarder
                output_filename = filename.replace('.wsdl', '_annotated.json')
                output_path = os.path.join(output_dir, output_filename)
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(annotation.to_dict(), f, indent=2, ensure_ascii=False)
                
                results["success"].append({
                    "service": annotation.service_name,
                    "file": output_filename,
                    "category": annotation.functional.service_category.value,
                    "capabilities": len(annotation.functional.capabilities)
                })
                
                print(f"\n[{i}/{len(wsdl_files)}] {filename} → annoté avec succès!")
            else:
                results["failed"].append(filename)
                print(f"\n[{i}/{len(wsdl_files)}] Échec pour {filename}")
                
        except Exception as e:
            results["failed"].append(filename)
            print(f"\n[{i}/{len(wsdl_files)}] Erreur pour {filename}: {e}")
    
    # Rapport final
    print("\n" + "="*80)
    print("RAPPORT FINAL")
    print("="*80)
    
    print(f"\nServices annotés avec succès: {len(results['success'])}/{len(wsdl_files)}")
    for item in results["success"]:
        print(f"   • {item['service']}")
        print(f"     - Catégorie: {item['category']}")
        print(f"     - Capacités: {item['capabilities']}")
        print(f"     - Fichier: {item['file']}")
    
    if results["failed"]:
        print(f"\nServices en échec: {len(results['failed'])}")
        for filename in results["failed"]:
            print(f"   • {filename}")
    
    # Sauvegarder le rapport
    report_path = os.path.join(output_dir, "annotation_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\nRapport sauvegardé: {report_path}")
    print(f"\nAnnotation terminée!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Annoter tous les services WSDL")
    parser.add_argument(
        "--model",
        type=str,
        default="llama3.2:3b",
        help="Modèle Ollama à utiliser (défaut: llama3.2:3b)"
    )
    parser.add_argument(
        "--input",
        type=str,
        default="services/wsdl/original",
        help="Répertoire des fichiers WSDL"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="services/wsdl/annotated",
        help="Répertoire de sortie pour les annotations"
    )
    
    args = parser.parse_args()
    
    annotate_all_services(
        wsdl_dir=args.input,
        output_dir=args.output,
        ollama_model=args.model
    )