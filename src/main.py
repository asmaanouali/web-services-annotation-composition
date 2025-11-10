import logging
from datetime import datetime
import json  # Ajouter cet import
from typing import Dict, Any, List, Optional  # Ajouter Optional

from src.core.registry import ServiceRegistry
from src.core.interceptor import InstrumentedSOAPClient
from src.annotation.pattern_detector import CompositionPatternDetector
from src.annotation.performance_analyzer import ContextualPerformanceAnalyzer
from src.annotation.policy_manager import PolicyManager
from src.recommendation.recommender import ContextualServiceRecommender
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class ServiceAnnotationSystem:
    """Système principal d'annotation et de gestion de services"""
    
    def __init__(self, mongo_uri: str = "mongodb://localhost:27017/"):
        self.registry = ServiceRegistry(mongo_uri)
        self.pattern_detector = CompositionPatternDetector(self.registry)
        self.perf_analyzer = ContextualPerformanceAnalyzer(self.registry)
        self.recommender = ContextualServiceRecommender(self.registry)
        self.policy_manager = PolicyManager(self.registry)
        
        self.logger = logging.getLogger(__name__)
    
    def register_and_annotate_service(self, wsdl_url: str, policies: Optional[Dict[str, Any]] = None) -> str:
        """Enregistre un service et applique les annotations initiales"""
        
        self.logger.info(f"Registering service from WSDL: {wsdl_url}")
        
        # Enregistrer le service
        service_id = self.registry.register_service(wsdl_url)
        
        # Appliquer les politiques si fournies
        if policies:
            if 'security' in policies:
                self.policy_manager.define_security_policy(service_id, policies['security'])
            if 'privacy' in policies:
                self.policy_manager.define_privacy_policy(service_id, policies['privacy'])
            if 'usage' in policies:
                self.policy_manager.define_usage_policy(service_id, policies['usage'])
            if 'qos' in policies:
                self.policy_manager.define_qos_policy(service_id, policies['qos'])
        
        self.logger.info(f"Service registered successfully: {service_id}")
        return service_id
    
    def invoke_service(self, service_id: str, operation: str, params: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Invoque un service avec capture d'annotations"""
        
        # Valider les politiques
        valid, violations = self.policy_manager.validate_policies(service_id, context)
        if not valid:
            raise Exception(f"Policy violations: {violations}")
        
        # Récupérer le service
        service = self.registry.get_service(service_id)
        if not service:
            raise Exception(f"Service not found: {service_id}")
        
        # Créer un client instrumenté
        client = InstrumentedSOAPClient(
            service['wsdl_url'],
            service_id,
            self.registry,
            context
        )
        
        # Invoquer l'opération
        result = client.invoke(operation, **params)
        
        return result
    
    def analyze_and_enrich(self):
        """Analyse l'historique et enrichit les annotations"""
        
        self.logger.info("Starting analysis and enrichment")
        
        # Détecter les patterns de composition
        self.logger.info("Detecting composition patterns...")
        self.pattern_detector.detect_patterns()
        
        # Analyser les performances contextuelles
        self.logger.info("Analyzing contextual performance...")
        self.perf_analyzer.analyze_all_services()
        
        self.logger.info("Analysis and enrichment completed")
    
    def find_best_services(self, query: Dict[str, Any], context: Dict[str, Any], top_k: int = 5) -> List[Dict[str, Any]]:
        """Trouve les meilleurs services pour une requête"""
        
        recommendations = self.recommender.recommend_services(query, context, top_k)
        
        return recommendations
    
    def get_service_summary(self, service_id: str) -> Dict[str, Any]:
        """Obtient un résumé complet d'un service avec toutes ses annotations"""
        
        service = self.registry.get_service(service_id)
        if not service:
            return {}
        
        # Calculer des métriques supplémentaires
        stats = service.get('interaction_annotations', {}).get('statistics', {})
        
        summary = {
            'service_id': service_id,
            'service_name': service['service_name'],
            'endpoint': service['endpoint_url'],
            'operations': [op['name'] for op in service.get('functional_annotations', {}).get('operations', [])],
            'statistics': {
                'total_invocations': stats.get('total_invocations', 0),
                'success_rate': f"{stats.get('success_rate', 0)*100:.1f}%",
                'avg_response_time': f"{stats.get('avg_response_time_ms', 0):.0f}ms"
            },
            'policies': {
                'security': service.get('policy_annotations', {}).get('security', {}),
                'privacy': service.get('policy_annotations', {}).get('privacy', {}).get('data_sensitivity', 'unknown')
            },
            'contextual_performance': service.get('interaction_annotations', {}).get('contextual_performance', {})
        }
        
        return summary
# Exemple d'utilisation complète
def demo():
    """Démonstration du système"""
    
    # Initialiser le système
    system = ServiceAnnotationSystem()
    
    # 1. Enregistrer un service
    wsdl_url = "http://webservices.oorsprong.org/websamples.countryinfo/CountryInfoService.wso?WSDL"
    
    policies = {
        'security': {
            'authentication_required': False,
            'authentication_method': 'none',
            'encryption': 'TLS_1.2'
        },
        'privacy': {
            'data_sensitivity': 'public',
            'stores_personal_data': False,
            'gdpr_compliant': True
        },
        'usage': {
            'rate_limit': '1000/day',
            'cost_per_call': 0.0,
            'free_tier': True
        },
        'qos': {
            'sla_availability': 0.99,
            'sla_response_time_ms': 1000
        }
    }
    
    service_id = system.register_and_annotate_service(wsdl_url, policies)
    print(f"Service registered: {service_id}")
    
    # 2. Invoquer le service plusieurs fois avec différents contextes
    contexts = [
        {
            'user': {'id': 'user1', 'location': {'country': 'DZ'}, 'authenticated': True},
            'temporal': {'timestamp': datetime.utcnow().isoformat()},
            'environmental': {'network_quality': 'good'},
            'application': {'goal': 'get_country_info'}
        },
        {
            'user': {'id': 'user2', 'location': {'country': 'FR'}, 'authenticated': True},
            'temporal': {'timestamp': datetime.utcnow().isoformat()},
            'environmental': {'network_quality': 'excellent'},
            'application': {'goal': 'get_country_info'}
        }
    ]
    
    for ctx in contexts:
        try:
            result = system.invoke_service(
                service_id,
                'CountryName',
                {'sCountryISOCode': ctx['user']['location']['country']},
                ctx
            )
            print(f"Result for {ctx['user']['location']['country']}: {result}")
        except Exception as e:
            print(f"Error: {e}")
    
    # 3. Analyser et enrichir les annotations
    system.analyze_and_enrich()
    
    # 4. Obtenir le résumé du service
    summary = system.get_service_summary(service_id)
    print("\nService Summary:")
    print(json.dumps(summary, indent=2, default=str))
    
    # 5. Rechercher les meilleurs services
    query = {'operation': 'CountryName'}
    context = contexts[0]
    
    recommendations = system.find_best_services(query, context, top_k=3)
    print("\nRecommendations:")
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec['service_name']} (Score: {rec['recommendation_score']:.2f})")
        print(f"   Reasons: {', '.join(rec['recommendation_reasons'])}")


if __name__ == "__main__":
    demo()