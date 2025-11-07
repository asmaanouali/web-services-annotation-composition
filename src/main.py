"""
ServiceAnnotationSystem - Point d'entrée principal du système
"""

import logging
from datetime import datetime
from typing import Dict, Any, List

from src.core.registry import ServiceRegistry
from src.core.interceptor import InstrumentedSOAPClient
from src.annotation.pattern_detector import CompositionPatternDetector
from src.annotation.performance_analyzer import ContextualPerformanceAnalyzer
from src.annotation.policy_manager import PolicyManager
from src.recommendation.recommender import ContextualServiceRecommender
from src.utils.logger import setup_logger

logger = setup_logger(__name__, log_level="INFO", log_file="logs/system.log")


class ServiceAnnotationSystem:
    """Système principal d'annotation et de gestion de services"""
    
    def __init__(self, mongo_uri: str = "mongodb://localhost:27017/"):
        self.registry = ServiceRegistry(mongo_uri)
        self.pattern_detector = CompositionPatternDetector(self.registry)
        self.perf_analyzer = ContextualPerformanceAnalyzer(self.registry)
        self.recommender = ContextualServiceRecommender(self.registry)
        self.policy_manager = PolicyManager(self.registry)
        
        logger.info("ServiceAnnotationSystem initialized")
    
    def register_and_annotate_service(self, wsdl_url: str, policies: Dict[str, Any] = None) -> str:
        """Enregistre un service et applique les annotations initiales"""
        
        logger.info(f"Registering service from WSDL: {wsdl_url}")
        
        service_id = self.registry.register_service(wsdl_url)
        
        if policies:
            if 'security' in policies:
                self.policy_manager.define_security_policy(service_id, policies['security'])
            if 'privacy' in policies:
                self.policy_manager.define_privacy_policy(service_id, policies['privacy'])
            if 'usage' in policies:
                self.policy_manager.define_usage_policy(service_id, policies['usage'])
            if 'qos' in policies:
                self.policy_manager.define_qos_policy(service_id, policies['qos'])
        
        logger.info(f"Service registered successfully: {service_id}")
        return service_id
    
    def invoke_service(self, service_id: str, operation: str, params: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Invoque un service avec capture d'annotations"""
        
        valid, violations = self.policy_manager.validate_policies(service_id, context)
        if not valid:
            raise Exception(f"Policy violations: {violations}")
        
        service = self.registry.get_service(service_id)
        if not service:
            raise Exception(f"Service not found: {service_id}")
        
        client = InstrumentedSOAPClient(
            service['wsdl_url'],
            service_id,
            self.registry,
            context
        )
        
        result = client.invoke(operation, **params)
        
        return result
    
    def analyze_and_enrich(self):
        """Analyse l'historique et enrichit les annotations"""
        
        logger.info("Starting analysis and enrichment")
        
        logger.info("Detecting composition patterns...")
        self.pattern_detector.detect_patterns()
        
        logger.info("Analyzing contextual performance...")
        self.perf_analyzer.analyze_all_services()
        
        logger.info("Analysis and enrichment completed")
    
    def find_best_services(self, query: Dict[str, Any], context: Dict[str, Any], top_k: int = 5) -> List[Dict[str, Any]]:
        """Trouve les meilleurs services pour une requête"""
        
        recommendations = self.recommender.recommend_services(query, context, top_k)
        
        return recommendations
    
    def get_service_summary(self, service_id: str) -> Dict[str, Any]:
        """Obtient un résumé complet d'un service avec toutes ses annotations"""
        
        service = self.registry.get_service(service_id)
        if not service:
            return None
        
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


if __name__ == "__main__":
    # Test rapide
    system = ServiceAnnotationSystem()
    print("System initialized successfully!")