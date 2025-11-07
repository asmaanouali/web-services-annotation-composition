"""
Module annotation - Détection de patterns et analyse de performance
"""

from src.annotation.pattern_detector import CompositionPatternDetector
from src.annotation.performance_analyzer import ContextualPerformanceAnalyzer
from src.annotation.policy_manager import PolicyManager, PolicyType

__all__ = [
    "CompositionPatternDetector",
    "ContextualPerformanceAnalyzer",
    "PolicyManager",
    "PolicyType"
]