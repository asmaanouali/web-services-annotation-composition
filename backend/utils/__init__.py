"""
Utility functions for QoS calculations
"""

from .qos_calculator import (
    calculate_utility,
    normalize,
    normalize_inverse,
    aggregate_qos,
    compare_qos
)

__all__ = [
    'calculate_utility',
    'normalize',
    'normalize_inverse',
    'aggregate_qos',
    'compare_qos'
]