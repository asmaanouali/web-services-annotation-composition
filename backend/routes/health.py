"""Health-check and annotation-status endpoints."""

from flask import Blueprint, jsonify

from state import (
    app_state, compute_annotation_status,
    SFT_DEPS_AVAILABLE, REWARD_DEPS_AVAILABLE, RL_DEPS_AVAILABLE,
)
from validators import safe_route

health_bp = Blueprint("health", __name__)


@health_bp.route("/api/health", methods=["GET"])
@safe_route
def health_check():
    """API health check."""
    return jsonify({
        "status": "healthy",
        "services_loaded": len(app_state["services"]),
        "services_annotated": len(app_state["annotated_services"]),
        "requests_loaded": len(app_state["requests"]),
        "is_trained": app_state["learning_state"]["is_trained"],
        "training_examples": len(app_state["learning_state"]["training_examples"]),
        "annotation_status": compute_annotation_status(),
        "interaction_history": app_state["interaction_store"].summary(),
        "sft_available": SFT_DEPS_AVAILABLE,
        "sft_trained": app_state["sft_state"]["is_trained"],
        "reward_available": REWARD_DEPS_AVAILABLE,
        "reward_trained": app_state["reward_state"]["is_trained"],
        "rl_available": RL_DEPS_AVAILABLE,
        "rl_trained": app_state["rl_state"]["is_trained"],
        "rl_algorithm": app_state["rl_state"]["algorithm"],
    })


@health_bp.route("/api/annotation/status", methods=["GET"])
@safe_route
def get_annotation_status():
    """Get current annotation status."""
    status = compute_annotation_status()
    app_state["annotation_status"] = status
    return jsonify(status)
