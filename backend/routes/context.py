"""Context endpoints — current execution context, context score for a service."""

from flask import Blueprint, request, jsonify

from state import app_state
from models.context import ExecutionContext, compute_context_score
from validators import safe_route

context_bp = Blueprint("context", __name__)


@context_bp.route("/api/context/current", methods=["GET"])
@safe_route
def get_current_context():
    """Extract and return the current execution context from the request."""
    exec_ctx = ExecutionContext.from_request(request)
    return jsonify(exec_ctx.to_dict())


@context_bp.route("/api/context/score/<service_id>", methods=["POST"])
@safe_route
def get_context_score(service_id):
    """Compute context compatibility score for a service vs current context."""
    service = next(
        (s for s in app_state["services"] if s.id == service_id), None
    )
    if not service:
        return jsonify({"error": "Service not found"}), 404

    exec_ctx = ExecutionContext.from_request(request)
    observed = app_state["interaction_store"].get_observed_contexts(service_id)
    score = compute_context_score(service, exec_ctx, observed)

    return jsonify({
        "service_id": service_id,
        "context_score": round(score, 4),
        "context": exec_ctx.to_dict(),
        "observed_contexts": observed,
    })
