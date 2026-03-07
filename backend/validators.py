"""
Request validation helpers for API endpoints.

Provides reusable decorators and functions for input validation,
keeping route handlers clean and consistent.
"""

import logging
from flask import request, jsonify
from functools import wraps

logger = logging.getLogger(__name__)

VALID_ALGORITHMS = {"dijkstra", "astar", "greedy"}
VALID_ANNOTATION_TYPES = {"interaction", "context", "policy"}
VALID_RL_ALGORITHMS = {"GRPO", "PPO"}


# ── Decorators ─────────────────────────────────────────────────────

def require_json(f):
    """Decorator: reject requests that are missing a JSON body."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400
        return f(*args, **kwargs)
    return wrapper


def require_fields(*fields):
    """Decorator factory: reject requests missing any of the listed JSON fields."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            data = request.get_json(silent=True) or {}
            missing = [field for field in fields if field not in data]
            if missing:
                return jsonify({
                    "error": f"Missing required fields: {', '.join(missing)}"
                }), 400
            return f(*args, **kwargs)
        return wrapper
    return decorator


def require_files(*file_keys):
    """Decorator factory: reject requests missing any of the listed file fields."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            missing = [k for k in file_keys if k not in request.files]
            if missing:
                return jsonify({
                    "error": f"Missing required file(s): {', '.join(missing)}"
                }), 400
            return f(*args, **kwargs)
        return wrapper
    return decorator


def safe_route(f):
    """Decorator: catch any unhandled exception and return a structured 500.

    This ensures **every** endpoint returns valid JSON even on unexpected
    errors, instead of a raw HTML 500 from Flask.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as exc:
            logger.exception("Unhandled error in %s", f.__name__)
            return jsonify({"error": str(exc)}), 500
    return wrapper


def validate_algorithm(algorithm):
    """Return an error response if *algorithm* is invalid, else ``None``."""
    if algorithm not in VALID_ALGORITHMS:
        return jsonify({
            "error": f"Unknown algorithm '{algorithm}'. "
                     f"Valid: {', '.join(sorted(VALID_ALGORITHMS))}"
        }), 400
    return None


def validate_annotation_types(types):
    """Return an error response if any annotation type is invalid, else ``None``."""
    invalid = set(types) - VALID_ANNOTATION_TYPES
    if invalid:
        return jsonify({
            "error": f"Invalid annotation types: {', '.join(invalid)}. "
                     f"Valid: {', '.join(sorted(VALID_ANNOTATION_TYPES))}"
        }), 400
    return None


def validate_rl_algorithm(algorithm):
    """Return an error response if RL algorithm is invalid, else ``None``."""
    if algorithm not in VALID_RL_ALGORITHMS:
        return jsonify({
            "error": f"Unknown RL algorithm '{algorithm}'. "
                     f"Valid: {', '.join(sorted(VALID_RL_ALGORITHMS))}"
        }), 400
    return None
