"""
annotation_system/separate_annotation_generator.py
Génère chaque type d'annotation de manière SÉPARÉE et INDÉPENDANTE
"""
import json
import sys
import os
from typing import Dict, Optional
from datetime import datetime
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from annotation_system.wsdl_parser import WSDLParser
from annotation_system.ollama_client import OllamaClient
from models.annotation_model import (
    ServiceAnnotation, FunctionalAnnotation, InteractionAnnotation,
    ContextAnnotation, PolicyAnnotation, ServiceCategory, PrivacyLevel,
    UsagePolicy, DataPrivacyPolicy
)


class SeparateAnnotationGenerator:
    """
    Génère chaque type d'annotation SÉPARÉMENT
    Permet de valider et modifier chaque annotation indépendamment
    """
    
    def __init__(self, ollama_model: str = "llama3.2:3b"):
        """
        Initialise le générateur d'annotations séparées
        
        Args:
            ollama_model: Nom du modèle Ollama à utiliser
        """
        self.llm_client = OllamaClient(model=ollama_model)
        
        # Vérifier la connexion
        if not self.llm_client.check_connection():
            raise ConnectionError("Impossible de se connecter à Ollama. Lancez 'ollama serve'")
    
    def generate_functional_annotation(self, wsdl_path: str) -> Optional[FunctionalAnnotation]:
        """
        Génère UNIQUEMENT l'annotation fonctionnelle
        
        Args:
            wsdl_path: Chemin vers le fichier WSDL
            
        Returns:
            FunctionalAnnotation ou None
        """
        print("\n" + "="*80)
        print("GÉNÉRATION ANNOTATION FONCTIONNELLE")
        print("="*80)
        
        # Parser le WSDL
        print(f"\n📄 Parsing du WSDL: {os.path.basename(wsdl_path)}")
        try:
            parser = WSDLParser(wsdl_path)
            wsdl_data = parser.extract_for_llm()
            print(f"   ✓ Service: {wsdl_data['service_name']}")
            print(f"   ✓ Opérations: {len(wsdl_data['operations'])}")
        except Exception as e:
            print(f"   ✗ Erreur de parsing: {e}")
            return None
        
        print("\n🤖 Génération avec LLM...")
        
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
        
        if not result:
            print("   ✗ Échec de génération")
            return None
        
        # Créer l'annotation
        annotation = FunctionalAnnotation()
        
        try:
            annotation.service_category = ServiceCategory(result.get("service_category", "search"))
            annotation.capabilities = result.get("capabilities", [])
            annotation.semantic_description = result.get("semantic_description", "")
            annotation.keywords = result.get("keywords", [])
            annotation.special_features = result.get("special_features", {})
            
            # Extraire input/output des opérations
            for op in wsdl_data.get("operations", []):
                annotation.input_parameters.extend([p["name"] for p in op.get("input_parameters", [])])
                annotation.output_parameters.extend([p["name"] for p in op.get("output_parameters", [])])
            
            print(f"\n✓ Annotation fonctionnelle générée:")
            print(f"   • Catégorie: {annotation.service_category.value}")
            print(f"   • Capacités: {len(annotation.capabilities)}")
            print(f"   • Keywords: {len(annotation.keywords)}")
            
            return annotation
            
        except Exception as e:
            print(f"   ✗ Erreur lors du traitement: {e}")
            return None
    
    def generate_interaction_annotation(self, wsdl_path: str, 
                                       functional_annotation: Optional[FunctionalAnnotation] = None) -> Optional[InteractionAnnotation]:
        """
        Génère UNIQUEMENT l'annotation d'interaction
        
        Args:
            wsdl_path: Chemin vers le fichier WSDL
            functional_annotation: Annotation fonctionnelle (optionnelle, pour contexte)
            
        Returns:
            InteractionAnnotation ou None
        """
        print("\n" + "="*80)
        print("GÉNÉRATION ANNOTATION D'INTERACTION")
        print("="*80)
        
        # Parser le WSDL
        print(f"\n📄 Parsing du WSDL: {os.path.basename(wsdl_path)}")
        try:
            parser = WSDLParser(wsdl_path)
            wsdl_data = parser.extract_for_llm()
        except Exception as e:
            print(f"   ✗ Erreur de parsing: {e}")
            return None
        
        # Utiliser l'annotation fonctionnelle si disponible
        service_category = "unknown"
        if functional_annotation:
            service_category = functional_annotation.service_category.value
            print(f"   ℹ️  Utilisation de la catégorie: {service_category}")
        
        print("\n🤖 Génération avec LLM...")
        
        prompt = f"""You are analyzing how this web service interacts with other services.

Service: {wsdl_data['service_name']}
Category: {service_category}
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
        
        if not result:
            print("   ✗ Échec de génération")
            return None
        
        # Créer l'annotation
        annotation = InteractionAnnotation()
        
        try:
            annotation.requires_services = result.get("requires_services", [])
            annotation.provides_for_services = result.get("provides_for_services", [])
            annotation.compatible_services = result.get("compatible_services", [])
            
            # Metrics
            metrics = result.get("quality_metrics", {})
            annotation.quality_metrics.response_time_ms = metrics.get("estimated_response_time_ms", 1000)
            annotation.quality_metrics.cost_per_call = metrics.get("estimated_cost_per_call", 0.0)
            annotation.quality_metrics.success_rate = metrics.get("typical_success_rate", 0.95)
            
            print(f"\n✓ Annotation d'interaction générée:")
            print(f"   • Requires: {annotation.requires_services}")
            print(f"   • Provides for: {annotation.provides_for_services}")
            print(f"   • Response time: {annotation.quality_metrics.response_time_ms}ms")
            
            return annotation
            
        except Exception as e:
            print(f"   ✗ Erreur lors du traitement: {e}")
            return None
    
    def generate_context_annotation(self, wsdl_path: str) -> Optional[ContextAnnotation]:
        """
        Génère UNIQUEMENT l'annotation de contexte
        
        Args:
            wsdl_path: Chemin vers le fichier WSDL
            
        Returns:
            ContextAnnotation ou None
        """
        print("\n" + "="*80)
        print("GÉNÉRATION ANNOTATION DE CONTEXTE")
        print("="*80)
        
        # Parser le WSDL
        print(f"\n📄 Parsing du WSDL: {os.path.basename(wsdl_path)}")
        try:
            parser = WSDLParser(wsdl_path)
            wsdl_data = parser.extract_for_llm()
        except Exception as e:
            print(f"   ✗ Erreur de parsing: {e}")
            return None
        
        service_name = wsdl_data['service_name']
        
        print("\n🤖 Génération avec LLM...")
        
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
        
        if not result:
            print("   ✗ Échec de génération")
            return None
        
        # Créer l'annotation
        annotation = ContextAnnotation()
        
        try:
            annotation.geographic_coverage = result.get("geographic_coverage", ["GLOBAL"])
            annotation.location_aware = result.get("location_aware", False)
            annotation.temporal_constraints = result.get("temporal_constraints", [])
            annotation.timezone_support = result.get("timezone_support", True)
            annotation.adaptation_capabilities = result.get("adaptation_capabilities", [])
            
            print(f"\n✓ Annotation de contexte générée:")
            print(f"   • Coverage: {annotation.geographic_coverage}")
            print(f"   • Location aware: {annotation.location_aware}")
            print(f"   • Temporal: {annotation.temporal_constraints}")
            
            return annotation
            
        except Exception as e:
            print(f"   ✗ Erreur lors du traitement: {e}")
            return None
    
    def generate_policy_annotation(self, wsdl_path: str,
                                   functional_annotation: Optional[FunctionalAnnotation] = None) -> Optional[PolicyAnnotation]:
        """
        Génère UNIQUEMENT l'annotation de politique
        
        Args:
            wsdl_path: Chemin vers le fichier WSDL
            functional_annotation: Annotation fonctionnelle (optionnelle, pour contexte)
            
        Returns:
            PolicyAnnotation ou None
        """
        print("\n" + "="*80)
        print("GÉNÉRATION ANNOTATION DE POLITIQUE")
        print("="*80)
        
        # Parser le WSDL
        print(f"\n📄 Parsing du WSDL: {os.path.basename(wsdl_path)}")
        try:
            parser = WSDLParser(wsdl_path)
            wsdl_data = parser.extract_for_llm()
        except Exception as e:
            print(f"   ✗ Erreur de parsing: {e}")
            return None
        
        service_name = wsdl_data['service_name']
        service_category = "unknown"
        if functional_annotation:
            service_category = functional_annotation.service_category.value
            print(f"   ℹ️  Utilisation de la catégorie: {service_category}")
        
        print("\n🤖 Génération avec LLM...")
        
        prompt = f"""Analyze security and policy requirements for: {service_name} (category: {service_category})

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
        
        if not result:
            print("   ✗ Échec de génération")
            return None
        
        # Créer l'annotation
        annotation = PolicyAnnotation()
        
        try:
            usage = result.get("usage_policy", {})
            annotation.usage_policy.rate_limit = usage.get("rate_limit", 1000)
            annotation.usage_policy.pricing_model = usage.get("pricing_model", "pay_per_use")
            annotation.usage_policy.cost_per_request = usage.get("cost_per_request", 0.0)
            annotation.usage_policy.guaranteed_uptime = usage.get("guaranteed_uptime", 0.99)
            
            annotation.security_requirements = result.get("security_requirements", [])
            annotation.compliance_standards = result.get("compliance_standards", [])
            
            # Créer des policies pour les données sensibles
            for field in result.get("sensitive_data_fields", []):
                policy = DataPrivacyPolicy(
                    data_field=field,
                    privacy_level=PrivacyLevel.CONFIDENTIAL,
                    retention_days=90,
                    encryption_required=True,
                    can_be_shared=False,
                    compliance_requirements=annotation.compliance_standards
                )
                annotation.privacy_policies.append(policy)
            
            print(f"\n✓ Annotation de politique générée:")
            print(f"   • Pricing: {annotation.usage_policy.pricing_model}")
            print(f"   • Compliance: {annotation.compliance_standards}")
            print(f"   • Sensitive fields: {len(annotation.privacy_policies)}")
            
            return annotation
            
        except Exception as e:
            print(f"   ✗ Erreur lors du traitement: {e}")
            return None
    
    def save_annotation(self, annotation: any, annotation_type: str, 
                       service_name: str, output_dir: str = "services/wsdl/annotated/separate"):
        """
        Sauvegarde une annotation individuelle
        
        Args:
            annotation: L'annotation à sauvegarder
            annotation_type: Type (functional, interaction, context, policy)
            service_name: Nom du service
            output_dir: Répertoire de sortie
        """
        os.makedirs(output_dir, exist_ok=True)
        
        filename = f"{service_name}_{annotation_type}.json"
        filepath = os.path.join(output_dir, filename)
        
        # Convertir en dict
        annotation_dict = self._annotation_to_dict(annotation)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(annotation_dict, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Annotation sauvegardée: {filepath}")
    
    def _annotation_to_dict(self, annotation) -> Dict:
        """Convertit une annotation en dictionnaire"""
        if hasattr(annotation, '__dataclass_fields__'):
            result = {}
            for field_name in annotation.__dataclass_fields__:
                value = getattr(annotation, field_name)
                if hasattr(value, '__dataclass_fields__'):
                    result[field_name] = self._annotation_to_dict(value)
                elif isinstance(value, list):
                    result[field_name] = [
                        self._annotation_to_dict(item) if hasattr(item, '__dataclass_fields__') else item
                        for item in value
                    ]
                elif hasattr(value, 'value'):  # Enum
                    result[field_name] = value.value
                else:
                    result[field_name] = value
            return result
        return annotation
    
    def combine_annotations(self, service_name: str, wsdl_path: str,
                           input_dir: str = "services/wsdl/annotated/separate",
                           output_dir: str = "services/wsdl/annotated") -> Optional[ServiceAnnotation]:
        """
        Combine toutes les annotations séparées en une annotation complète
        
        Args:
            service_name: Nom du service
            wsdl_path: Chemin vers le WSDL
            input_dir: Répertoire des annotations séparées
            output_dir: Répertoire de sortie pour l'annotation complète
            
        Returns:
            ServiceAnnotation complète ou None
        """
        print("\n" + "="*80)
        print(f"COMBINAISON DES ANNOTATIONS - {service_name}")
        print("="*80)
        
        # Créer l'annotation complète
        annotation = ServiceAnnotation(
            annotation_id=str(uuid.uuid4()),
            service_name=service_name,
            wsdl_location=wsdl_path,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Charger chaque type d'annotation
        annotation_types = ['functional', 'interaction', 'context', 'policy']
        loaded = {}
        
        for ann_type in annotation_types:
            filepath = os.path.join(input_dir, f"{service_name}_{ann_type}.json")
            
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    loaded[ann_type] = data
                    print(f"   ✓ Chargé: {ann_type}")
            else:
                print(f"   ✗ Manquant: {ann_type}")
                return None
        
        # Reconstruire les annotations
        try:
            # Functional
            func_data = loaded['functional']
            annotation.functional.service_category = ServiceCategory(func_data['service_category'])
            annotation.functional.capabilities = func_data['capabilities']
            annotation.functional.semantic_description = func_data['semantic_description']
            annotation.functional.keywords = func_data['keywords']
            annotation.functional.special_features = func_data['special_features']
            annotation.functional.input_parameters = func_data['input_parameters']
            annotation.functional.output_parameters = func_data['output_parameters']
            
            # Interaction
            inter_data = loaded['interaction']
            annotation.interaction.requires_services = inter_data['requires_services']
            annotation.interaction.provides_for_services = inter_data['provides_for_services']
            annotation.interaction.compatible_services = inter_data['compatible_services']
            annotation.interaction.quality_metrics.response_time_ms = inter_data['quality_metrics']['response_time_ms']
            annotation.interaction.quality_metrics.cost_per_call = inter_data['quality_metrics']['cost_per_call']
            annotation.interaction.quality_metrics.success_rate = inter_data['quality_metrics']['success_rate']
            
            # Context
            ctx_data = loaded['context']
            annotation.context.geographic_coverage = ctx_data['geographic_coverage']
            annotation.context.location_aware = ctx_data['location_aware']
            annotation.context.temporal_constraints = ctx_data['temporal_constraints']
            annotation.context.timezone_support = ctx_data['timezone_support']
            annotation.context.adaptation_capabilities = ctx_data['adaptation_capabilities']
            
            # Policy
            pol_data = loaded['policy']
            annotation.policy.usage_policy.rate_limit = pol_data['usage_policy']['rate_limit']
            annotation.policy.usage_policy.pricing_model = pol_data['usage_policy']['pricing_model']
            annotation.policy.usage_policy.cost_per_request = pol_data['usage_policy']['cost_per_request']
            annotation.policy.usage_policy.guaranteed_uptime = pol_data['usage_policy']['guaranteed_uptime']
            annotation.policy.security_requirements = pol_data['security_requirements']
            annotation.policy.compliance_standards = pol_data['compliance_standards']
            
            # Privacy policies
            for priv_data in pol_data['privacy_policies']:
                policy = DataPrivacyPolicy(
                    data_field=priv_data['data_field'],
                    privacy_level=PrivacyLevel(priv_data['privacy_level']),
                    retention_days=priv_data['retention_days'],
                    encryption_required=priv_data['encryption_required'],
                    can_be_shared=priv_data['can_be_shared'],
                    compliance_requirements=priv_data['compliance_requirements']
                )
                annotation.policy.privacy_policies.append(policy)
            
            print("\n✓ Annotations combinées avec succès")
            
            # Sauvegarder l'annotation complète
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{service_name}_annotated.json")
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(annotation.to_dict(), f, indent=2, ensure_ascii=False)
            
            print(f"💾 Annotation complète sauvegardée: {output_file}")
            
            return annotation
            
        except Exception as e:
            print(f"\n✗ Erreur lors de la combinaison: {e}")
            return None


# Script de démonstration
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Génération d'annotations séparées")
    parser.add_argument("--wsdl", type=str, required=True, help="Chemin vers le fichier WSDL")
    parser.add_argument("--type", type=str, choices=['functional', 'interaction', 'context', 'policy', 'all'],
                       default='all', help="Type d'annotation à générer")
    parser.add_argument("--model", type=str, default="llama3.2:3b", help="Modèle Ollama")
    parser.add_argument("--combine", action='store_true', help="Combiner les annotations existantes")
    
    args = parser.parse_args()
    
    try:
        generator = SeparateAnnotationGenerator(ollama_model=args.model)
    except ConnectionError as e:
        print(f"\n✗ {e}")
        exit(1)
    
    service_name = os.path.basename(args.wsdl).replace('.wsdl', '')
    
    if args.combine:
        # Combiner les annotations existantes
        generator.combine_annotations(service_name, args.wsdl)
    else:
        # Générer les annotations
        if args.type in ['functional', 'all']:
            func_ann = generator.generate_functional_annotation(args.wsdl)
            if func_ann:
                generator.save_annotation(func_ann, 'functional', service_name)
        
        if args.type in ['interaction', 'all']:
            inter_ann = generator.generate_interaction_annotation(args.wsdl)
            if inter_ann:
                generator.save_annotation(inter_ann, 'interaction', service_name)
        
        if args.type in ['context', 'all']:
            ctx_ann = generator.generate_context_annotation(args.wsdl)
            if ctx_ann:
                generator.save_annotation(ctx_ann, 'context', service_name)
        
        if args.type in ['policy', 'all']:
            pol_ann = generator.generate_policy_annotation(args.wsdl)
            if pol_ann:
                generator.save_annotation(pol_ann, 'policy', service_name)
        
        print("\n" + "="*80)
        print("Génération terminée!")
        print("="*80)