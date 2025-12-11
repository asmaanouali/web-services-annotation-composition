"""
annotation_system/ollama_client.py
Client pour communiquer avec Ollama et générer les annotations
"""
import requests
import json
from typing import Dict, Optional, Any
import time


class OllamaClient:
    """Client pour interagir avec l'API Ollama"""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2:3b"):
        """
        Initialise le client Ollama
        
        Args:
            base_url: URL de base de l'API Ollama
            model: Nom du modèle à utiliser (llama3.2:3b, mistral, etc.)
        """
        self.base_url = base_url
        self.model = model
        self.api_url = f"{base_url}/api/generate"
        self.chat_url = f"{base_url}/api/chat"
        
    def check_connection(self) -> bool:
        """Vérifie la connexion à Ollama"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"Impossible de se connecter à Ollama: {e}")
            return False
    
    def list_models(self) -> list:
        """Liste les modèles disponibles"""
        try:
            response = requests.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
            return []
        except Exception as e:
            print(f"Erreur lors de la récupération des modèles: {e}")
            return []
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None, 
                 temperature: float = 0.3, format: str = "json") -> Dict:
        """
        Génère une réponse avec Ollama
        
        Args:
            prompt: Le prompt principal
            system_prompt: Prompt système optionnel
            temperature: Température pour la génération (0-1)
            format: Format de sortie ("json" ou "")
            
        Returns:
            Dictionnaire contenant la réponse
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        if format == "json":
            payload["format"] = "json"
        
        try:
            print(f"🔄 Envoi de la requête à Ollama (modèle: {self.model})...")
            start_time = time.time()
            
            response = requests.post(self.api_url, json=payload, timeout=300)
            
            elapsed_time = time.time() - start_time
            print(f"Réponse reçue en {elapsed_time:.2f}s")
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "response": result.get("response", ""),
                    "model": result.get("model", ""),
                    "elapsed_time": elapsed_time
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Timeout: Le modèle met trop de temps à répondre"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Erreur: {str(e)}"
            }
    
    def parse_json_response(self, response_text: str) -> Optional[Dict]:
        """
        Parse la réponse JSON du LLM
        Gère les cas où le JSON est mal formaté
        """
        try:
            # Nettoyer la réponse
            cleaned = response_text.strip()
            
            # Supprimer les backticks markdown si présents
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            
            cleaned = cleaned.strip()
            
            # Parser le JSON
            return json.loads(cleaned)
            
        except json.JSONDecodeError as e:
            print(f"Erreur de parsing JSON: {e}")
            print(f"Réponse brute: {response_text[:200]}...")
            return None
    
    def generate_with_retry(self, prompt: str, system_prompt: Optional[str] = None,
                           max_retries: int = 3) -> Optional[Dict]:
        """
        Génère avec retry en cas d'échec
        """
        for attempt in range(max_retries):
            result = self.generate(prompt, system_prompt)
            
            if result["success"]:
                parsed = self.parse_json_response(result["response"])
                if parsed:
                    return parsed
                else:
                    print(f"Tentative {attempt + 1}/{max_retries}: JSON invalide, retry...")
            else:
                print(f"Tentative {attempt + 1}/{max_retries}: {result['error']}")
            
            if attempt < max_retries - 1:
                time.sleep(2)  # Attendre avant de réessayer
        
        return None


# Test du client
if __name__ == "__main__":
    print("Test du client Ollama\n")
    
    # Créer le client
    client = OllamaClient(model="llama3.2:3b")
    
    # Vérifier la connexion
    print("Vérification de la connexion...")
    if client.check_connection():
        print("✅ Connexion à Ollama OK\n")
    else:
        print("Ollama n'est pas accessible. Assurez-vous qu'il est lancé (ollama serve)\n")
        exit(1)
    
    # Lister les modèles
    print("Modèles disponibles:")
    models = client.list_models()
    if models:
        for model in models:
            print(f"   - {model}")
    else:
        print("Aucun modèle trouvé. Installez un modèle avec: ollama pull llama3.2:3b")
    print()
    
    # Test simple
    print("Test de génération JSON...")
    test_prompt = """Generate a simple JSON object with these fields:
    - service_name: "TestService"
    - category: "search"
    - capabilities: a list with 2 capabilities"""
    
    result = client.generate(test_prompt, format="json", temperature=0.3)
    
    if result["success"]:
        print("Génération réussie!")
        parsed = client.parse_json_response(result["response"])
        if parsed:
            print("JSON parsé:")
            print(json.dumps(parsed, indent=2))
        else:
            print("Impossible de parser le JSON")
            print(f"Réponse brute: {result['response']}")
    else:
        print(f"Échec: {result['error']}")