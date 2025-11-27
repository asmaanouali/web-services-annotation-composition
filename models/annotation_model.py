"""
models/annotation_model.py
Modèle de données pour les annotations basé sur le papier de référence [1]
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum

class AnnotationType(Enum):
    """Types d'annotations selon le modèle"""
    FUNCTIONAL = "functional"  # Capacités fonctionnelles du service
    INTERACTION = "interaction"  # Interactions avec d'autres services
    CONTEXT = "context"  # Contexte d'utilisation
    POLICY = "policy"  # Politiques d'usage


class PrivacyLevel(Enum):
    """Niveaux de confidentialité des données"""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class ServiceCategory(Enum):
    """Catégories de services"""
    SEARCH = "search"
    BOOKING = "booking"
    PAYMENT = "payment"
    INFORMATION = "information"
    NOTIFICATION = "notification"


@dataclass
class ParameterMapping:
    """Mapping entre paramètres de différents services"""
    source_param: str
    target_param: str
    transformation: Optional[str] = None  # e.g., "date_format", "currency_conversion"
    confidence: float = 1.0


@dataclass
class QualityMetrics:
    """Métriques de qualité du service"""
    reliability: float = 0.0  # 0-1
    response_time_ms: int = 0
    availability: float = 0.0  # 0-1
    success_rate: float = 0.0  # 0-1
    cost_per_call: float = 0.0


@dataclass
class FunctionalAnnotation:
    """Annotation fonctionnelle - capacités du service"""
    annotation_type: AnnotationType = AnnotationType.FUNCTIONAL
    
    # Informations de base
    service_name: str = ""
    service_category: ServiceCategory = ServiceCategory.SEARCH
    operation_name: str = ""
    
    # Capacités fonctionnelles
    capabilities: List[str] = field(default_factory=list)
    input_parameters: List[str] = field(default_factory=list)
    output_parameters: List[str] = field(default_factory=list)
    
    # Description sémantique
    semantic_description: str = ""
    keywords: List[str] = field(default_factory=list)
    
    # Contraintes fonctionnelles
    required_inputs: List[str] = field(default_factory=list)
    optional_inputs: List[str] = field(default_factory=list)
    
    # Features spécifiques
    special_features: Dict[str, Any] = field(default_factory=dict)
    # Ex: {"supports_multi_currency": true, "max_passengers": 9}


@dataclass
class InteractionAnnotation:
    """Annotation d'interaction - relations avec autres services"""
    annotation_type: AnnotationType = AnnotationType.INTERACTION
    
    # Services compatibles
    compatible_services: List[str] = field(default_factory=list)
    
    # Dépendances
    requires_services: List[str] = field(default_factory=list)  # Services nécessaires avant
    provides_for_services: List[str] = field(default_factory=list)  # Services qui peuvent suivre
    
    # Mappings de paramètres
    parameter_mappings: List[ParameterMapping] = field(default_factory=list)
    
    # Orchestration
    orchestration_hints: Dict[str, Any] = field(default_factory=dict)
    # Ex: {"can_be_parallel": true, "timeout_seconds": 30}
    
    # Historique d'interactions
    successful_compositions: List[str] = field(default_factory=list)
    failed_compositions: List[str] = field(default_factory=list)
    
    # Métriques de qualité
    quality_metrics: QualityMetrics = field(default_factory=QualityMetrics)


@dataclass
class ContextConstraint:
    """Contrainte contextuelle"""
    constraint_type: str  # "location", "time", "user_preference", "device"
    condition: str  # Expression de la condition
    description: str


@dataclass
class ContextAnnotation:
    """Annotation de contexte - conditions d'utilisation"""
    annotation_type: AnnotationType = AnnotationType.CONTEXT
    
    # Contexte géographique
    geographic_coverage: List[str] = field(default_factory=list)  # ["EU", "US", "GLOBAL"]
    location_aware: bool = False
    
    # Contexte temporel
    temporal_constraints: List[str] = field(default_factory=list)
    # Ex: ["business_hours_only", "24/7_available"]
    timezone_support: bool = True
    
    # Contexte utilisateur
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    # Ex: {"preferred_language": ["en", "fr"], "accessibility_required": false}
    
    # Contexte environnemental
    network_requirements: Dict[str, Any] = field(default_factory=dict)
    # Ex: {"min_bandwidth_mbps": 1, "supports_offline": false}
    
    # Contexte de l'application
    application_context: Dict[str, Any] = field(default_factory=dict)
    # Ex: {"use_case": "travel_booking", "user_type": "business"}
    
    # Contraintes contextuelles
    constraints: List[ContextConstraint] = field(default_factory=list)
    
    # Adaptabilité
    adaptation_capabilities: List[str] = field(default_factory=list)
    # Ex: ["auto_retry", "fallback_available", "caching_enabled"]


