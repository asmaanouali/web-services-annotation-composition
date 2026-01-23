"""
Models module for service composition system
"""

from .service import WebService, QoS, CompositionRequest, CompositionResult
from .annotation import (
    ServiceAnnotation,
    InteractionAnnotation,
    ContextAnnotation,
    PolicyAnnotation
)

__all__ = [
    'WebService',
    'QoS',
    'CompositionRequest',
    'CompositionResult',
    'ServiceAnnotation',
    'InteractionAnnotation',
    'ContextAnnotation',
    'PolicyAnnotation'
]