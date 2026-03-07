"""Annotation endpoints — estimate, start (background), progress polling."""

import logging
import threading
from flask import Blueprint, request, jsonify

from state import app_state, state_lock, compute_annotation_status
from services.annotator import ServiceAnnotator
from services.classic_composer import ClassicComposer
from services.llm_composer import LLMComposer
from validators import safe_route

annotation_bp = Blueprint("annotation", __name__)
_log = logging.getLogger("annotation")  # shares the file handler set up by annotator


@annotation_bp.route("/api/annotate/estimate", methods=["POST"])
@safe_route
def estimate_annotation_time():
    """Estimate annotation time with detailed breakdown."""
    try:
        data = request.json or {}
        use_llm = data.get("use_llm", False)
        service_ids = data.get("service_ids", None)
        annotation_types = data.get(
            "annotation_types", ["interaction", "context", "policy"]
        )

        if service_ids:
            target_services = [s for s in app_state["services"] if s.id in service_ids]
        else:
            target_services = app_state["services"]

        num_services = len(target_services)
        num_types = len(annotation_types)
        total_services = len(app_state["services"])

        # Complexity analysis
        if target_services:
            avg_inputs = sum(len(s.inputs) for s in target_services) / num_services
            avg_outputs = sum(len(s.outputs) for s in target_services) / num_services
            avg_io = avg_inputs + avg_outputs
        else:
            avg_inputs = avg_outputs = avg_io = 0

        complexity_factor = 1.0 + (avg_io / 15.0)

        breakdown = {}

        # 1. Base processing
        base_time_per_service = 0.005
        breakdown["base_processing"] = {
            "label": "Base Processing",
            "time": num_services * base_time_per_service,
            "detail": f"{num_services} services x {base_time_per_service*1000:.0f}ms",
        }

        # 2. Annotation generation
        if use_llm:
            llm_latency = 5.0
            max_workers = 10
            sequential_time = num_services * llm_latency
            annotation_time = sequential_time / max_workers
            breakdown["annotation_generation"] = {
                "label": "LLM Annotation Generation",
                "time": annotation_time,
                "detail": (
                    f"{num_services} services x ~{llm_latency}s per call "
                    f"/ {max_workers} workers"
                ),
            }
        else:
            classic_time_per_type = 0.005
            annotation_time = (
                num_services * num_types * classic_time_per_type * complexity_factor
            )
            breakdown["annotation_generation"] = {
                "label": "Classic Annotation Generation",
                "time": annotation_time,
                "detail": (
                    f"{num_services} x {num_types} types x "
                    f"{classic_time_per_type*1000:.0f}ms x {complexity_factor:.1f}x"
                ),
            }

        # 3. Social association building
        avg_degree = min(
            avg_io * max(int(total_services ** 0.4), 1), total_services
        )
        estimated_lookups = num_services * avg_degree
        association_time_per_lookup = 0.00005
        association_time = estimated_lookups * association_time_per_lookup
        breakdown["association_building"] = {
            "label": "Social Association Building",
            "time": association_time,
            "detail": f"{num_services} x ~{int(avg_degree)} avg connections x 50us",
        }

        # 4. Social node property calculation
        property_time = num_services * 0.002
        breakdown["property_calculation"] = {
            "label": "Social Node Properties",
            "time": property_time,
            "detail": f"{num_services} services x 2ms",
        }

        # 5. Network overhead (LLM only)
        if use_llm:
            max_workers = 10
            network_overhead = (num_services * 0.3) / max_workers
            breakdown["network_overhead"] = {
                "label": "Network Overhead (Ollama)",
                "time": network_overhead,
                "detail": f"{num_services} API calls x ~300ms / {max_workers} workers",
            }

        total_time = sum(item["time"] for item in breakdown.values())
        total_time_with_margin = total_time * 1.1

        return jsonify({
            "estimated_time_seconds": total_time_with_margin,
            "num_services": num_services,
            "num_annotation_types": num_types,
            "use_llm": use_llm,
            "annotation_types": annotation_types,
            "complexity_factor": round(complexity_factor, 2),
            "avg_io_per_service": round(avg_io, 1),
            "avg_inputs": round(avg_inputs, 1),
            "avg_outputs": round(avg_outputs, 1),
            "total_services_in_repo": total_services,
            "breakdown": breakdown,
            "safety_margin": "10%",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@annotation_bp.route("/api/annotate/start", methods=["POST"])
@safe_route
def start_annotation():
    """Start automatic service annotation in a background thread.
    Returns 202 immediately; poll /api/annotate/progress for status."""
    try:
        data = request.json or {}
        use_llm = data.get("use_llm", False)
        service_ids = data.get("service_ids", None)
        annotation_types = data.get(
            "annotation_types", ["interaction", "context", "policy"]
        )

        _log.info("POST /api/annotate/start  use_llm=%s  service_ids=%s  annotation_types=%s",
                   use_llm, service_ids if service_ids else "ALL", annotation_types)

        if not app_state["services"]:
            _log.warning("Annotation start rejected — no services loaded")
            return jsonify({"error": "No services loaded"}), 400

        thread = app_state.get("annotation_thread")
        if thread and thread.is_alive():
            _log.warning("Annotation start rejected — already in progress")
            return jsonify({"error": "Annotation already in progress"}), 409

        if not app_state["annotator"]:
            app_state["annotator"] = ServiceAnnotator(
                app_state["services"],
                training_examples=app_state["learning_state"].get("training_examples"),
                interaction_store=app_state["interaction_store"],
            )

        total = len(service_ids) if service_ids else len(app_state["services"])

        with state_lock:
            app_state["annotation_progress"] = {
                "current": 0,
                "total": total,
                "current_service": "",
                "completed": False,
                "error": None,
                "result": None,
            }

        # ── background worker ──
        def _annotation_worker():
            try:
                log_every = max(total // 200, 1)

                def progress_callback(current, _total, service_id):
                    with state_lock:
                        p = app_state["annotation_progress"]
                        p["current"] = current
                        p["total"] = _total
                        p["current_service"] = service_id
                    if current % log_every == 0 or current == _total:
                        print(f"Annotation progress: {current}/{_total} - {service_id}")

                annotated = app_state["annotator"].annotate_all(
                    service_ids=service_ids,
                    use_llm=use_llm,
                    annotation_types=annotation_types,
                    progress_callback=progress_callback,
                )

                # Update services list
                svc_by_id = {s.id: s for s in annotated}
                for i, s in enumerate(app_state["services"]):
                    if s.id in svc_by_id:
                        app_state["services"][i] = svc_by_id[s.id]

                app_state["annotated_services"] = app_state["services"]

                # Rebuild composers
                app_state["classic_composer"] = ClassicComposer(app_state["services"])
                if app_state["learning_state"]["is_trained"]:
                    app_state["llm_composer"] = LLMComposer(
                        app_state["services"],
                        training_examples=app_state["learning_state"]["training_examples"],
                    )
                else:
                    app_state["llm_composer"] = LLMComposer(app_state["services"])

                app_state["annotation_status"] = compute_annotation_status()

                with state_lock:
                    app_state["annotation_progress"]["completed"] = True
                    app_state["annotation_progress"]["result"] = {
                        "message": "Annotation completed",
                        "total_annotated": len(annotated),
                        "services": [s.to_dict() for s in annotated],
                        "annotation_types": annotation_types,
                        "used_llm": use_llm,
                    }
                print(f"Annotation finished: {len(annotated)} services annotated.")
                _log.info("Background worker COMPLETED  annotated=%d  use_llm=%s", len(annotated), use_llm)

            except Exception as exc:
                import traceback
                traceback.print_exc()
                _log.error("Background worker FAILED: %s", exc, exc_info=True)
                with state_lock:
                    app_state["annotation_progress"]["error"] = str(exc)
                    app_state["annotation_progress"]["completed"] = True

        t = threading.Thread(target=_annotation_worker, daemon=True)
        app_state["annotation_thread"] = t
        t.start()

        return jsonify({"message": "Annotation started in background", "total": total}), 202

    except Exception as e:
        with state_lock:
            app_state["annotation_progress"]["error"] = str(e)
            app_state["annotation_progress"]["completed"] = True
        return jsonify({"error": str(e)}), 500


@annotation_bp.route("/api/annotate/progress", methods=["GET"])
@safe_route
def get_annotation_progress():
    """Retrieve annotation progress. When completed, 'result' holds the final data."""
    with state_lock:
        progress = app_state.get(
            "annotation_progress",
            {
                "current": 0,
                "total": 0,
                "current_service": "",
                "completed": False,
                "error": None,
                "result": None,
            },
        ).copy()
    return jsonify(progress)
