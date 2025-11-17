"""
LLM Annotator - Génération d'annotations sémantiques via LLM
"""
import requests
import json
from config import Config

class LLMAnnotator:
    """Classe pour générer des annotations sémantiques via Ollama"""
    
    def __init__(self, model=None):
        """
        Initialise l'annotateur LLM
        
        Args:
            model (str): Nom du modèle Ollama à utiliser
        """
        self.model = model or Config.OLLAMA_MODEL
        self.base_url = Config.OLLAMA_BASE_URL
        self.api_url = f"{self.base_url}/api/generate"
        
    def _call_ollama(self, prompt, system_prompt=None):
        """
        Appelle l'API Ollama avec streaming pour éviter les timeouts
        
        Args:
            prompt (str): Le prompt utilisateur
            system_prompt (str): Instructions système pour le LLM
            
        Returns:
            str: Réponse du LLM
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,  # Activé pour éviter les timeouts
            "options": {
                "temperature": 0.3,
                "top_p": 0.9,
                "num_predict": 1000  # Limiter la longueur de réponse
            }
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=120,  # 2 minutes max
                stream=True
            )
            response.raise_for_status()
            
            # Collecter la réponse streamée
            full_response = ""
            print("   ", end="", flush=True)
            
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        if "response" in chunk:
                            full_response += chunk["response"]
                            # Afficher un point pour montrer la progression
                            print(".", end="", flush=True)
                        
                        # Vérifier si c'est la dernière partie
                        if chunk.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue
            
            print()  # Nouvelle ligne après les points
            return full_response
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Erreur lors de l'appel à Ollama: {str(e)}")
    
    def generate_annotations(self, service_info):
        """
        Génère des annotations sémantiques pour un service SOAP
        
        Args:
            service_info (dict): Informations extraites du WSDL
            
        Returns:
            dict: Annotations générées
        """
        # Construire le prompt système (plus concis)
        system_prompt = """Tu es un expert en services web SOAP. Analyse le service et génère des annotations JSON.

Structure JSON requise :
{
  "domain": "domaine (ex: météo, finance)",
  "description": "description brève",
  "keywords": ["mot1", "mot2", "mot3"],
  "use_cases": ["usage1", "usage2"],
  "operations": [
    {
      "name": "nom_operation",
      "semantic_description": "description",
      "input_semantic": "signification input",
      "output_semantic": "signification output"
    }
  ]
}

Réponds UNIQUEMENT en JSON, sans texte supplémentaire."""

        # Construire le prompt utilisateur (plus court)
        prompt = self._build_annotation_prompt(service_info)
        
        # Appeler le LLM
        print(f"🤖 Appel du LLM ({self.model})...")
        response = self._call_ollama(prompt, system_prompt)
        
        # Parser la réponse JSON
        try:
            annotations = self._parse_llm_response(response)
            return annotations
        except Exception as e:
            print(f"⚠️  Erreur parsing JSON: {e}")
            print(f"Réponse brute: {response[:300]}...")
            # Retourner des annotations par défaut
            return self._generate_default_annotations(service_info)
    
    def _build_annotation_prompt(self, service_info):
        """Construit le prompt pour le LLM (version courte)"""
        prompt = f"""Analyse ce service SOAP :

Service: {service_info['service_name']}
Endpoint: {service_info['endpoint']}

Opérations:
"""
        for op in service_info['operations'][:3]:  # Limiter à 3 opérations max
            prompt += f"- {op['name']}: {op['input_message']} → {op['output_message']}\n"
        
        prompt += "\nTypes principaux:\n"
        for type_def in service_info['types'][:5]:  # Limiter à 5 types max
            if type_def['fields']:
                prompt += f"- {type_def['name']}: "
                field_names = [f['name'] for f in type_def['fields'][:3]]
                prompt += ", ".join(field_names) + "\n"
        
        prompt += "\nGénère le JSON d'annotations maintenant :"
        
        return prompt
    
    def _parse_llm_response(self, response):
        """Parse la réponse du LLM en JSON"""
        # Nettoyer la réponse
        response = response.strip()
        
        # Retirer les balises markdown si présentes
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.rfind("```")
            if end > start:
                response = response[start:end]
        elif "```" in response:
            start = response.find("```") + 3
            end = response.rfind("```")
            if end > start:
                response = response[start:end]
        
        response = response.strip()
        
        # Trouver le premier { et le dernier }
        first_brace = response.find("{")
        last_brace = response.rfind("}")
        
        if first_brace != -1 and last_brace != -1:
            response = response[first_brace:last_brace+1]
        
        # Parser le JSON
        annotations = json.loads(response)
        
        # Valider la structure minimale
        required_keys = ["domain", "description"]
        for key in required_keys:
            if key not in annotations:
                raise ValueError(f"Clé manquante: {key}")
        
        # Ajouter des valeurs par défaut si manquantes
        if "keywords" not in annotations:
            annotations["keywords"] = ["soap", "web-service"]
        if "use_cases" not in annotations:
            annotations["use_cases"] = ["Integration"]
        if "operations" not in annotations:
            annotations["operations"] = []
        
        return annotations
    
    def _generate_default_annotations(self, service_info):
        """Génère des annotations par défaut en cas d'erreur"""
        return {
            "domain": "unknown",
            "description": f"Service SOAP: {service_info['service_name']}",
            "keywords": ["soap", "web-service"],
            "use_cases": ["Integration via SOAP"],
            "operations": [
                {
                    "name": op['name'],
                    "semantic_description": f"Operation {op['name']}",
                    "input_semantic": f"Input data for {op['name']}",
                    "output_semantic": f"Output data from {op['name']}"
                }
                for op in service_info['operations']
            ],
            "generation_status": "default_fallback"
        }
    
    def check_ollama_status(self):
        """Vérifie si Ollama est accessible"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                return {
                    "status": "ok",
                    "available_models": [m.get("name") for m in models],
                    "current_model": self.model
                }
            else:
                return {"status": "error", "message": "Ollama non accessible"}
        except Exception as e:
            return {"status": "error", "message": str(e)}