"""
Solution B: Composition intelligente avec LLM (Ollama)
Utilise un LLM local pour raisonner sur les compositions
"""

import time
import json
import requests
from models.service import CompositionResult
from utils.qos_calculator import calculate_utility


class LLMComposer:
    def __init__(self, services, ollama_url="http://localhost:11434"):
        self.services = services
        self.service_dict = {s.id: s for s in services}
        self.ollama_url = ollama_url
        self.model = "llama3.2:3b"  # ou "mistral", "codellama", etc.
        self.conversation_history = []
    
    def compose(self, request, enable_reasoning=True, enable_adaptation=True):
        """
        Compose des services en utilisant le raisonnement LLM
        
        Args:
            request: CompositionRequest
            enable_reasoning: Active le raisonnement du LLM
            enable_adaptation: Active l'adaptation contextuelle
        
        Returns:
            CompositionResult
        """
        start_time = time.time()
        result = CompositionResult()
        
        try:
            # Étape 1: Analyser le contexte avec le LLM
            context_analysis = self._analyze_context(request) if enable_reasoning else {}
            
            # Étape 2: Sélectionner les services avec le LLM
            selected_services = self._llm_select_services(request, context_analysis)
            
            # Étape 3: Valider et calculer l'utilité
            if selected_services:
                best_service = selected_services[0]
                
                qos_checks = best_service.qos.meets_constraints(request.qos_constraints)
                utility = calculate_utility(
                    best_service.qos,
                    request.qos_constraints,
                    qos_checks
                )
                
                # Bonus pour les annotations
                if best_service.annotations:
                    utility += best_service.annotations.trust_degree * 5
                    utility += best_service.annotations.reputation * 5
                
                # Étape 4: Générer l'explication
                explanation = self._generate_explanation(
                    best_service,
                    request,
                    context_analysis,
                    qos_checks
                )
                
                # Étape 5: Appliquer des adaptations si activées
                adaptations = []
                if enable_adaptation:
                    adaptations = self._apply_adaptations(best_service, context_analysis)
                
                result.services = [best_service]
                result.workflow = [best_service.id]
                result.utility_value = utility
                result.qos_achieved = best_service.qos
                result.success = True
                result.explanation = explanation
                
                if adaptations:
                    result.explanation += "\n\nAdaptations appliquées:\n" + "\n".join(f"- {a}" for a in adaptations)
            
            else:
                result.explanation = "Le LLM n'a trouvé aucun service approprié"
        
        except Exception as e:
            print(f"Erreur LLM composition: {e}")
            result.success = False
            result.explanation = f"Erreur: {str(e)}"
        
        result.computation_time = time.time() - start_time
        return result
    
    def _analyze_context(self, request):
        """Analyse le contexte de la requête avec le LLM"""
        # Préparer les informations pour le LLM
        context_info = {
            'provided_params': request.provided,
            'target_param': request.resultant,
            'qos_constraints': request.qos_constraints.to_dict()
        }
        
        prompt = f"""Analyze this service composition request and identify key priorities:

Request Details:
- Input parameters available: {len(request.provided)} parameters
- Target output: {request.resultant}
- QoS Constraints:
  * Response Time: ≤ {request.qos_constraints.response_time}
  * Availability: ≥ {request.qos_constraints.availability}
  * Reliability: ≥ {request.qos_constraints.reliability}

Based on these constraints, identify:
1. Priority level (high/medium/low)
2. Environment type (production/development/test)
3. Main concerns (performance/reliability/security)

Respond in JSON format with: {{"priority": "...", "environment": "...", "main_concern": "..."}}
"""
        
        try:
            response = self._call_ollama(prompt)
            # Extraire le JSON de la réponse
            analysis = self._extract_json(response)
            return analysis
        except:
            # Fallback: analyse basique
            return {
                "priority": "high" if request.qos_constraints.availability > 90 else "medium",
                "environment": "production",
                "main_concern": "reliability"
            }
    
    def _llm_select_services(self, request, context_analysis):
        """Sélectionne les services en utilisant le LLM"""
        # Trouver les candidats
        candidates = [
            s for s in self.services
            if request.resultant in s.outputs and s.has_required_inputs(request.provided)
        ]
        
        if not candidates:
            return []
        
        # Limiter à 10 meilleurs candidats pour le LLM
        candidates = sorted(candidates, key=lambda s: s.qos.reliability, reverse=True)[:10]
        
        # Préparer les informations des services pour le LLM
        services_info = []
        for s in candidates:
            info = {
                'id': s.id,
                'qos': {
                    'reliability': s.qos.reliability,
                    'availability': s.qos.availability,
                    'response_time': s.qos.response_time
                }
            }
            
            if s.annotations:
                info['annotations'] = {
                    'trust': s.annotations.trust_degree,
                    'reputation': s.annotations.reputation,
                    'role': s.annotations.interaction.role
                }
            
            services_info.append(info)
        
        prompt = f"""Select the best service for this composition request.

Context: {json.dumps(context_analysis, indent=2)}

Available Services:
{json.dumps(services_info, indent=2)}

Constraints:
- Response Time: ≤ {request.qos_constraints.response_time}
- Availability: ≥ {request.qos_constraints.availability}
- Reliability: ≥ {request.qos_constraints.reliability}

Select the service ID that best matches these requirements.
Respond with just the service ID.
"""
        
        try:
            response = self._call_ollama(prompt)
            selected_id = response.strip()
            
            # Trouver le service correspondant
            for s in candidates:
                if s.id in selected_id:
                    return [s]
            
            # Si pas de match, retourner le meilleur candidat
            return [candidates[0]]
        
        except:
            # Fallback: retourner le meilleur candidat
            return [candidates[0]]
    
    def _generate_explanation(self, service, request, context_analysis, qos_checks):
        """Génère une explication détaillée avec le LLM"""
        prompt = f"""Explain why service {service.id} was selected for this composition:

Service QoS:
- Reliability: {service.qos.reliability}
- Availability: {service.qos.availability}
- Response Time: {service.qos.response_time}

Context: {json.dumps(context_analysis)}

QoS Constraints Met: {sum(qos_checks.values())}/{len(qos_checks)}

Provide a brief, professional explanation (2-3 sentences).
"""
        
        try:
            explanation = self._call_ollama(prompt)
            return explanation.strip()
        except:
            # Fallback: explication basique
            met_count = sum(qos_checks.values())
            total_count = len(qos_checks)
            
            explanation = f"Service {service.id} sélectionné par le LLM. "
            explanation += f"Il satisfait {met_count}/{total_count} contraintes QoS. "
            
            if service.annotations:
                explanation += f"Trust degree: {service.annotations.trust_degree:.2f}, "
                explanation += f"Reputation: {service.annotations.reputation:.2f}. "
            
            return explanation
    
    def _apply_adaptations(self, service, context_analysis):
        """Applique des adaptations contextuelles"""
        adaptations = []
        
        priority = context_analysis.get('priority', 'medium')
        environment = context_analysis.get('environment', 'production')
        
        if priority == 'high':
            adaptations.append("Failover strategy activated for high priority")
            adaptations.append("Monitoring enhanced for critical service")
        
        if environment == 'production':
            adaptations.append("Production-grade caching enabled")
            adaptations.append("Advanced logging activated")
        
        if service.annotations:
            if service.annotations.policy.security_level == 'high':
                adaptations.append("Enhanced security protocols applied")
            
            if service.annotations.context.time_critical == 'high':
                adaptations.append("Priority execution queue assigned")
        
        return adaptations
    
    def _call_ollama(self, prompt):
        """Appelle l'API Ollama"""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "top_p": 0.9
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()['response']
            else:
                raise Exception(f"Ollama API error: {response.status_code}")
        
        except requests.exceptions.ConnectionError:
            raise Exception("Cannot connect to Ollama. Is it running? Start with: ollama serve")
        except Exception as e:
            raise Exception(f"Ollama error: {str(e)}")
    
    def _extract_json(self, text):
        """Extrait du JSON d'une réponse texte"""
        try:
            # Chercher du JSON dans la réponse
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start != -1 and end > start:
                json_str = text[start:end]
                return json.loads(json_str)
            
            return {}
        except:
            return {}
    
    def chat(self, message):
        """Chat interactif avec le LLM pour clarifier les besoins"""
        self.conversation_history.append({
            "role": "user",
            "content": message
        })
        
        # Construire le contexte
        context = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in self.conversation_history[-5:]  # Garder les 5 derniers messages
        ])
        
        prompt = f"""You are an expert in web service composition. 
Help the user understand service selection and composition.

Conversation:
{context}

Respond helpfully and concisely.
"""
        
        try:
            response = self._call_ollama(prompt)
            
            self.conversation_history.append({
                "role": "assistant",
                "content": response
            })
            
            return response
        except Exception as e:
            return f"Error communicating with LLM: {str(e)}"