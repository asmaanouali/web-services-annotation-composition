import requests
import json
from typing import Dict, Any, List
from src.models.service import Service

class LLMAnnotator:
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "llama2"):
        self.ollama_url = ollama_url
        self.model = model
        self.timeout = 60
    
    def is_available(self) -> bool:
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def annotate_service(self, service: Service, all_services: List[Service]) -> Dict[str, Any]:
        """
        Génère les 3 types d'annotations selon le stage:
        1. Interaction or not with other services
        2. Interactions context
        3. Policy associated to the use of these annotations
        """
        
        other_service_names = [s.name for s in all_services if s.id != service.id]
        
        prompt = f"""Analyze this web service and create annotations in JSON format.

Service Name: {service.name}
Operations: {', '.join(service.operations)}
Functionalities: {', '.join(service.functionalities)}
Available services to interact with: {', '.join(other_service_names)}

Create annotations with these 3 types:

1. INTERACTION ANNOTATIONS (for each operation):
   - operation name
   - number_of_interactions (historical usage count: 0-500)
   - success_rate (0.0 to 1.0)
   - avg_response_time_ms (50-500ms)
   - interacts_with_services (list of service names it commonly works with)

2. CONTEXT ANNOTATIONS:
   - location_dependent (true/false)
   - time_sensitive (true/false)
   - user_preference_based (true/false)
   - requires_session (true/false)

3. POLICY ANNOTATIONS:
   - requires_authentication (true/false)
   - data_privacy_level (GDPR, CCPA, HIPAA, or PUBLIC)
   - rate_limit_per_minute (100-1000)
   - allowed_clients (["*"] or specific list)
   - usage_cost (LOW, MEDIUM, HIGH)

Return ONLY valid JSON with this structure:
{{
  "interaction_annotations": [
    {{
      "operation": "operationName",
      "number_of_interactions": 150,
      "success_rate": 0.95,
      "avg_response_time_ms": 200,
      "interacts_with_services": ["ServiceA", "ServiceB"]
    }}
  ],
  "context_annotations": {{
    "location_dependent": false,
    "time_sensitive": true,
    "user_preference_based": false,
    "requires_session": true
  }},
  "policy_annotations": {{
    "requires_authentication": true,
    "data_privacy_level": "GDPR",
    "rate_limit_per_minute": 500,
    "allowed_clients": ["*"],
    "usage_cost": "MEDIUM"
  }}
}}

Be realistic based on service type."""

        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                text = response.json().get('response', '{}')
                # Extraire le JSON
                start = text.find('{')
                end = text.rfind('}') + 1
                if start >= 0 and end > start:
                    annotations = json.loads(text[start:end])
                    return self._validate_annotations(annotations, service, other_service_names)
        except:
            pass
        
        # Si Ollama échoue, générer des annotations réalistes
        return self._generate_realistic_annotations(service, other_service_names)
    
    def _validate_annotations(self, data: Dict, service: Service, other_services: List[str]) -> Dict:
        if 'interaction_annotations' not in data:
            return self._generate_realistic_annotations(service, other_services)
        return data
    
    def _generate_realistic_annotations(self, service: Service, other_services: List[str]) -> Dict:
        import random
        
        interaction_anns = []
        for operation in service.operations:
            # Choisir 1-3 services avec qui il interagit
            num_interactions = random.randint(1, min(3, len(other_services))) if other_services else 0
            interacts_with = random.sample(other_services, num_interactions) if num_interactions > 0 else []
            
            interaction_anns.append({
                "operation": operation,
                "number_of_interactions": random.randint(50, 400),
                "success_rate": round(random.uniform(0.85, 0.99), 2),
                "avg_response_time_ms": random.randint(80, 400),
                "interacts_with_services": interacts_with
            })
        
        return {
            "interaction_annotations": interaction_anns,
            "context_annotations": {
                "location_dependent": random.choice([True, False]),
                "time_sensitive": random.choice([True, False]),
                "user_preference_based": random.choice([True, False]),
                "requires_session": random.choice([True, False])
            },
            "policy_annotations": {
                "requires_authentication": random.choice([True, False]),
                "data_privacy_level": random.choice(["GDPR", "CCPA", "HIPAA", "PUBLIC"]),
                "rate_limit_per_minute": random.randint(100, 1000),
                "allowed_clients": ["*"],
                "usage_cost": random.choice(["LOW", "MEDIUM", "HIGH"])
            }
        }
    
    def enrich_wsdl(self, original_wsdl: str, annotations: Dict[str, Any]) -> str:
        """Enrichit le WSDL avec les annotations"""
        # Ajouter les annotations en commentaire XML dans le WSDL
        annotations_comment = f"\n<!-- ENRICHED ANNOTATIONS\n{json.dumps(annotations, indent=2)}\n-->\n"
        
        # Insérer avant la balise de fermeture </definitions>
        if '</definitions>' in original_wsdl:
            enriched = original_wsdl.replace('</definitions>', annotations_comment + '</definitions>')
        else:
            enriched = original_wsdl + annotations_comment
        
        return enriched
