"""
Application Flask principale
"""
from flask import Flask, request, jsonify, render_template_string
from config import Config
from services.wsdl_parser import WSDLParser
from services.llm_annotator import LLMAnnotator
from services.wsdl_enricher import WSDLEnricher
import os
import json
import traceback

# Initialisation
app = Flask(__name__)
Config.ensure_directories()

# Template HTML simple pour la page d'accueil
HOME_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>WSDL Annotator</title>
    <style>
        body { font-family: Arial; max-width: 800px; margin: 50px auto; padding: 20px; }
        h1 { color: #2c3e50; }
        .status { padding: 10px; background: #e8f5e9; border-radius: 5px; margin: 20px 0; }
        .endpoint { background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }
        code { background: #263238; color: #aed581; padding: 2px 6px; border-radius: 3px; }
        .new { background: #fff3cd; border-left: 4px solid #ffc107; }
    </style>
</head>
<body>
    <h1>🚀 WSDL Semantic Annotator</h1>
    <div class="status">
        <strong>Statut :</strong> Système opérationnel (Étape 2 - Parser WSDL)
    </div>
    
    <h2>Endpoints disponibles</h2>
    <div class="endpoint">
        <strong>GET /</strong> - Cette page
    </div>
    <div class="endpoint">
        <strong>GET /health</strong> - Vérifier le système
    </div>
    <div class="endpoint new">
        <strong>GET /parse-example</strong> - Parser le WSDL exemple (NOUVEAU ✨)
    </div>
    <div class="endpoint">
        <strong>POST /annotate</strong> - Annoter un WSDL (prochaine étape)
    </div>
    
    <h2>Configuration</h2>
    <ul>
        <li>LLM Model: {{ model }}</li>
        <li>Input Directory: {{ input_dir }}</li>
        <li>Output Directory: {{ output_dir }}</li>
    </ul>
    
    <h2>Test rapide</h2>
    <p>Clique ici pour tester le parser : <a href="/parse-example" target="_blank">Parser exemple_service.wsdl</a></p>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def home():
    """Page d'accueil"""
    return render_template_string(
        HOME_TEMPLATE,
        model=Config.OLLAMA_MODEL,
        input_dir=Config.INPUT_DIR,
        output_dir=Config.OUTPUT_DIR
    )

@app.route("/health", methods=["GET"])
def health():
    """Vérifier l'état du système"""
    import requests
    
    status = {
        "flask": "OK",
        "ollama": "Checking...",
        "directories": {
            "input": os.path.exists(Config.INPUT_DIR),
            "output": os.path.exists(Config.OUTPUT_DIR)
        }
    }
    
    # Vérifier Ollama
    try:
        response = requests.get(f"{Config.OLLAMA_BASE_URL}/api/tags", timeout=2)
        if response.status_code == 200:
            status["ollama"] = "OK"
            models = response.json().get("models", [])
            status["available_models"] = [m.get("name") for m in models]
        else:
            status["ollama"] = "ERROR"
    except Exception as e:
        status["ollama"] = f"ERROR: {str(e)}"
        status["ollama_note"] = "Assure-toi qu'Ollama est lancé : ollama serve"
    
    return jsonify(status)

@app.route("/parse-example", methods=["GET"])
def parse_example():
    """Parser le fichier WSDL exemple"""
    try:
        wsdl_path = os.path.join(Config.INPUT_DIR, "exemple_service.wsdl")
        
        if not os.path.exists(wsdl_path):
            return jsonify({
                "error": "Fichier exemple_service.wsdl non trouvé",
                "path": wsdl_path
            }), 404
        
        # Parser le WSDL
        parser = WSDLParser(wsdl_path)
        service_info = parser.parse()
        
        # Ajouter le résumé
        service_info['summary'] = parser.get_summary()
        
        # Retirer le raw_wsdl pour un affichage plus propre
        service_info_display = service_info.copy()
        service_info_display['raw_wsdl'] = f"[{len(service_info['raw_wsdl'])} caractères]"
        
        return jsonify({
            "status": "success",
            "message": "WSDL parsé avec succès",
            "service_info": service_info_display
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }), 500

@app.route("/annotate", methods=["POST"])
@app.route("/annotate", methods=["POST"])
def annotate():
    """Endpoint pour annoter et enrichir un WSDL"""
    try:
        # Récupérer le nom du fichier WSDL
        data = request.get_json()
        
        if not data or 'wsdl_filename' not in data:
            wsdl_filename = "exemple_service.wsdl"
        else:
            wsdl_filename = data['wsdl_filename']
        
        wsdl_path = os.path.join(Config.INPUT_DIR, wsdl_filename)
        
        if not os.path.exists(wsdl_path):
            return jsonify({
                "error": f"Fichier {wsdl_filename} non trouvé",
                "path": wsdl_path
            }), 404
        
        # Étape 1 : Parser le WSDL
        print(f"📖 Parsing {wsdl_filename}...")
        parser = WSDLParser(wsdl_path)
        service_info = parser.parse()
        
        # Étape 2 : Générer les annotations
        print(f"🤖 Génération des annotations...")
        annotator = LLMAnnotator()
        
        # Vérifier Ollama
        ollama_status = annotator.check_ollama_status()
        if ollama_status["status"] != "ok":
            return jsonify({
                "error": "Ollama non accessible",
                "details": ollama_status,
                "hint": "Assure-toi qu'Ollama est lancé"
            }), 503
        
        annotations = annotator.generate_annotations(service_info)
        
        # Étape 3 : Enrichir le WSDL
        print(f"🔧 Enrichissement du WSDL...")
        base_name = wsdl_filename.replace('.wsdl', '')
        enriched_path = os.path.join(Config.OUTPUT_DIR, f"{base_name}_enriched.wsdl")
        
        enricher = WSDLEnricher(wsdl_path)
        enricher.enrich(annotations, enriched_path)
        
        # Sauvegarder les résultats en JSON
        json_output = os.path.join(Config.OUTPUT_DIR, f"{base_name}_annotations.json")
        result = {
            "service_info": service_info,
            "annotations": annotations,
            "enriched_wsdl_path": enriched_path
        }
        
        with open(json_output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Pipeline complet terminé")
        
        return jsonify({
            "status": "success",
            "message": "WSDL annoté et enrichi avec succès",
            "service_name": service_info['service_name'],
            "annotations": annotations,
            "files": {
                "enriched_wsdl": enriched_path,
                "annotations_json": json_output
            }
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }), 500

if __name__ == "__main__":
    print("🚀 Démarrage du serveur...")
    print(f"📁 Input: {Config.INPUT_DIR}")
    print(f"📁 Output: {Config.OUTPUT_DIR}")
    print(f"🤖 LLM Model: {Config.OLLAMA_MODEL}")
    print(f"🌐 URL: http://{Config.FLASK_HOST}:{Config.FLASK_PORT}")
    
    app.run(
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=Config.FLASK_DEBUG
    )