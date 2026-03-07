"""Composition endpoints — classic, LLM, compare, batch, chat, best-solutions."""

from datetime import datetime
from flask import Blueprint, request, jsonify

from state import app_state
from helpers import parse_xml_upload, calculate_statistics, calculate_formal_metrics, generate_comparison_discussion
from services.classic_composer import ClassicComposer
from services.llm_composer import LLMComposer
from services.wsdl_parser import parse_requests_xml, parse_best_solutions_xml
from models.context import (
    ExecutionContext,
    compute_context_score,
    adapt_qos_constraints_for_context,
)
from validators import safe_route, require_json, require_fields

composition_bp = Blueprint("composition", __name__)


# ── Requests upload (prerequisite to composition) ─────────────────

@composition_bp.route("/api/requests/upload", methods=["POST"])
@safe_route
def upload_requests():
    """Upload composition requests XML file."""
    try:
        file = request.files.get("file")
        if not file:
            return jsonify({"error": "No file provided"}), 400

        requests_list = parse_xml_upload(file, parse_requests_xml)
        app_state["requests"] = requests_list
        print(f"Parsed {len(requests_list)} requests")

        return jsonify({
            "message": f"{len(requests_list)} requests loaded",
            "requests": [r.to_dict() for r in requests_list],
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@composition_bp.route("/api/requests", methods=["GET"])
@safe_route
def get_requests():
    """Retrieve requests list."""
    return jsonify({
        "requests": [r.to_dict() for r in app_state["requests"]],
        "total": len(app_state["requests"]),
    })


# ── Classic composition (Solution A) ─────────────────────────────

@composition_bp.route("/api/compose/classic", methods=["POST"])
@safe_route
@require_json
@require_fields("request_id")
def compose_classic():
    """Classic composition (Solution A) — context-aware."""
    try:
        data = request.json
        request_id = data.get("request_id")
        algorithm = data.get("algorithm", "dijkstra")

        comp_request = next(
            (r for r in app_state["requests"] if r.id == request_id), None
        )
        if not comp_request:
            return jsonify({"error": "Request not found"}), 404

        # Extract execution context
        exec_ctx = ExecutionContext.from_request(request)

        # Adapt QoS constraints for current context
        adapted_constraints = adapt_qos_constraints_for_context(
            comp_request.qos_constraints, exec_ctx
        )
        original_constraints = comp_request.qos_constraints
        comp_request.qos_constraints = adapted_constraints

        if not app_state["classic_composer"]:
            services = app_state["annotated_services"] or app_state["services"]
            app_state["classic_composer"] = ClassicComposer(services)

        result = app_state["classic_composer"].compose(comp_request, algorithm)
        app_state["results_classic"][request_id] = result

        # Restore original constraints
        comp_request.qos_constraints = original_constraints

        # Record interaction in history
        service_ids = [
            s.id if hasattr(s, "id") else s for s in result.services
        ]
        if service_ids:
            app_state["interaction_store"].record_composition(
                composition_id=f"classic_{request_id}_{algorithm}",
                service_ids=service_ids,
                success=result.success,
                utility=result.utility_value,
                context=exec_ctx.to_flat_dict(),
                response_time_ms=result.computation_time * 1000,
            )
            if app_state["annotator"]:
                app_state["annotator"].refresh_history_stats()

        resp = result.to_dict()
        resp["context_used"] = exec_ctx.to_dict()
        return jsonify(resp)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── LLM composition (Solution B) ─────────────────────────────────

@composition_bp.route("/api/compose/llm", methods=["POST"])
@safe_route
@require_json
@require_fields("request_id")
def compose_llm():
    """Intelligent composition with LLM (Solution B) — context-aware + learning.
    Requires services to be annotated first."""
    try:
        annotated_count = sum(
            1 for s in app_state["services"]
            if hasattr(s, "annotations") and s.annotations is not None
        )
        if annotated_count == 0:
            return jsonify({
                "error": "Services must be annotated before LLM composition",
                "message": (
                    "Please annotate the services first in Tab 2 "
                    "(Automatic Annotation) before using intelligent composition."
                ),
                "services_annotated": False,
                "annotation_count": 0,
                "total_services": len(app_state["services"]),
            }), 400

        data = request.json
        request_id = data.get("request_id")
        enable_reasoning = data.get("enable_reasoning", True)
        enable_adaptation = data.get("enable_adaptation", True)

        comp_request = next(
            (r for r in app_state["requests"] if r.id == request_id), None
        )
        if not comp_request:
            return jsonify({"error": "Request not found"}), 404

        # Extract execution context & adapt constraints
        exec_ctx = ExecutionContext.from_request(request)
        adapted_constraints = adapt_qos_constraints_for_context(
            comp_request.qos_constraints, exec_ctx
        )
        original_constraints = comp_request.qos_constraints
        comp_request.qos_constraints = adapted_constraints

        if not app_state["llm_composer"]:
            services = app_state["annotated_services"] or app_state["services"]
            app_state["llm_composer"] = LLMComposer(
                services,
                training_examples=app_state["learning_state"]["training_examples"],
            )

        result = app_state["llm_composer"].compose(
            comp_request,
            enable_reasoning=enable_reasoning,
            enable_adaptation=enable_adaptation,
        )
        app_state["results_llm"][request_id] = result

        # Restore original constraints
        comp_request.qos_constraints = original_constraints

        # Continuous learning: record composition
        composition_record = {
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id,
            "request": comp_request.to_dict(),
            "result": result.to_dict(),
            "success": result.success,
            "utility": result.utility_value,
            "context": exec_ctx.to_dict(),
        }
        app_state["learning_state"]["composition_history"].append(composition_record)

        # Record interaction in history store
        service_ids = [
            s.id if hasattr(s, "id") else s for s in result.services
        ]
        if service_ids:
            app_state["interaction_store"].record_composition(
                composition_id=f"llm_{request_id}",
                service_ids=service_ids,
                success=result.success,
                utility=result.utility_value,
                context=exec_ctx.to_flat_dict(),
                response_time_ms=result.computation_time * 1000,
            )
            if app_state["annotator"]:
                app_state["annotator"].refresh_history_stats()

        # Update performance metrics
        metrics = app_state["learning_state"]["performance_metrics"]
        metrics["total_compositions"] += 1
        if result.success:
            metrics["successful_compositions"] += 1

        history = app_state["learning_state"]["composition_history"]
        total_utility = sum(r["utility"] for r in history)
        metrics["average_utility"] = total_utility / len(history)

        if len(history) >= 10:
            recent_avg = sum(r["utility"] for r in history[-10:]) / 10
            overall_avg = metrics["average_utility"]
            metrics["learning_rate"] = (
                ((recent_avg - overall_avg) / overall_avg * 100)
                if overall_avg > 0 else 0
            )

        # Learn from this composition
        app_state["llm_composer"].learn_from_composition(composition_record)

        resp = result.to_dict()
        resp["context_used"] = exec_ctx.to_dict()
        return jsonify(resp)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Chat ──────────────────────────────────────────────────────────

@composition_bp.route("/api/llm/chat", methods=["POST"])
@safe_route
@require_json
@require_fields("message")
def llm_chat():
    """Chat with LLM."""
    try:
        data = request.json
        message = data.get("message", "")

        if not app_state["llm_composer"]:
            services = app_state["annotated_services"] or app_state["services"]
            app_state["llm_composer"] = LLMComposer(services)

        response = app_state["llm_composer"].chat(message)
        return jsonify({"response": response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Comparison endpoints ──────────────────────────────────────────

@composition_bp.route("/api/best-solutions/upload", methods=["POST"])
@safe_route
def upload_best_solutions():
    """Upload best solutions XML file."""
    try:
        file = request.files.get("file")
        if not file:
            return jsonify({"error": "No file provided"}), 400

        solutions = parse_xml_upload(file, parse_best_solutions_xml)
        app_state["best_solutions"] = solutions
        print(f"Parsed {len(solutions)} best solutions")

        return jsonify({
            "message": f"{len(solutions)} best solutions loaded",
            "solutions": solutions,
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@composition_bp.route("/api/compose/compare", methods=["POST"])
@safe_route
@require_json
@require_fields("request_id")
def compose_compare():
    """Run all three classic algorithms + LLM on the same request."""
    try:
        data = request.json
        request_id = data.get("request_id")

        comp_request = next(
            (r for r in app_state["requests"] if r.id == request_id), None
        )
        if not comp_request:
            return jsonify({"error": "Request not found"}), 404

        results = {}

        # Classic algorithms
        if app_state["classic_composer"]:
            for algo in ["dijkstra", "astar", "greedy"]:
                try:
                    result = app_state["classic_composer"].compose(comp_request, algo)
                    results[algo] = result.to_dict()
                    app_state["results_classic"][f"{request_id}_{algo}"] = result
                except Exception as e:
                    results[algo] = {
                        "success": False, "error": str(e),
                        "utility_value": 0, "computation_time": 0,
                    }

        # LLM composition
        annotated_count = sum(
            1 for s in app_state["services"]
            if hasattr(s, "annotations") and s.annotations is not None
        )
        if app_state["llm_composer"] and annotated_count > 0:
            try:
                llm_result = app_state["llm_composer"].compose(comp_request)
                results["llm"] = llm_result.to_dict()
                app_state["results_llm"][request_id] = llm_result
            except Exception as e:
                results["llm"] = {
                    "success": False, "error": str(e),
                    "utility_value": 0, "computation_time": 0,
                }
        else:
            results["llm"] = {
                "success": False,
                "error": "LLM not available or services not annotated",
                "utility_value": 0, "computation_time": 0,
            }

        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@composition_bp.route("/api/compose/batch", methods=["POST"])
@safe_route
def compose_batch():
    """Batch compose all requests with classic + LLM."""
    try:
        data = request.json or {}
        algorithm = data.get("algorithm", "dijkstra")
        request_ids = data.get("request_ids", [r.id for r in app_state["requests"]])

        results = {}
        annotated_count = sum(
            1 for s in app_state["services"]
            if hasattr(s, "annotations") and s.annotations is not None
        )

        for req_id in request_ids:
            comp_request = next(
                (r for r in app_state["requests"] if r.id == req_id), None
            )
            if not comp_request:
                continue

            entry = {"classic": None, "llm": None}

            # Classic composition
            if app_state["classic_composer"]:
                try:
                    result = app_state["classic_composer"].compose(comp_request, algorithm)
                    app_state["results_classic"][req_id] = result
                    entry["classic"] = result.to_dict()
                except Exception as e:
                    entry["classic"] = {
                        "success": False, "error": str(e),
                        "utility_value": 0, "computation_time": 0,
                    }

            # LLM composition
            if app_state["llm_composer"] and annotated_count > 0:
                try:
                    llm_result = app_state["llm_composer"].compose(comp_request)
                    app_state["results_llm"][req_id] = llm_result
                    entry["llm"] = llm_result.to_dict()
                except Exception as e:
                    entry["llm"] = {
                        "success": False, "error": str(e),
                        "utility_value": 0, "computation_time": 0,
                    }

            results[req_id] = entry

        return jsonify({"results": results, "total": len(results)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@composition_bp.route("/api/comparison", methods=["GET"])
@safe_route
def get_comparison():
    """Enhanced comparison: Solution A vs B vs Best Solutions with rich metrics."""
    try:
        comparisons = []

        for req in app_state["requests"]:
            req_id = req.id
            comparison = {
                "request_id": req_id,
                "best_known": app_state["best_solutions"].get(req_id),
                "classic": None,
                "llm": None,
            }

            classic_result = app_state["results_classic"].get(req_id)
            if classic_result:
                comparison["classic"] = (
                    classic_result.to_dict()
                    if hasattr(classic_result, "to_dict") else classic_result
                )

            llm_result = app_state["results_llm"].get(req_id)
            if llm_result:
                comparison["llm"] = (
                    llm_result.to_dict()
                    if hasattr(llm_result, "to_dict") else llm_result
                )

            comparisons.append(comparison)

        stats = calculate_statistics(comparisons)

        # Formal evaluation metrics (precision, recall, F1) vs best-known
        formal_metrics = calculate_formal_metrics(comparisons)

        training_impact = {
            "is_trained": app_state["learning_state"]["is_trained"],
            "training_examples": len(app_state["learning_state"]["training_examples"]),
            "composition_history": len(app_state["learning_state"]["composition_history"]),
            "performance_metrics": app_state["learning_state"]["performance_metrics"],
        }

        resp = {
            "comparisons": comparisons,
            "statistics": stats,
            "training_impact": training_impact,
            "total_requests": len(app_state["requests"]),
            "total_services": len(app_state["services"]),
            "annotated_services": sum(
                1 for s in app_state["services"]
                if hasattr(s, "annotations") and s.annotations is not None
            ),
        }
        if formal_metrics:
            resp["formal_metrics"] = formal_metrics

        # Analytical discussion — requirement 2c
        resp["discussion"] = generate_comparison_discussion(
            stats, formal_metrics, training_impact
        )

        return jsonify(resp)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
