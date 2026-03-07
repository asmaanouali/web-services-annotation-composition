"""
Annotation models based on the MOF-based Social Web Services Description Metamodel.
Reference: Benna, A., Maamar, Z., & Nacer, M. A. (2016).
"""

class SNProperty:
    """Generic property for annotations (MOF-based)."""
    __slots__ = ('prop_name', 'value')
    def __init__(self, prop_name="", value=0.0):
        self.prop_name = prop_name
        self.value = value
    
    def to_dict(self):
        return {
            'prop_name': self.prop_name,
            'value': self.value
        }


class SNAssociationType:
    """Social association type between services."""
    __slots__ = ('type_name', 'is_symmetric', 'supports_transitivity', 'is_dependent', 'temporal_aspect')
    def __init__(self):
        self.type_name = ""
        self.is_symmetric = False
        self.supports_transitivity = False
        self.is_dependent = False
        self.temporal_aspect = "permanent"
    
    def to_dict(self):
        return {
            'type_name': self.type_name,
            'is_symmetric': self.is_symmetric,
            'supports_transitivity': self.supports_transitivity,
            'is_dependent': self.is_dependent,
            'temporal_aspect': self.temporal_aspect
        }


class SNAssociationWeight(SNProperty):
    """Weight of a social association (specialisation of SNProperty)."""
    __slots__ = ('calculation_method',)
    def __init__(self, weight_type="", value=0.0):
        super().__init__(weight_type, value)
        self.calculation_method = "interaction_count"
    
    def to_dict(self):
        result = super().to_dict()
        result['calculation_method'] = self.calculation_method
        return result


class SNAssociation:
    """Association between two services (social relation)."""
    __slots__ = ('source_node', 'target_node', 'association_type', 'association_weight', 'duration', 'creation_date', 'last_interaction')
    def __init__(self):
        self.source_node = ""
        self.target_node = ""
        self.association_type = SNAssociationType()
        self.association_weight = SNAssociationWeight()
        self.duration = "permanent"
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
    """Social node representing a service in the social network."""
    __slots__ = ('node_id', 'node_type', 'state', 'properties',
                 'trust_degree', 'reputation', 'cooperativeness', 'associations')

    def __init__(self, node_id=""):
        self.node_id = node_id
        self.node_type = "WebService"  # WebService, User, Provider
        self.state = "active"  # active, inactive, deprecated
        self.properties = []  # List of SNProperty
        
        # Node Degree (social properties of the node)
        self.trust_degree = SNProperty("trust_degree", 0.5)
        self.reputation = SNProperty("reputation", 0.5)
        self.cooperativeness = SNProperty("cooperativeness", 0.5)
        
        # Associations from this node to others
        self.associations = []  # List of SNAssociation
    
    def add_property(self, prop_name, value):
        """Adds a property to the node."""
        prop = SNProperty(prop_name, value)
        self.properties.append(prop)
    
    def add_association(self, target_node, assoc_type, weight_value):
        """Adds an association to another service."""
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
    """Interaction annotations (based on the MOF model)."""
    __slots__ = ('can_call', 'depends_on', 'role', 'collaboration_history',
                 'substitutes', 'collaboration_associations',
                 'substitution_associations', 'competition_associations')

    def __init__(self):
        self.can_call = []  # Services this service can call
        self.depends_on = []  # Dependencies
        self.role = "worker"  # orchestrator, worker, aggregator
        self.collaboration_history = {}  # Collaboration history
        self.substitutes = []  # Replacement services
        
        # Typed social associations
        self.collaboration_associations = []  # List of target_nodes
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
    """Usage context annotations — derived from real history."""
    __slots__ = ('context_aware', 'location_sensitive', 'time_critical',
                 'interaction_count', 'last_used', 'usage_patterns',
                 'environmental_requirements', 'observed_locations',
                 'observed_networks', 'observed_devices',
                 'context_adaptation_score')

    def __init__(self):
        self.context_aware = False
        self.location_sensitive = False
        self.time_critical = "low"  # low, medium, high
        self.interaction_count = 0
        self.last_used = None
        self.usage_patterns = []           # e.g. ["peak_hours_morning", "business_days"]
        self.environmental_requirements = []
        # NEW: observed context summary (populated from history store)
        self.observed_locations = {}       # {"Paris": 10, "London": 5}
        self.observed_networks = {}        # {"wifi": 12, "4G": 8}
        self.observed_devices = {}         # {"mobile": 5, "desktop": 15}
        self.context_adaptation_score = 0.0  # 0–1, how well the service adapts
    
    def to_dict(self):
        return {
            'context_aware': self.context_aware,
            'location_sensitive': self.location_sensitive,
            'time_critical': self.time_critical,
            'interaction_count': self.interaction_count,
            'last_used': self.last_used,
            'usage_patterns': self.usage_patterns,
            'environmental_requirements': self.environmental_requirements,
            'observed_locations': self.observed_locations,
            'observed_networks': self.observed_networks,
            'observed_devices': self.observed_devices,
            'context_adaptation_score': self.context_adaptation_score,
        }


