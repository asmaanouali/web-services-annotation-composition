"""
Composition models — re-exports from service.py for convenience.

The canonical definitions of CompositionRequest and CompositionResult
live in models.service.  This module re-exports them so that callers
can write ``from models.composition import CompositionRequest``.
"""

from models.service import CompositionRequest, CompositionResult

__all__ = ["CompositionRequest", "CompositionResult"]