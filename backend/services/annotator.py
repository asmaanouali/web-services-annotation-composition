"""
Module d'annotation automatique des services web
Basé sur le modèle MOF-based Social Web Services
Utilise un LLM pour générer des annotations intelligentes
"""

import random
import json
import requests
from models.annotation import ServiceAnnotation, InteractionAnnotation, ContextAnnotation, PolicyAnnotation


class ServiceAnnotator:
    def __init__(self, services=None, ollama_url="http://localhost:11434"):
        self.services = services or []
        self.service_dict = {s.id: s for s in self.services}
        self.ollama_url = ollama_url
        self.model = "llama2"
    
    def annotate_service(self, service, use_llm=False, annotation_types=None):
        """
        Annote un service avec les types d'annotations sélectionnés
        
        Args:
            service: Service à annoter
            use_llm: Utiliser le LLM pour les annotations
            annotation_types: Liste des types ('interaction', 'context', 'policy')
        """
        if annotation_types is None:
            annotation_types = ['interaction', 'context', 'policy']
        
        annotation = ServiceAnnotation()
        
        if use_llm:
            # Utiliser le LLM pour générer les annotations
            annotation = self._annotate_with_llm(service, annotation_types)
        else:
            # Utiliser la méthode classique
            if 'interaction' in annotation_types:
                annotation.interaction = self._generate_interaction_annotations(service)
            
            if 'context' in annotation_types:
                annotation.context = self._generate_context_annotations(service)
            
            if 'policy' in annotation_types:
                annotation.policy = self._generate_policy_annotations(service)
        
        # Propriétés sociales (toujours calculées)
        annotation.trust_degree = self._calculate_trust(service)
        annotation.reputation = self._calculate_reputation(service)
        annotation.collaboration_weight = self._find_collaborations(service)
        annotation.robustness_score = self._calculate_robustness(service)
        
        service.annotations = annotation
        return service
    
    def _annotate_with_llm(self, service, annotation_types):
        """Utilise le LLM pour générer des annotations intelligentes"""
        annotation = ServiceAnnotation()
        
        # Préparer le contexte du service
        service_context = {
            'id': service.id,
            'inputs': service.inputs,
            'outputs': service.outputs,
            'qos': {
                'reliability': service.qos.reliability,
                'availability': service.qos.availability,
                'response_time': service.qos.response_time,
                'compliance': service.qos.compliance,
                'security': service.qos.best_practices
            }
        }
        
        # Générer chaque type d'annotation avec le LLM
        if 'interaction' in annotation_types:
            annotation.interaction = self._llm_generate_interaction(service, service_context)
        
        if 'context' in annotation_types:
            annotation.context = self._llm_generate_context(service, service_context)
        
        if 'policy' in annotation_types:
            annotation.policy = self._llm_generate_policy(service, service_context)
        
        return annotation
    
    def _llm_generate_interaction(self, service, context):
        """Génère les annotations d'interaction avec le LLM"""
        interaction = InteractionAnnotation()
        
        # Trouver les services compatibles
        compatible_services = []
        for other in self.services:
            if other.id != service.id:
                io_match = len(set(service.outputs) & set(other.inputs))
                if io_match > 0:
                    compatible_services.append({
                        'id': other.id,
                        'match_score': io_match
                    })
        
        prompt = f"""Analyze this web service and determine its interaction characteristics:

Service ID: {service.id}
Number of inputs: {len(service.inputs)}
Number of outputs: {len(service.outputs)}
QoS Reliability: {service.qos.reliability}%
Compatible services found: {len(compatible_services)}

Based on this information, respond ONLY with a JSON object (no markdown, no explanation):
{{
  "role": "orchestrator" or "worker" or "aggregator",
  "can_call_count": number of services this can call (0-{len(compatible_services)}),
  "collaboration_level": "high" or "medium" or "low"
}}
"""
        
        try:
            response = self._call_ollama(prompt)
            data = self._extract_json(response)
            
            if data:
                # Déterminer le rôle
                role_map = {
                    'orchestrator': 'orchestrator',
                    'worker': 'worker',
                    'aggregator': 'aggregator'
                }
                interaction.role = role_map.get(data.get('role', '').lower(), 'worker')
                
                # Sélectionner les services à appeler
                can_call_count = min(data.get('can_call_count', 3), len(compatible_services))
                top_compatible = sorted(compatible_services, key=lambda x: x['match_score'], reverse=True)
                interaction.can_call = [s['id'] for s in top_compatible[:can_call_count]]
                
                # Trouver les dépendances
                for other in self.services:
                    if other.id != service.id:
                        if any(inp in other.outputs for inp in service.inputs):
                            interaction.depends_on.append(other.id)
                
                # Simuler l'historique
                interaction.collaboration_history = {
                    svc_id: random.randint(1, 100)
                    for svc_id in interaction.can_call[:5]
                }
            else:
                # Fallback à la méthode classique
                interaction = self._generate_interaction_annotations(service)
        
        except Exception as e:
            print(f"LLM error for interaction: {e}")
            interaction = self._generate_interaction_annotations(service)
        
        return interaction
    
    def _llm_generate_context(self, service, context):
        """Génère les annotations de contexte avec le LLM"""
        ctx = ContextAnnotation()
        
        prompt = f"""Analyze this web service's contextual characteristics:

Service: {service.id}
QoS Metrics:
- Availability: {service.qos.availability}%
- Response Time: {service.qos.response_time}ms
- Reliability: {service.qos.reliability}%

Respond ONLY with JSON (no markdown):
{{
  "context_aware": true or false,
  "location_sensitive": true or false,
  "time_critical": "high" or "medium" or "low",
  "usage_frequency": "high" or "medium" or "low"
}}
"""
        
        try:
            response = self._call_ollama(prompt)
            data = self._extract_json(response)
            
            if data:
                ctx.context_aware = data.get('context_aware', False)
                ctx.location_sensitive = data.get('location_sensitive', False)
                ctx.time_critical = data.get('time_critical', 'medium')
                
                # Déterminer le nombre d'interactions basé sur la fréquence
                freq = data.get('usage_frequency', 'medium')
                if freq == 'high':
                    ctx.interaction_count = random.randint(200, 500)
                elif freq == 'medium':
                    ctx.interaction_count = random.randint(50, 200)
                else:
                    ctx.interaction_count = random.randint(10, 50)
                
                ctx.usage_patterns = ["peak_hours_morning", "business_days"]
                
                if service.qos.compliance > 80:
                    ctx.environmental_requirements = ["secure_network", "vpn"]
            else:
                ctx = self._generate_context_annotations(service)
        
        except Exception as e:
            print(f"LLM error for context: {e}")
            ctx = self._generate_context_annotations(service)
        
        return ctx
    
    def _llm_generate_policy(self, service, context):
        """Génère les annotations de politiques avec le LLM"""
        policy = PolicyAnnotation()
        
        prompt = f"""Analyze this web service's policy and compliance requirements:

Service: {service.id}
QoS Compliance Score: {service.qos.compliance}%
QoS Best Practices: {service.qos.best_practices}%
Reliability: {service.qos.reliability}%

Respond ONLY with JSON (no markdown):
{{
  "gdpr_compliant": true or false,
  "security_level": "high" or "medium" or "low",
  "data_retention_days": 30 or 60 or 90 or 180 or 365,
  "encryption_required": true or false,
  "data_classification": "public" or "internal" or "confidential"
}}
"""
        
        try:
            response = self._call_ollama(prompt)
            data = self._extract_json(response)
            
            if data:
                policy.gdpr_compliant = data.get('gdpr_compliant', True)
                policy.security_level = data.get('security_level', 'medium')
                policy.data_retention_days = data.get('data_retention_days', 30)
                policy.encryption_required = data.get('encryption_required', False)
                policy.data_classification = data.get('data_classification', 'internal')
                
                policy.privacy_policy = "encrypted" if policy.encryption_required else "standard"
                
                if service.qos.compliance > 85:
                    policy.compliance_standards = ["ISO27001", "SOC2"]
                elif service.qos.compliance > 70:
                    policy.compliance_standards = ["ISO27001"]
                else:
                    policy.compliance_standards = []
            else:
                policy = self._generate_policy_annotations(service)
        
        except Exception as e:
            print(f"LLM error for policy: {e}")
            policy = self._generate_policy_annotations(service)
        
        return policy
    
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
            raise Exception("Cannot connect to Ollama. Is it running?")
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
            
            return None
        except:
            return None
    
    def annotate_all(self, service_ids=None, use_llm=False, annotation_types=None, progress_callback=None):
        """
        Annote les services sélectionnés
        
        Args:
            service_ids: Liste des IDs de services à annoter (None = tous)
            use_llm: Utiliser le LLM
            annotation_types: Types d'annotations à générer
            progress_callback: Callback pour la progression
        
        Returns:
            Liste des services annotés
        """
        if annotation_types is None:
            annotation_types = ['interaction', 'context', 'policy']
        
        # Sélectionner les services à annoter
        if service_ids:
            services_to_annotate = [s for s in self.services if s.id in service_ids]
        else:
            services_to_annotate = self.services
        
        total = len(services_to_annotate)
        annotated = []
        
        for i, service in enumerate(services_to_annotate):
            self.annotate_service(service, use_llm=use_llm, annotation_types=annotation_types)
            annotated.append(service)
            
            if progress_callback:
                progress_callback(i + 1, total, service.id)
        
        return annotated
    
    def _generate_interaction_annotations(self, service):
        """Génère les annotations d'interaction"""
        interaction = InteractionAnnotation()
        
        # Trouver les services qui peuvent être appelés
        # (ceux dont les inputs sont dans nos outputs)
        for other in self.services:
            if other.id == service.id:
                continue
            
            # Peut appeler si nos outputs matchent ses inputs
            if any(out in other.inputs for out in service.outputs):
                interaction.can_call.append(other.id)
            
            # Dépend de si nos inputs viennent de ses outputs
            if any(inp in other.outputs for inp in service.inputs):
                interaction.depends_on.append(other.id)
        
        # Déterminer le rôle
        if len(interaction.can_call) > 3:
            interaction.role = "orchestrator"
        elif len(interaction.depends_on) > 3:
            interaction.role = "aggregator"
        else:
            interaction.role = "worker"
        
        # Simuler un historique de collaboration
        interaction.collaboration_history = {
            svc_id: random.randint(1, 100)
            for svc_id in interaction.can_call[:5]
        }
        
        # Trouver des substituts (services avec outputs similaires)
        for other in self.services:
            if other.id == service.id:
                continue
            
            common_outputs = set(service.outputs) & set(other.outputs)
            if len(common_outputs) >= len(service.outputs) * 0.7:  # 70% de similarité
                interaction.substitutes.append(other.id)
        
        return interaction
    
    def _generate_context_annotations(self, service):
        """Génère les annotations de contexte"""
        context = ContextAnnotation()
        
        # Déterminer le contexte basé sur les QoS et les paramètres
        context.context_aware = service.qos.availability > 95
        context.location_sensitive = random.choice([True, False])
        
        # Criticité basée sur le temps de réponse
        if service.qos.response_time < 50:
            context.time_critical = "low"
        elif service.qos.response_time < 200:
            context.time_critical = "medium"
        else:
            context.time_critical = "high"
        
        # Simuler l'historique d'utilisation
        context.interaction_count = random.randint(10, 500)
        
        # Patterns d'utilisation
        context.usage_patterns = [
            "peak_hours_morning",
            "business_days",
            "batch_processing"
        ]
        
        # Exigences environnementales
        if service.qos.compliance > 80:
            context.environmental_requirements = ["secure_network", "vpn"]
        
        return context
    
    def _generate_policy_annotations(self, service):
        """Génère les annotations de politiques"""
        policy = PolicyAnnotation()
        
        # Conformité GDPR basée sur le niveau de compliance
        policy.gdpr_compliant = service.qos.compliance > 70
        
        # Rétention des données
        policy.data_retention_days = random.choice([30, 60, 90, 180, 365])
        
        # Niveau de sécurité basé sur les QoS
        if service.qos.reliability > 90:
            policy.security_level = "high"
        elif service.qos.reliability > 70:
            policy.security_level = "medium"
        else:
            policy.security_level = "low"
        
        # Politique de confidentialité
        policy.privacy_policy = random.choice([
            "encrypted",
            "anonymized",
            "encrypted_and_anonymized"
        ])
        
        # Standards de conformité
        if service.qos.compliance > 85:
            policy.compliance_standards = ["ISO27001", "SOC2"]
        elif service.qos.compliance > 70:
            policy.compliance_standards = ["ISO27001"]
        
        # Classification des données
        if service.qos.compliance > 85:
            policy.data_classification = "confidential"
        elif service.qos.compliance > 70:
            policy.data_classification = "internal"
        else:
            policy.data_classification = "public"
        
        policy.encryption_required = policy.security_level == "high"
        
        return policy
    
    def _calculate_trust(self, service):
        """Calcule le degré de confiance basé sur les QoS"""
        # Moyenne pondérée des QoS
        trust = (
            service.qos.reliability * 0.3 +
            service.qos.successability * 0.3 +
            service.qos.availability * 0.2 +
            service.qos.compliance * 0.2
        ) / 100.0
        
        return min(max(trust, 0.0), 1.0)
    
    def _calculate_reputation(self, service):
        """Calcule la réputation basée sur les QoS et les best practices"""
        reputation = (
            service.qos.best_practices * 0.4 +
            service.qos.documentation * 0.3 +
            service.qos.compliance * 0.3
        ) / 100.0
        
        return min(max(reputation, 0.0), 1.0)
    
    def _find_collaborations(self, service):
        """Trouve les poids de collaboration avec d'autres services"""
        collaborations = {}
        
        for other in self.services:
            if other.id == service.id:
                continue
            
            # Calculer un poids de collaboration basé sur la compatibilité
            weight = self._calculate_collaboration_weight(service, other)
            
            if weight > 0.3:  # Seuil minimum
                collaborations[other.id] = weight
        
        # Garder seulement les top 10
        sorted_collab = sorted(collaborations.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_collab[:10])
    
    def _calculate_collaboration_weight(self, service1, service2):
        """Calcule le poids de collaboration entre deux services"""
        # Compatibilité des inputs/outputs
        io_match = len(set(service1.outputs) & set(service2.inputs)) / max(len(service2.inputs), 1)
        
        # Similarité des QoS
        qos_similarity = 1 - abs(service1.qos.reliability - service2.qos.reliability) / 100
        
        # Poids final
        weight = (io_match * 0.7 + qos_similarity * 0.3)
        
        return weight
    
    def _calculate_robustness(self, service):
        """Calcule le score de robustesse"""
        robustness = (
            service.qos.reliability * 0.4 +
            service.qos.availability * 0.3 +
            service.qos.successability * 0.3
        ) / 100.0
        
        return min(max(robustness, 0.0), 1.0)