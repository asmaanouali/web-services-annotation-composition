"""
annotation_system/batch_separate_annotate.py
Script pour annoter tous les services avec annotations SÉPARÉES
"""
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from annotation_system.separate_annotation_generator import SeparateAnnotationGenerator


def annotate_all_services_separately(wsdl_dir: str = "services/wsdl/original",
                                     output_dir: str = "services/wsdl/annotated/separate",
                                     ollama_model: str = "llama3.2:3b"):
    """
    Annote tous les services avec génération SÉPARÉE de chaque type
    
    Args:
        wsdl_dir: Répertoire contenant les fichiers WSDL
        output_dir: Répertoire de sortie pour les annotations séparées
        ollama_model: Modèle Ollama à utiliser
    """
    print("="*80)
    print("ANNOTATION BATCH - MODE SÉPARÉ")
    print("="*80)
    print("\nChaque type d'annotation sera généré indépendamment:")
    print("  1. Annotation Fonctionnelle")
    print("  2. Annotation d'Interaction")
    print("  3. Annotation de Contexte")
    print("  4. Annotation de Politique")
    
    # Vérifier que le répertoire existe
    if not os.path.exists(wsdl_dir):
        print(f"\n✗ Répertoire non trouvé: {wsdl_dir}")
        return
    
    # Créer le répertoire de sortie
    os.makedirs(output_dir, exist_ok=True)
    
    # Lister tous les fichiers WSDL
    wsdl_files = [f for f in os.listdir(wsdl_dir) if f.endswith('.wsdl')]
    
    if not wsdl_files:
        print(f"\n✗ Aucun fichier WSDL trouvé dans {wsdl_dir}")
        return
    
    print(f"\n📋 {len(wsdl_files)} services à annoter:")
    for i, filename in enumerate(wsdl_files, 1):
        print(f"   {i}. {filename}")
    
    # Créer le générateur
    try:
        generator = SeparateAnnotationGenerator(ollama_model=ollama_model)
        print(f"\n✓ Générateur initialisé (modèle: {ollama_model})")
    except ConnectionError as e:
        print(f"\n✗ {e}")
        print("   Lancez Ollama avec: ollama serve")
        return
    
    # Résultats
    results = {
        "services": [],
        "total": len(wsdl_files),
        "completed": 0,
        "failed": []
    }
    
    # Annoter chaque service
    for i, filename in enumerate(wsdl_files, 1):
        wsdl_path = os.path.join(wsdl_dir, filename)
        service_name = filename.replace('.wsdl', '')
        
        print(f"\n{'='*80}")
        print(f"[{i}/{len(wsdl_files)}] SERVICE: {service_name}")
        print(f"{'='*80}")
        
        service_result = {
            "service_name": service_name,
            "annotations": {}
        }
        
        try:
            # 1. Annotation Fonctionnelle
            print("\n🔹 ÉTAPE 1/4: Annotation Fonctionnelle")
            func_ann = generator.generate_functional_annotation(wsdl_path)
            if func_ann:
                generator.save_annotation(func_ann, 'functional', service_name, output_dir)
                service_result["annotations"]["functional"] = "✓"
            else:
                service_result["annotations"]["functional"] = "✗"
            
            # 2. Annotation d'Interaction (avec contexte de l'annotation fonctionnelle)
            print("\n🔹 ÉTAPE 2/4: Annotation d'Interaction")
            inter_ann = generator.generate_interaction_annotation(wsdl_path, func_ann)
            if inter_ann:
                generator.save_annotation(inter_ann, 'interaction', service_name, output_dir)
                service_result["annotations"]["interaction"] = "✓"
            else:
                service_result["annotations"]["interaction"] = "✗"
            
            # 3. Annotation de Contexte
            print("\n🔹 ÉTAPE 3/4: Annotation de Contexte")
            ctx_ann = generator.generate_context_annotation(wsdl_path)
            if ctx_ann:
                generator.save_annotation(ctx_ann, 'context', service_name, output_dir)
                service_result["annotations"]["context"] = "✓"
            else:
                service_result["annotations"]["context"] = "✗"
            
            # 4. Annotation de Politique (avec contexte de l'annotation fonctionnelle)
            print("\n🔹 ÉTAPE 4/4: Annotation de Politique")
            pol_ann = generator.generate_policy_annotation(wsdl_path, func_ann)
            if pol_ann:
                generator.save_annotation(pol_ann, 'policy', service_name, output_dir)
                service_result["annotations"]["policy"] = "✓"
            else:
                service_result["annotations"]["policy"] = "✗"
            
            # Vérifier si toutes les annotations ont été générées
            all_success = all(v == "✓" for v in service_result["annotations"].values())
            
            if all_success:
                results["completed"] += 1
                service_result["status"] = "success"
                print(f"\n✓ [{i}/{len(wsdl_files)}] {service_name} - Toutes les annotations générées")
            else:
                results["failed"].append(service_name)
                service_result["status"] = "partial"
                print(f"\n⚠️  [{i}/{len(wsdl_files)}] {service_name} - Annotations partielles")
            
            results["services"].append(service_result)
            
        except Exception as e:
            results["failed"].append(service_name)
            service_result["status"] = "failed"
            service_result["error"] = str(e)
            results["services"].append(service_result)
            print(f"\n✗ [{i}/{len(wsdl_files)}] Erreur pour {service_name}: {e}")
    
    # Rapport final
    print("\n\n" + "="*80)
    print("RAPPORT FINAL - ANNOTATIONS SÉPARÉES")
    print("="*80)
    
    print(f"\n📊 STATISTIQUES:")
    print(f"   • Services traités: {len(wsdl_files)}")
    print(f"   • Complètement annotés: {results['completed']}")
    print(f"   • Partiellement annotés: {len([s for s in results['services'] if s['status'] == 'partial'])}")
    print(f"   • Échecs: {len(results['failed'])}")
    
    print(f"\n📁 DÉTAILS PAR SERVICE:")
    for service_result in results["services"]:
        status_icon = "✓" if service_result["status"] == "success" else "⚠️" if service_result["status"] == "partial" else "✗"
        print(f"\n   {status_icon} {service_result['service_name']}")
        print(f"      Status: {service_result['status']}")
        for ann_type, status in service_result["annotations"].items():
            print(f"         • {ann_type}: {status}")
    
    if results["failed"]:
        print(f"\n✗ Services en échec complet:")
        for service_name in results["failed"]:
            print(f"   • {service_name}")
    
    # Sauvegarder le rapport
    report_path = os.path.join(output_dir, "annotation_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Rapport sauvegardé: {report_path}")
    print(f"\n📂 Annotations sauvegardées dans: {output_dir}/")
    print("\n✨ Annotation terminée!")


