"""
Intercepteur SOAP pour capturer les invocations et annotations
"""

from zeep import Client
from zeep.plugins import Plugin
import time
from datetime import datetime
from typing import Any, Dict
import logging

from src.core.registry import ServiceRegistry

logger = logging.getLogger(__name__)


class AnnotationInterceptor(Plugin):
    """Plugin zeep pour intercepter et enregistrer les invocations SOAP"""
    
    def __init__(self, registry: ServiceRegistry, service_id: str, context: Dict[str, Any]):
        self.registry = registry
        self.service_id = service_id
        self.context = context
        
        self.start_time = None
        self.operation_name = None
    
    def ingress(self, envelope, http_headers, operation):
        """Appelé avant l'envoi de la requête"""
        self.start_time = time.time()
        self.operation_name = operation.name
        
        logger.debug(f"Invoking operation: {operation.name}")
        return envelope, http_headers
    
    def egress(self, envelope, http_headers, operation, binding_options):
        """Appelé après réception de la réponse"""
        execution_time_ms = int((time.time() - self.start_time) * 1000)
        
        # Enregistrer l'exécution
        execution_record = {
            'service_id': self.service_id,
            'operation_name': self.operation_name,
            'timestamp': datetime.utcnow(),
            'execution_time_ms': execution_time_ms,
            'status': 'success',
            'context': self.context,
            'http_status': http_headers.get('status', 200)
        }
        
        # Sauvegarder dans l'historique
        self.registry.execution_history.insert_one(execution_record)
        
        # Mettre à jour les statistiques
        self._update_statistics(execution_time_ms, 'success')
        
        logger.info(f"Operation {self.operation_name} completed in {execution_time_ms}ms")
        return envelope, http_headers
    
    def _update_statistics(self, execution_time_ms: int, status: str):
        """Met à jour les statistiques du service"""
        service = self.registry.get_service(self.service_id)
        if not service:
            return
        
        stats = service.get('interaction_annotations', {}).get('statistics', {})
        
        total = stats.get('total_invocations', 0) + 1
        success_count = stats.get('success_count', 0) + (1 if status == 'success' else 0)
        failure_count = stats.get('failure_count', 0) + (1 if status == 'failure' else 0)
        
        old_avg = stats.get('avg_response_time_ms', 0)
        new_avg = ((old_avg * (total - 1)) + execution_time_ms) / total
        
        self.registry.services.update_one(
            {'service_id': self.service_id},
            {
                '$set': {
                    'interaction_annotations.statistics': {
                        'total_invocations': total,
                        'success_count': success_count,
                        'failure_count': failure_count,
                        'success_rate': success_count / total if total > 0 else 0,
                        'avg_response_time_ms': new_avg,
                        'last_invocation': datetime.utcnow()
                    },
                    'metadata.updated_at': datetime.utcnow()
                }
            }
        )


class InstrumentedSOAPClient:
    """Client SOAP instrumenté pour capturer les interactions"""
    
    def __init__(self, wsdl_url: str, service_id: str, registry: ServiceRegistry, context: Dict[str, Any] = None):
        self.wsdl_url = wsdl_url
        self.service_id = service_id
        self.registry = registry
        self.context = context or {}
        
        interceptor = AnnotationInterceptor(registry, service_id, self.context)
        self.client = Client(wsdl_url, plugins=[interceptor])
        self.service = self.client.service
    
    def invoke(self, operation_name: str, **kwargs) -> Any:
        """Invoque une opération du service"""
        try:
            operation = getattr(self.service, operation_name)
            result = operation(**kwargs)
            
            self._record_invocation(operation_name, kwargs, result, 'success')
            
            return result
            
        except Exception as e:
            self._record_invocation(operation_name, kwargs, None, 'failure', str(e))
            raise
    
    def _record_invocation(self, operation_name: str, inputs: Dict, output: Any, status: str, error: str = None):
        """Enregistre les détails de l'invocation"""
        record = {
            'service_id': self.service_id,
            'operation_name': operation_name,
            'timestamp': datetime.utcnow(),
            'inputs': self._serialize_data(inputs),
            'output': self._serialize_data(output) if output else None,
            'status': status,
            'error_message': error,
            'context': self.context
        }
        
        self.registry.execution_history.insert_one(record)
    
    def _serialize_data(self, data: Any) -> Any:
        """Sérialise les données pour le stockage"""
        if data is None:
            return None
        
        if isinstance(data, (str, int, float, bool)):
            return data
        elif isinstance(data, dict):
            return {k: self._serialize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._serialize_data(item) for item in data]
        else:
            return str(data)