class PolicyAnnotation:
    """Policy annotations (privacy, security, compliance)."""
    __slots__ = ('gdpr_compliant', 'data_retention_days', 'security_level',
                 'privacy_policy', 'compliance_standards',
                 'data_classification', 'encryption_required')

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
    Complete annotation of a service (based on MOF-based Social Web Services).
    Corresponds to the S-WSDL model from the paper.
    """
    __slots__ = ('social_node', 'interaction', 'context', 'policy')

    def __init__(self, service_id=""):
        # Main social node
        self.social_node = SNNode(service_id)
        
        # Complementary annotations (model extension)
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
        """Creates a full annotation from a dictionary (inverse of to_dict)."""
        service_id = data.get('social_node', {}).get('node_id', '')
        annotation = cls(service_id)

        # ── Reconstruct social node ──
        if 'social_node' in data:
            sn_data = data['social_node']
            annotation.social_node.node_type = sn_data.get('node_type', 'WebService')
            annotation.social_node.state = sn_data.get('state', 'active')

            if 'trust_degree' in sn_data:
                annotation.social_node.trust_degree.value = sn_data['trust_degree'].get('value', 0.5)
            if 'reputation' in sn_data:
                annotation.social_node.reputation.value = sn_data['reputation'].get('value', 0.5)
            if 'cooperativeness' in sn_data:
                annotation.social_node.cooperativeness.value = sn_data['cooperativeness'].get('value', 0.5)

            # Properties
            for p in sn_data.get('properties', []):
                annotation.social_node.add_property(p.get('prop_name', ''), p.get('value', 0.0))

            # Associations
            for a_data in sn_data.get('associations', []):
                assoc = SNAssociation()
                assoc.source_node = a_data.get('source_node', '')
                assoc.target_node = a_data.get('target_node', '')
                at = a_data.get('association_type', {})
                assoc.association_type.type_name = at.get('type_name', '')
                assoc.association_type.is_symmetric = at.get('is_symmetric', False)
                assoc.association_type.supports_transitivity = at.get('supports_transitivity', False)
                assoc.association_type.is_dependent = at.get('is_dependent', False)
                assoc.association_type.temporal_aspect = at.get('temporal_aspect', 'permanent')
                aw = a_data.get('association_weight', {})
                assoc.association_weight.prop_name = aw.get('prop_name', '')
                assoc.association_weight.value = aw.get('value', 0.0)
                assoc.association_weight.calculation_method = aw.get('calculation_method', 'interaction_count')
                assoc.duration = a_data.get('duration', 'permanent')
                assoc.creation_date = a_data.get('creation_date')
                assoc.last_interaction = a_data.get('last_interaction')
                annotation.social_node.associations.append(assoc)

        # ── Reconstruct interaction annotation ──
        if 'interaction' in data:
            i = data['interaction']
            annotation.interaction.can_call = i.get('can_call', [])
            annotation.interaction.depends_on = i.get('depends_on', [])
            annotation.interaction.role = i.get('role', 'worker')
            annotation.interaction.collaboration_history = i.get('collaboration_history', {})
            annotation.interaction.substitutes = i.get('substitutes', [])
            annotation.interaction.collaboration_associations = i.get('collaboration_associations', [])
            annotation.interaction.substitution_associations = i.get('substitution_associations', [])
            annotation.interaction.competition_associations = i.get('competition_associations', [])

        # ── Reconstruct context annotation ──
        if 'context' in data:
            c = data['context']
            annotation.context.context_aware = c.get('context_aware', False)
            annotation.context.location_sensitive = c.get('location_sensitive', False)
            annotation.context.time_critical = c.get('time_critical', 'low')
            annotation.context.interaction_count = c.get('interaction_count', 0)
            annotation.context.last_used = c.get('last_used')
            annotation.context.usage_patterns = c.get('usage_patterns', [])
            annotation.context.environmental_requirements = c.get('environmental_requirements', [])
            annotation.context.observed_locations = c.get('observed_locations', {})
            annotation.context.observed_networks = c.get('observed_networks', {})
            annotation.context.observed_devices = c.get('observed_devices', {})
            annotation.context.context_adaptation_score = c.get('context_adaptation_score', 0.0)

        # ── Reconstruct policy annotation ──
        if 'policy' in data:
            p = data['policy']
            annotation.policy.gdpr_compliant = p.get('gdpr_compliant', True)
            annotation.policy.data_retention_days = p.get('data_retention_days', 30)
            annotation.policy.security_level = p.get('security_level', 'medium')
            annotation.policy.privacy_policy = p.get('privacy_policy', 'encrypted')
            annotation.policy.compliance_standards = p.get('compliance_standards', [])
            annotation.policy.data_classification = p.get('data_classification', 'internal')
            annotation.policy.encryption_required = p.get('encryption_required', False)

        return annotation