@dataclass
class DataPrivacyPolicy:
    """Politique de confidentialité des données"""
    data_field: str
    privacy_level: PrivacyLevel
    retention_days: int
    encryption_required: bool
    can_be_shared: bool
    compliance_requirements: List[str] = field(default_factory=list)  # ["GDPR", "PCI-DSS"]


@dataclass
class UsagePolicy:
    """Politique d'usage du service"""
    rate_limit: Optional[int] = None  # Requests per hour
    quota_per_day: Optional[int] = None
    requires_authentication: bool = True
    authentication_methods: List[str] = field(default_factory=list)
    
    # Coûts
    pricing_model: str = "pay_per_use"  # "free", "subscription", "pay_per_use"
    cost_per_request: float = 0.0
    currency: str = "USD"
    
    # SLA
    guaranteed_uptime: float = 0.99
    max_response_time_ms: int = 5000


@dataclass
class PolicyAnnotation:
    """Annotation de politique - règles d'usage et confidentialité"""
    annotation_type: AnnotationType = AnnotationType.POLICY
    
    # Politiques de confidentialité
    privacy_policies: List[DataPrivacyPolicy] = field(default_factory=list)
    
    # Politique d'usage
    usage_policy: UsagePolicy = field(default_factory=UsagePolicy)
    
    # Sécurité
    security_requirements: List[str] = field(default_factory=list)
    # Ex: ["TLS_1.3", "API_KEY", "OAUTH2"]
    
    # Conformité réglementaire
    compliance_standards: List[str] = field(default_factory=list)
    # Ex: ["GDPR", "PCI-DSS", "SOC2"]
    
    # Restrictions d'usage
    usage_restrictions: List[str] = field(default_factory=list)
    # Ex: ["no_scraping", "commercial_use_only"]
    
    # Termes et conditions
    terms_url: Optional[str] = None
    privacy_policy_url: Optional[str] = None


@dataclass
class ServiceAnnotation:
    """Annotation complète d'un service web"""
    
    # Métadonnées
    annotation_id: str
    service_name: str
    wsdl_location: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: str = "1.0"
    
    # Les 4 types d'annotations
    functional: FunctionalAnnotation = field(default_factory=FunctionalAnnotation)
    interaction: InteractionAnnotation = field(default_factory=InteractionAnnotation)
    context: ContextAnnotation = field(default_factory=ContextAnnotation)
    policy: PolicyAnnotation = field(default_factory=PolicyAnnotation)
    
    # Metadata additionnelle
    tags: List[str] = field(default_factory=list)
    confidence_score: float = 1.0  # Confiance dans l'annotation (0-1)
    
    def to_dict(self) -> Dict:
        """Convertit l'annotation en dictionnaire"""
        return {
            "annotation_id": self.annotation_id,
            "service_name": self.service_name,
            "wsdl_location": self.wsdl_location,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
            "functional": self._dataclass_to_dict(self.functional),
            "interaction": self._dataclass_to_dict(self.interaction),
            "context": self._dataclass_to_dict(self.context),
            "policy": self._dataclass_to_dict(self.policy),
            "tags": self.tags,
            "confidence_score": self.confidence_score
        }
    
    def _dataclass_to_dict(self, obj) -> Dict:
        """Convertit récursivement un dataclass en dict"""
        if hasattr(obj, '__dataclass_fields__'):
            result = {}
            for field_name, field_def in obj.__dataclass_fields__.items():
                value = getattr(obj, field_name)
                if isinstance(value, Enum):
                    result[field_name] = value.value
                elif isinstance(value, list):
                    result[field_name] = [self._dataclass_to_dict(item) if hasattr(item, '__dataclass_fields__') else item for item in value]
                elif hasattr(value, '__dataclass_fields__'):
                    result[field_name] = self._dataclass_to_dict(value)
                else:
                    result[field_name] = value
            return result
        return obj


# Exemple d'utilisation
if __name__ == "__main__":
    # Créer une annotation exemple
    annotation = ServiceAnnotation(
        annotation_id="amadeus_flight_001",
        service_name="AmadeusFlightService",
        wsdl_location="services/wsdl/original/AmadeusFlightService.wsdl"
    )
    
    # Annotation fonctionnelle
    annotation.functional.service_category = ServiceCategory.SEARCH
    annotation.functional.capabilities = [
        "search_flights",
        "multi_city_search",
        "flexible_dates"
    ]
    
    # Annotation de contexte
    annotation.context.geographic_coverage = ["GLOBAL"]
    annotation.context.location_aware = True
    
    # Annotation de politique
    annotation.policy.usage_policy.cost_per_request = 0.01
    annotation.policy.compliance_standards = ["PCI-DSS", "GDPR"]
    
    print("Modèle d'annotation créé avec succès!")
    print(f"Service: {annotation.service_name}")
    print(f"Catégorie: {annotation.functional.service_category.value}")