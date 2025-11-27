"""
annotation_system/annotation_generator.py
Génère automatiquement les annotations à partir des WSDL en utilisant un LLM
"""
import json
import sys
import os
from typing import Dict, Optional
from datetime import datetime
import uuid

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from annotation_system.wsdl_parser import WSDLParser
from annotation_system.ollama_client import OllamaClient
from models.annotation_model import (
    ServiceAnnotation, FunctionalAnnotation, InteractionAnnotation,
    ContextAnnotation, PolicyAnnotation, ServiceCategory, PrivacyLevel,
    UsagePolicy, DataPrivacyPolicy, ParameterMapping
)


class AnnotationGenerator:
    """Génère automatiquement des annotations pour les services web"""
    
    def __init__(self, ollama_model: str = "llama3.2"):
        """
        Initialise le générateur d'annotations
        
        Args:
            ollama_model: Nom du modèle Ollama à utiliser
        """
        self.llm_client = OllamaClient(model=ollama_model)
        
        # Vérifier la connexion
        if not self.llm_client.check_connection():
            raise ConnectionError("Impossible de se connecter à Ollama. Lancez 'ollama serve'")
    
    def generate_annotation(self, wsdl_path: str) -> Optional[ServiceAnnotation]:
        """
        Génère une annotation complète pour un service WSDL
        
        Args:
            wsdl_path: Chemin vers le fichier WSDL
            
        Returns:
            ServiceAnnotation complète ou None en cas d'échec
        """
        print(f"\n{'='*80}")
        print(f"Génération d'annotations pour: {os.path.basename(wsdl_path)}")
        print(f"{'='*80}\n")
        
        # 1. Parser le WSDL
        print("Parsing du WSDL...")
        try:
            parser = WSDLParser(wsdl_path)
            wsdl_data = parser.extract_for_llm()
            print(f"   Service: {wsdl_data['service_name']}")
            print(f"   Opérations: {len(wsdl_data['operations'])}")
        except Exception as e:
            print(f"   Erreur de parsing: {e}")
            return None
        
        # 2. Générer les annotations via LLM
        print("\n2️⃣ Génération des annotations avec le LLM...")
        
        annotation = ServiceAnnotation(
            annotation_id=str(uuid.uuid4()),
            service_name=wsdl_data['service_name'],
            wsdl_location=wsdl_path,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Générer chaque type d'annotation
        self._generate_functional_annotation(annotation, wsdl_data)
        self._generate_interaction_annotation(annotation, wsdl_data)
        self._generate_context_annotation(annotation, wsdl_data)
        self._generate_policy_annotation(annotation, wsdl_data)
        
        print("\nAnnotation complète générée avec succès!")
        return annotation
    
    def _generate_functional_annotation(self, annotation: ServiceAnnotation, 
                                       wsdl_data: Dict) -> None:
        """Génère l'annotation fonctionnelle"""
        print("\n   Annotation fonctionnelle...")
        
        prompt = f"""You are analyzing a web service to extract its functional capabilities.

Service Information:
{json.dumps(wsdl_data, indent=2)}

Analyze this service and provide a JSON response with:
{{
  "service_category": "one of: search, booking, payment, information, notification",
  "capabilities": ["list of functional capabilities this service provides"],
  "semantic_description": "clear description of what this service does",
  "keywords": ["list of relevant keywords"],
  "special_features": {{"key": "value pairs of special features"}}
}}

Important:
- Be precise and technical
- Extract real capabilities from the operations
- Keywords should be searchable terms
- Special features are unique aspects (e.g., supports_multi_currency, loyalty_points)
"""
        
        system_prompt = """You are an expert in web services and SOA architecture. 
Your task is to analyze WSDL services and extract structured functional information.
Always respond with valid JSON only."""
        
        result = self.llm_client.generate_with_retry(prompt, system_prompt)
        
        if result:
            try:
                annotation.functional.service_category = ServiceCategory(result.get("service_category", "search"))
                annotation.functional.capabilities = result.get("capabilities", [])
                annotation.functional.semantic_description = result.get("semantic_description", "")
                annotation.functional.keywords = result.get("keywords", [])
                annotation.functional.special_features = result.get("special_features", {})
                
                # Extraire input/output des opérations
                for op in wsdl_data.get("operations", []):
                    annotation.functional.input_parameters.extend([p["name"] for p in op.get("input_parameters", [])])
                    annotation.functional.output_parameters.extend([p["name"] for p in op.get("output_parameters", [])])
                
                print(f"      Catégorie: {annotation.functional.service_category.value}")
                print(f"      Capacités: {len(annotation.functional.capabilities)}")
            except Exception as e:
                print(f"      Erreur lors du traitement: {e}")
        else:
            print(f"      Échec de génération")
    
    def _generate_interaction_annotation(self, annotation: ServiceAnnotation, 
                                        wsdl_data: Dict) -> None:
        """Génère l'annotation d'interaction"""
        print("\n   Annotation d'interaction...")
        
        prompt = f"""You are analyzing how this web service interacts with other services.

Service: {wsdl_data['service_name']}
Category: {annotation.functional.service_category.value}
Operations: {json.dumps([op['name'] for op in wsdl_data['operations']])}

Based on the service type, provide a JSON response with:
{{
  "requires_services": ["list of service types this service needs BEFORE execution"],
  "provides_for_services": ["list of service types that can use this service's output"],
  "compatible_services": ["list of service types that are compatible"],
  "quality_metrics": {{
    "estimated_response_time_ms": 1000,
    "estimated_cost_per_call": 0.01,
    "typical_success_rate": 0.95
  }}
}}

Examples:
- A flight search service REQUIRES: none, PROVIDES_FOR: booking services, payment services
- A payment service REQUIRES: booking confirmation, PROVIDES_FOR: notification services
- A hotel search REQUIRES: none, PROVIDES_FOR: booking services, payment services

Be logical about service dependencies in a travel booking workflow.
"""
        
        system_prompt = """You are an expert in service composition and orchestration.
Analyze service dependencies and interactions. Respond with valid JSON only."""
        
        result = self.llm_client.generate_with_retry(prompt, system_prompt)
        
        if result:
            try:
                annotation.interaction.requires_services = result.get("requires_services", [])
                annotation.interaction.provides_for_services = result.get("provides_for_services", [])
                annotation.interaction.compatible_services = result.get("compatible_services", [])
                
                # Metrics
                metrics = result.get("quality_metrics", {})
                annotation.interaction.quality_metrics.response_time_ms = metrics.get("estimated_response_time_ms", 1000)
                annotation.interaction.quality_metrics.cost_per_call = metrics.get("estimated_cost_per_call", 0.0)
                annotation.interaction.quality_metrics.success_rate = metrics.get("typical_success_rate", 0.95)
                
                print(f"      Requires: {annotation.interaction.requires_services}")
                print(f"      Provides for: {annotation.interaction.provides_for_services}")
            except Exception as e:
                print(f"      Erreur lors du traitement: {e}")
        else:
            print(f"      Échec de génération")
    
    def _generate_context_annotation(self, annotation: ServiceAnnotation, 
                                     wsdl_data: Dict) -> None:
        """Génère l'annotation de contexte"""
        print("\n   Annotation de contexte...")
        
        service_name = wsdl_data['service_name']
        
        prompt = f"""Analyze the contextual requirements for this service: {service_name}

Provide a JSON response with:
{{
  "geographic_coverage": ["list of regions: GLOBAL, EU, US, ASIA, etc."],
  "location_aware": true/false,
  "temporal_constraints": ["e.g., business_hours_only, 24/7_available"],
  "timezone_support": true/false,
  "adaptation_capabilities": ["e.g., auto_retry, fallback_available, caching_enabled"]
}}

Consider:
- Major travel APIs typically have GLOBAL coverage
- Payment services need 24/7 availability
- Search services benefit from caching
"""
        
        system_prompt = """You are analyzing service context requirements.
Provide realistic contextual constraints. Respond with valid JSON only."""
        
        result = self.llm_client.generate_with_retry(prompt, system_prompt)
        
        if result:
            try:
                annotation.context.geographic_coverage = result.get("geographic_coverage", ["GLOBAL"])
                annotation.context.location_aware = result.get("location_aware", False)
                annotation.context.temporal_constraints = result.get("temporal_constraints", [])
                annotation.context.timezone_support = result.get("timezone_support", True)
                annotation.context.adaptation_capabilities = result.get("adaptation_capabilities", [])
                
                print(f"      Coverage: {annotation.context.geographic_coverage}")
                print(f"      Location aware: {annotation.context.location_aware}")
            except Exception as e:
                print(f"      Erreur lors du traitement: {e}")
        else:
            print(f"      Échec de génération")
    
    def _generate_policy_annotation(self, annotation: ServiceAnnotation, 
                                    wsdl_data: Dict) -> None:
        """Génère l'annotation de politique"""
        print("\n   🔒 Annotation de politique...")
        
        service_name = wsdl_data['service_name']
        category = annotation.functional.service_category.value
        
        prompt = f"""Analyze security and policy requirements for: {service_name} (category: {category})

Provide a JSON response with:
{{
  "usage_policy": {{
    "rate_limit": 1000,
    "pricing_model": "free/subscription/pay_per_use",
    "cost_per_request": 0.01,
    "guaranteed_uptime": 0.99
  }},
  "security_requirements": ["e.g., TLS_1.3, API_KEY, OAUTH2"],
  "compliance_standards": ["e.g., GDPR, PCI-DSS, SOC2"],
  "sensitive_data_fields": ["list of field names that contain sensitive data"]
}}

Consider:
- Payment services MUST have PCI-DSS
- All services handling personal data need GDPR compliance
- Travel booking services handle passport info (sensitive)
"""
        
        system_prompt = """You are a security and compliance expert.
Analyze service policies and requirements. Respond with valid JSON only."""
        
        result = self.llm_client.generate_with_retry(prompt, system_prompt)
        
        if result:
            try:
                usage = result.get("usage_policy", {})
                annotation.policy.usage_policy.rate_limit = usage.get("rate_limit", 1000)
                annotation.policy.usage_policy.pricing_model = usage.get("pricing_model", "pay_per_use")
                annotation.policy.usage_policy.cost_per_request = usage.get("cost_per_request", 0.0)
                annotation.policy.usage_policy.guaranteed_uptime = usage.get("guaranteed_uptime", 0.99)
                
                annotation.policy.security_requirements = result.get("security_requirements", [])
                annotation.policy.compliance_standards = result.get("compliance_standards", [])
                
                # Créer des policies pour les données sensibles
                for field in result.get("sensitive_data_fields", []):
                    policy = DataPrivacyPolicy(
                        data_field=field,
                        privacy_level=PrivacyLevel.CONFIDENTIAL,
                        retention_days=90,
                        encryption_required=True,
                        can_be_shared=False,
                        compliance_requirements=annotation.policy.compliance_standards
                    )
                    annotation.policy.privacy_policies.append(policy)
                
                print(f"      Pricing: {annotation.policy.usage_policy.pricing_model}")
                print(f"      Compliance: {annotation.policy.compliance_standards}")
                print(f"      Sensitive fields: {len(annotation.policy.privacy_policies)}")
            except Exception as e:
                print(f"    Erreur lors du traitement: {e}")
        else:
            print(f"     Échec de génération")


# Script principal pour tester
if __name__ == "__main__":
    print("Test du Générateur d'Annotations\n")
    
    # Créer le générateur
    try:
        generator = AnnotationGenerator(ollama_model="llama3.2:3b")
    except ConnectionError as e:
        print(f"{e}")
        exit(1)
    
    # Tester avec un service
    wsdl_file = "services/wsdl/original/AmadeusFlightService.wsdl"
    
    if not os.path.exists(wsdl_file):
        print(f"Fichier non trouvé: {wsdl_file}")
        print("   Assurez-vous d'avoir créé les fichiers WSDL d'abord")
        exit(1)
    
    # Générer l'annotation
    annotation = generator.generate_annotation(wsdl_file)
    
    if annotation:
        # Sauvegarder en JSON
        output_file = "services/wsdl/annotated/AmadeusFlightService_annotated.json"
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(annotation.to_dict(), f, indent=2, ensure_ascii=False)
        
        print(f"\nAnnotation sauvegardée: {output_file}")
        print(f"\nStatistiques:")
        print(f"   - Capabilities: {len(annotation.functional.capabilities)}")
        print(f"   - Compatible services: {len(annotation.interaction.compatible_services)}")
        print(f"   - Privacy policies: {len(annotation.policy.privacy_policies)}")