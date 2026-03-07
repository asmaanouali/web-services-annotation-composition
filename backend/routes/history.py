"""Interaction history endpoints — status, per-service, clear, import."""

from flask import Blueprint, jsonify

from state import app_state
from validators import safe_route

history_bp = Blueprint("history", __name__)


@history_bp.route("/api/history/status", methods=["GET"])
@safe_route
def get_history_status():
    """Get interaction history summary."""
    store = app_state["interaction_store"]
    return jsonify(store.summary())


@history_bp.route("/api/history/service/<service_id>", methods=["GET"])
@safe_route
def get_service_history(service_id):
    """Get detailed interaction stats for a specific service."""
    store = app_state["interaction_store"]
    return jsonify({
        "service_id": service_id,
        "interaction_count": store.get_interaction_count(service_id),
        "collaboration_counts": store.get_collaboration_counts(service_id),
        "success_rate": store.get_success_rate(service_id),
        "avg_utility": store.get_avg_utility(service_id),
        "last_used": store.get_last_used(service_id),
        "usage_patterns": store.get_usage_patterns(service_id),
        "observed_contexts": store.get_observed_contexts(service_id),
    })


@history_bp.route("/api/history/clear", methods=["POST"])
@safe_route
def clear_history():
    """Clear all interaction history."""
    app_state["interaction_store"].clear()
    if app_state["annotator"]:
        app_state["annotator"].refresh_history_stats()
    return jsonify({"message": "Interaction history cleared"})


@history_bp.route("/api/history/import-training", methods=["POST"])
@safe_route
def import_training_to_history():
    """Import training examples into the interaction history store."""
    examples = app_state["learning_state"].get("training_examples", [])
    if not examples:
        return jsonify({"error": "No training examples available"}), 400
    app_state["interaction_store"].import_from_training(examples)
    if app_state["annotator"]:
        app_state["annotator"].refresh_history_stats()
    return jsonify({
        "message": f"Imported {len(examples)} training examples into history",
        "history": app_state["interaction_store"].summary(),
    })