def combine_all_annotations(separate_dir: str = "services/wsdl/annotated/separate",
                            wsdl_dir: str = "services/wsdl/original",
                            output_dir: str = "services/wsdl/annotated",
                            ollama_model: str = "llama3.2:3b"):
    """
    Combine toutes les annotations séparées en annotations complètes
    
    Args:
        separate_dir: Répertoire des annotations séparées
        wsdl_dir: Répertoire des WSDL
        output_dir: Répertoire de sortie
        ollama_model: Modèle (non utilisé mais pour cohérence)
    """
    print("\n" + "="*80)
    print("COMBINAISON DES ANNOTATIONS SÉPARÉES")
    print("="*80)
    
    if not os.path.exists(separate_dir):
        print(f"\n✗ Répertoire non trouvé: {separate_dir}")
        return
    
    # Trouver tous les services annotés
    annotation_files = [f for f in os.listdir(separate_dir) if f.endswith('_functional.json')]
    services = [f.replace('_functional.json', '') for f in annotation_files]
    
    if not services:
        print(f"\n✗ Aucune annotation trouvée dans {separate_dir}")
        return
    
    print(f"\n📋 {len(services)} services à combiner:")
    for service in services:
        print(f"   • {service}")
    
    try:
        generator = SeparateAnnotationGenerator(ollama_model=ollama_model)
    except ConnectionError as e:
        print(f"\n✗ {e}")
        return
    
    results = {
        "success": [],
        "failed": []
    }
    
    for i, service_name in enumerate(services, 1):
        wsdl_path = os.path.join(wsdl_dir, f"{service_name}.wsdl")
        
        print(f"\n[{i}/{len(services)}] Combinaison: {service_name}")
        
        annotation = generator.combine_annotations(service_name, wsdl_path, separate_dir, output_dir)
        
        if annotation:
            results["success"].append(service_name)
            print(f"   ✓ Combinaison réussie")
        else:
            results["failed"].append(service_name)
            print(f"   ✗ Échec de combinaison")
    
    print("\n" + "="*80)
    print("RAPPORT FINAL - COMBINAISON")
    print("="*80)
    
    print(f"\n✓ Succès: {len(results['success'])}/{len(services)}")
    for service in results["success"]:
        print(f"   • {service}")
    
    if results["failed"]:
        print(f"\n✗ Échecs: {len(results['failed'])}")
        for service in results["failed"]:
            print(f"   • {service}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Annotation batch en mode séparé")
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
        default="services/wsdl/annotated/separate",
        help="Répertoire de sortie pour les annotations séparées"
    )
    parser.add_argument(
        "--combine",
        action="store_true",
        help="Combiner les annotations séparées en annotations complètes"
    )
    
    args = parser.parse_args()
    
    if args.combine:
        combine_all_annotations(
            separate_dir=args.output,
            wsdl_dir=args.input,
            output_dir="services/wsdl/annotated",
            ollama_model=args.model
        )
    else:
        annotate_all_services_separately(
            wsdl_dir=args.input,
            output_dir=args.output,
            ollama_model=args.model
        )