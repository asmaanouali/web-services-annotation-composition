"""
Modèles d'annotations basés sur le MOF-based Social Web Services Description Metamodel
Référence: Benna, A., Maamar, Z., & Nacer, M. A. (2016)
"""

class SNProperty:
    """Propriété générique pour les annotations (MOF-based)"""
    def __init__(self, prop_name="", value=0.0):
        self.prop_name = prop_name
        self.value = value
    
    def to_dict(self):
        return {
            'prop_name': self.prop_name,
            'value': self.value
        }


class SNAssociationType:
    """Type d'association sociale entre services"""
    def __init__(self):
        self.type_name = ""  # collaboration, substitution, competition, recommendation
        self.is_symmetric = False
        self.supports_transitivity = False
        self.is_dependent = False
        self.temporal_aspect = "permanent"  # permanent, temporary, upon_request
    
    def to_dict(self):
        return {
            'type_name': self.type_name,
            'is_symmetric': self.is_symmetric,
            'supports_transitivity': self.supports_transitivity,
            'is_dependent': self.is_dependent,
            'temporal_aspect': self.temporal_aspect
        }


class SNAssociationWeight(SNProperty):
    """Poids d'une association sociale (spécialisation de SNProperty)"""
    def __init__(self, weight_type="", value=0.0):
        super().__init__(weight_type, value)
        self.calculation_method = "interaction_count"  # interaction_count, qos_similarity, combined
    
    def to_dict(self):
        result = super().to_dict()
        result['calculation_method'] = self.calculation_method
        return result


class SNAssociation:
    """Association entre deux services (relation sociale)"""
    def __init__(self):
        self.source_node = ""  # ID du service source
        self.target_node = ""  # ID du service cible
        self.association_type = SNAssociationType()
        self.association_weight = SNAssociationWeight()
        self.duration = "permanent"  # permanent, temporary
        self.creation_date = None
        self.last_interaction = None
    
    def to_dict(self):
        return {
            'source_node': self.source_node,
            'target_node': self.target_node,
            'association_type': self.association_type.to_dict(),
            'association_weight': self.association_weight.to_dict(),
            'duration': self.duration,
            'creation_date': self.creation_date,
            'last_interaction': self.last_interaction
        }


class SNNode:
    """Nœud social représentant un service dans le réseau social"""
    def __init__(self, node_id=""):
        self.node_id = node_id
        self.node_type = "WebService"  # WebService, User, Provider
        self.state = "active"  # active, inactive, deprecated
        self.properties = []  # Liste de SNProperty
        
        # Node Degree (propriétés sociales du nœud)
        self.trust_degree = SNProperty("trust_degree", 0.5)
        self.reputation = SNProperty("reputation", 0.5)
        self.cooperativeness = SNProperty("cooperativeness", 0.5)
        
        # Associations de ce nœud vers d'autres
        self.associations = []  # Liste de SNAssociation
    
    def add_property(self, prop_name, value):
        """Ajoute une propriété au nœud"""
        prop = SNProperty(prop_name, value)
        self.properties.append(prop)
    
    def add_association(self, target_node, assoc_type, weight_value):
        """Ajoute une association vers un autre service"""
        assoc = SNAssociation()
        assoc.source_node = self.node_id
        assoc.target_node = target_node
        assoc.association_type.type_name = assoc_type
        assoc.association_weight.prop_name = f"{assoc_type}_weight"
        assoc.association_weight.value = weight_value
        self.associations.append(assoc)
    
    def to_dict(self):
        return {
            'node_id': self.node_id,
            'node_type': self.node_type,
            'state': self.state,
            'properties': [p.to_dict() for p in self.properties],
            'trust_degree': self.trust_degree.to_dict(),
            'reputation': self.reputation.to_dict(),
            'cooperativeness': self.cooperativeness.to_dict(),
            'associations': [a.to_dict() for a in self.associations]
        }


class InteractionAnnotation:
    """Annotations d'interaction (basées sur le modèle MOF)"""
    def __init__(self):
        self.can_call = []  # Services que ce service peut appeler
        self.depends_on = []  # Dépendances
        self.role = "worker"  # orchestrateur, worker, aggregator
        self.collaboration_history = {}  # Historique des collaborations
        self.substitutes = []  # Services de remplacement
        
        # Associations sociales typées
        self.collaboration_associations = []  # Liste de target_nodes
        self.substitution_associations = []
        self.competition_associations = []
    
    def to_dict(self):
        return {
            'can_call': self.can_call,
            'depends_on': self.depends_on,
            'role': self.role,
            'collaboration_history': self.collaboration_history,
            'substitutes': self.substitutes,
            'collaboration_associations': self.collaboration_associations,
            'substitution_associations': self.substitution_associations,
            'competition_associations': self.competition_associations
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
    """
    Annotation complète d'un service (basée sur MOF-based Social Web Services)
    Correspond au modèle S-WSDL du papier
    """
    def __init__(self, service_id=""):
        # Nœud social principal
        self.social_node = SNNode(service_id)
        
        # Annotations complémentaires (extension du modèle)
        self.interaction = InteractionAnnotation()
        self.context = ContextAnnotation()
        self.policy = PolicyAnnotation()
    
    def to_dict(self):
        return {
            'social_node': self.social_node.to_dict(),
            'interaction': self.interaction.to_dict(),
            'context': self.context.to_dict(),
            'policy': self.policy.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data):
        """Crée une annotation à partir d'un dictionnaire"""
        service_id = data.get('social_node', {}).get('node_id', '')
        annotation = cls(service_id)
        
        # Reconstruire le nœud social
        if 'social_node' in data:
            sn_data = data['social_node']
            annotation.social_node.node_type = sn_data.get('node_type', 'WebService')
            annotation.social_node.state = sn_data.get('state', 'active')
            
            if 'trust_degree' in sn_data:
                annotation.social_node.trust_degree.value = sn_data['trust_degree'].get('value', 0.5)
            if 'reputation' in sn_data:
                annotation.social_node.reputation.value = sn_data['reputation'].get('value', 0.5)
        
        return annotation