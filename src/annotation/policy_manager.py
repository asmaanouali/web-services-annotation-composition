from enum import Enum
from typing import List, Dict, Optional, Any, Tuple
from src.core.registry import ServiceRegistry
from datetime import datetime
import logging

class PolicyType(Enum):
    SECURITY = "security"
    PRIVACY = "privacy"
    USAGE = "usage"
    QOS = "qos"

class PolicyManager:
    """Gère les politiques associées aux services"""
    
    def __init__(self, registry: ServiceRegistry):
        self.registry = registry
        self.logger = logging.getLogger(__name__)
    
    def define_security_policy(self, service_id: str, policy: Dict[str, Any]) -> bool:
        """Définit une politique de sécurité"""
        required_fields = ['authentication_required', 'authentication_method']
        
        if not all(field in policy for field in required_fields):
            self.logger.error("Missing required security policy fields")
            return False
        
        return self._update_policy(service_id, PolicyType.SECURITY, policy)
    
    def define_privacy_policy(self, service_id: str, policy: Dict[str, Any]) -> bool:
        """Définit une politique de confidentialité"""
        required_fields = ['data_sensitivity', 'stores_personal_data']
        
        if not all(field in policy for field in required_fields):
            self.logger.error("Missing required privacy policy fields")
            return False
        
        # Valider les valeurs
        valid_sensitivities = ['public', 'internal', 'confidential', 'secret']
        if policy['data_sensitivity'] not in valid_sensitivities:
            self.logger.error(f"Invalid data sensitivity: {policy['data_sensitivity']}")
            return False
        
        return self._update_policy(service_id, PolicyType.PRIVACY, policy)
    
    def define_usage_policy(self, service_id: str, policy: Dict[str, Any]) -> bool:
        """Définit une politique d'utilisation"""
        return self._update_policy(service_id, PolicyType.USAGE, policy)
    
    def define_qos_policy(self, service_id: str, policy: Dict[str, Any]) -> bool:
        """Définit une politique de QoS (SLA)"""
        return self._update_policy(service_id, PolicyType.QOS, policy)
    
    def _update_policy(self, service_id: str, policy_type: PolicyType, policy: Dict[str, Any]) -> bool:
        """Met à jour une politique dans le registre"""
        try:
            update_path = f'policy_annotations.{policy_type.value}'
            result = self.registry.services.update_one(
                {'service_id': service_id},
                {
                    '$set': {
                        update_path: policy,
                        'metadata.updated_at': datetime.utcnow()
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            self.logger.error(f"Error updating policy: {e}")
            return False
    
    def validate_policies(self, service_id: str, context: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Valide que toutes les politiques sont respectées pour un contexte donné"""
        service = self.registry.get_service(service_id)
        if not service:
            return False, ["Service not found"]
        
        violations = []
        
        # Valider les politiques de sécurité
        security_violations = self._validate_security(service, context)
        violations.extend(security_violations)
        
        # Valider les politiques de confidentialité
        privacy_violations = self._validate_privacy(service, context)
        violations.extend(privacy_violations)
        
        # Valider les politiques d'utilisation
        usage_violations = self._validate_usage(service, context)
        violations.extend(usage_violations)
        
        # Valider les SLA
        qos_violations = self._validate_qos(service, context)
        violations.extend(qos_violations)
        
        return len(violations) == 0, violations
    
    def _validate_security(self, service: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        """Valide les politiques de sécurité"""
        violations = []
        security_policy = service.get('policy_annotations', {}).get('security', {})
        
        if security_policy.get('authentication_required', False):
            user_authenticated = context.get('user', {}).get('authenticated', False)
            if not user_authenticated:
                violations.append("Authentication required but user not authenticated")
        
        return violations
    
    def _validate_privacy(self, service: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        """Valide les politiques de confidentialité"""
        violations = []
        privacy_policy = service.get('policy_annotations', {}).get('privacy', {})
        
        data_sensitivity = privacy_policy.get('data_sensitivity', 'unknown')
        user_privacy_level = context.get('user', {}).get('preferences', {}).get('privacy_level', 'medium')
        
        # Vérifier compatibilité
        if user_privacy_level == 'high' and data_sensitivity in ['confidential', 'secret']:
            violations.append(f"Service handles {data_sensitivity} data but user requires high privacy")
        
        # Vérifier consentement si données personnelles
        if privacy_policy.get('stores_personal_data', False):
            consent = context.get('user', {}).get('consents', {}).get('data_processing', False)
            if not consent:
                violations.append("Service processes personal data but user has not given consent")
        
        return violations
    
    def _validate_usage(self, service: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        """Valide les politiques d'utilisation"""
        violations = []
        usage_policy = service.get('policy_annotations', {}).get('usage', {})
        
        # Vérifier rate limiting (nécessiterait un compteur externe)
        # Vérifier coût
        cost_per_call = usage_policy.get('cost_per_call', 0.0)
        max_cost = context.get('application', {}).get('constraints', {}).get('max_cost', float('inf'))
        
        if cost_per_call > max_cost:
            violations.append(f"Service cost ({cost_per_call}) exceeds maximum allowed ({max_cost})")
        
        return violations
    
    def _validate_qos(self, service: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        """Valide les SLA"""
        violations = []
        qos_policy = service.get('policy_annotations', {}).get('qos', {})
        stats = service.get('interaction_annotations', {}).get('statistics', {})
        
        # Vérifier temps de réponse
        sla_response_time = qos_policy.get('sla_response_time_ms', float('inf'))
        avg_response_time = stats.get('avg_response_time_ms', 0)
        
        if avg_response_time > sla_response_time:
            violations.append(f"Average response time ({avg_response_time}ms) exceeds SLA ({sla_response_time}ms)")
        
        # Vérifier disponibilité
        sla_availability = qos_policy.get('sla_availability', 0.0)
        success_rate = stats.get('success_rate', 0.0)
        
        if success_rate < sla_availability:
            violations.append(f"Success rate ({success_rate}) below SLA ({sla_availability})")
        
        return violations