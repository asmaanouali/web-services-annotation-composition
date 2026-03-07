"""
Routes package — Flask Blueprints for the service composition API.

Each sub-module defines a Blueprint for a logical group of endpoints.
All blueprints are collected in ``all_blueprints`` for easy registration
in the application factory.
"""

from .health import health_bp
from .training import training_bp
from .services import services_bp
from .annotation import annotation_bp
from .composition import composition_bp
from .history import history_bp
from .context import context_bp

all_blueprints = [
    health_bp,
    training_bp,
    services_bp,
    annotation_bp,
    composition_bp,
    history_bp,
    context_bp,
]

__all__ = ["all_blueprints"]
