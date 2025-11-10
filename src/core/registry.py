from pymongo import MongoClient
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging
from src.core.wsdl_parser import WSDLParser

logger = logging.getLogger(__name__)

class ServiceRegistry:
    def __init__(self, mongo_uri: str = "mongodb://localhost:27017/", db_name: str = "service_registry"):
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.services = self.db['services']
        self.execution_history = self.db['execution_history']
        
        # Créer des index
        self.services.create_index("service_id", unique=True)
        self.services.create_index("service_name")
        self.execution_history.create_index([("service_id", 1), ("timestamp", -1)])
        
        self.logger = logging.getLogger(__name__)
    
    def register_service(self, wsdl_url: str) -> str:
        """Enregistre un nouveau service"""
        try:
            # Parser le WSDL
            parser = WSDLParser(wsdl_url)
            annotations = parser.generate_functional_annotations()
            
            # Ajouter les métadonnées
            annotations['metadata'] = {
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'status': 'active',
                'invocation_count': 0
            }
            
            # Initialiser les annotations d'interaction et de politique
            annotations['interaction_annotations'] = {
                'execution_history': [],
                'statistics': {
                    'total_invocations': 0,
                    'success_rate': 0.0,
                    'avg_response_time_ms': 0.0
                },
                'composition_patterns': [],
                'contextual_performance': {}
            }
            
            annotations['policy_annotations'] = {
                'security': {},
                'privacy': {'data_sensitivity': 'unknown'},
                'usage': {},
                'qos': {}
            }
            
            # Insérer dans la base
            self.services.insert_one(annotations)
            
            self.logger.info(f"Service registered: {annotations['service_name']} (ID: {annotations['service_id']})")
            return annotations['service_id']
            
        except Exception as e:
            self.logger.error(f"Error registering service: {e}")
            raise
    
    def get_service(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Récupère un service par son ID"""
        return self.services.find_one({'service_id': service_id}, {'_id': 0})
    
    def search_services(self, query: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Recherche des services selon des critères"""
        search_filter = {}
        
        # Recherche par nom
        if 'name' in query:
            search_filter['service_name'] = {'$regex': query['name'], '$options': 'i'}
        
        # Recherche par opération
        if 'operation' in query:
            search_filter['functional_annotations.operations.name'] = query['operation']
        
        # Filtrage par QoS
        if 'min_success_rate' in query:
            search_filter['interaction_annotations.statistics.success_rate'] = {
                '$gte': query['min_success_rate']
            }
        
        # Exécuter la recherche
        results = list(self.services.find(search_filter, {'_id': 0}))
        
        # Si contexte fourni, trier par pertinence contextuelle
        if context and results:
            results = self._rank_by_context(results, context)
        
        return results
    
    def _rank_by_context(self, services: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Classe les services par pertinence contextuelle"""
        # Implémentation simplifiée - à enrichir
        for service in services:
            service['context_score'] = self._compute_context_score(service, context)
        
        return sorted(services, key=lambda s: s.get('context_score', 0), reverse=True)
    
    def _compute_context_score(self, service: Dict[str, Any], context: Dict[str, Any]) -> float:
        """Calcule un score de pertinence contextuelle"""
        score = 0.0
        
        # Exemple : bonus si le service a été utilisé avec succès dans un contexte similaire
        contextual_perf = service.get('interaction_annotations', {}).get('contextual_performance', {})
        
        if 'user' in context and 'location' in context['user']:
            location = context['user']['location'].get('country', '')
            if location in contextual_perf.get('by_location', {}):
                loc_perf = contextual_perf['by_location'][location]
                score += loc_perf.get('success_rate', 0) * 50
        
        # Pénalité si temps de réponse trop élevé
        avg_response = service.get('interaction_annotations', {}).get('statistics', {}).get('avg_response_time_ms', 1000)
        if 'application' in context and 'constraints' in context['application']:
            max_time = context['application']['constraints'].get('max_response_time', 5000)
            if avg_response < max_time:
                score += (1 - avg_response / max_time) * 30
        
        return score
    
    def update_annotations(self, service_id: str, annotations: Dict[str, Any]) -> bool:
        """Met à jour les annotations d'un service"""
        try:
            result = self.services.update_one(
                {'service_id': service_id},
                {
                    '$set': {
                        **annotations,
                        'metadata.updated_at': datetime.utcnow()
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            self.logger.error(f"Error updating annotations: {e}")
            return False
    
    def list_all_services(self) -> List[Dict[str, Any]]:
        """Liste tous les services enregistrés"""
        return list(self.services.find({}, {'_id': 0}))