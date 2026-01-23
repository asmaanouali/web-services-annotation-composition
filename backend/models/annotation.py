"""
Modèles d'annotations basés sur le MOF-based Social Web Services
"""

class InteractionAnnotation:
    """Annotations d'interaction avec d'autres services"""
    def __init__(self):
        self.can_call = []  # Services que ce service peut appeler
        self.depends_on = []  # Dépendances
        self.role = "worker"  # orchestrateur, worker, aggregator, etc.
        self.collaboration_history = {}  # Historique des collaborations
        self.substitutes = []  # Services de remplacement
    
    def to_dict(self):
        return {
            'can_call': self.can_call,
            'depends_on': self.depends_on,
            'role': self.role,
            'collaboration_history': self.collaboration_history,
            'substitutes': self.substitutes
        }


class ContextAnnotation:
    """Annotations de contexte d'utilisation"""
    def __init__(self):
        self.context_aware = False
        self.location_sensitive = False
        self.time_critical = "low"  # low, medium, high
        self.interaction_count = 0
        self.last_used = None
        self.usage_patterns = []
        self.environmental_requirements = []
    
    def to_dict(self):
        return {
            'context_aware': self.context_aware,
            'location_sensitive': self.location_sensitive,
            'time_critical': self.time_critical,
            'interaction_count': self.interaction_count,
            'last_used': self.last_used,
            'usage_patterns': self.usage_patterns,
            'environmental_requirements': self.environmental_requirements
        }


class PolicyAnnotation:
    """Annotations de politiques (privacy, sécurité, conformité)"""
    def __init__(self):
        self.gdpr_compliant = True
        self.data_retention_days = 30
        self.security_level = "medium"  # low, medium, high
        self.privacy_policy = "encrypted"
        self.compliance_standards = []  # ISO, HIPAA, etc.
        self.data_classification = "internal"  # public, internal, confidential
        self.encryption_required = False
    
    def to_dict(self):
        return {
            'gdpr_compliant': self.gdpr_compliant,
            'data_retention_days': self.data_retention_days,
            'security_level': self.security_level,
            'privacy_policy': self.privacy_policy,
            'compliance_standards': self.compliance_standards,
            'data_classification': self.data_classification,
            'encryption_required': self.encryption_required
        }


class ServiceAnnotation:
    """Annotation complète d'un service (basée sur MOF)"""
    def __init__(self):
        self.interaction = InteractionAnnotation()
        self.context = ContextAnnotation()
        self.policy = PolicyAnnotation()
        
        # Propriétés sociales (Social Web Services)
        self.trust_degree = 0.5  # 0 à 1
        self.reputation = 0.5  # 0 à 1
        self.collaboration_weight = {}  # {service_id: weight}
        self.robustness_score = 0.5  # 0 à 1
    
    def to_dict(self):
        return {
            'interaction': self.interaction.to_dict(),
            'context': self.context.to_dict(),
            'policy': self.policy.to_dict(),
            'trust_degree': self.trust_degree,
            'reputation': self.reputation,
            'collaboration_weight': self.collaboration_weight,
            'robustness_score': self.robustness_score
        }
    
    @classmethod
    def from_dict(cls, data):
        """Crée une annotation à partir d'un dictionnaire"""
        annotation = cls()
        if 'trust_degree' in data:
            annotation.trust_degree = data['trust_degree']
        if 'reputation' in data:
            annotation.reputation = data['reputation']
        if 'collaboration_weight' in data:
            annotation.collaboration_weight = data['collaboration_weight']
        return annotation