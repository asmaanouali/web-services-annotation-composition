"""Annotation endpoints — estimate, start (background), progress polling."""

import logging
import math
import threading
import requests as http_requests
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

        if use_llm:
            max_workers = int(data.get("max_workers", 10))
            batch_size = int(data.get("batch_size", 5))
            num_batches = -(-num_services // batch_size)  # ceiling division
            num_waves = math.ceil(num_batches / max_workers)

            # Probe Ollama availability with a quick HEAD-style request
            ollama_url = app_state.get("ollama_url", "http://localhost:11434")
            ollama_reachable = False
            try:
                probe = http_requests.get(
                    f"{ollama_url}/api/tags", timeout=2
                )
                ollama_reachable = probe.status_code == 200
            except Exception:
                pass

            if ollama_reachable:
                # LLM is available: estimate based on model inference time
                # Empirical: ~3-8s per batch depending on batch_size
                per_batch_latency = 2.0 + batch_size * 0.8
            else:
                # Ollama unreachable: each batch will hit connection timeout
                # then fall back to classic (urllib3 retries take ~4s)
                per_batch_latency = 4.0

            # 1. LLM annotation time = waves × per-batch latency + overhead
            wave_overhead = 0.3  # threading dispatch overhead per wave
            annotation_time = num_waves * (per_batch_latency + wave_overhead)
            status_note = "Ollama connected" if ollama_reachable else "Ollama offline — will use classic fallback"
            breakdown["annotation_generation"] = {
                "label": "LLM Annotation Generation" if ollama_reachable else "Annotation (Ollama offline → fallback)",
                "time": annotation_time,
                "detail": (
                    f"{num_batches} batches ÷ {max_workers} workers = "
                    f"{num_waves} waves × ~{per_batch_latency:.1f}s"
                ),
            }

            # 2. Network overhead (only when Ollama is reachable)
            if ollama_reachable:
                network_overhead = num_waves * 0.2
                breakdown["network_overhead"] = {
                    "label": "Network Overhead (Ollama)",
                    "time": network_overhead,
                    "detail": f"{num_waves} waves × ~200ms",
                }
        else:
            # Classic bulk annotation — highly optimized, sub-second for thousands
            # Phase 1 (edge computation): ~0.5ms per service
            phase1_time = num_services * 0.0005 * complexity_factor
            # Phase 2 (assembly): ~1ms per service
            phase2_time = num_services * 0.001 * complexity_factor
            annotation_time = phase1_time + phase2_time
            status_note = None
            breakdown["annotation_generation"] = {
                "label": "Classic Annotation (bulk)",
                "time": annotation_time,
                "detail": (
                    f"{num_services} services × {complexity_factor:.1f}x complexity"
                ),
            }

        # Social association building (same for both modes)
        avg_degree = min(
            avg_io * max(int(total_services ** 0.4), 1), total_services
        )
        estimated_lookups = num_services * avg_degree
        association_time_per_lookup = 0.000005  # 5µs per lookup (optimized indexes)
        association_time = estimated_lookups * association_time_per_lookup
        breakdown["association_building"] = {
            "label": "Social Association Building",
            "time": association_time,
            "detail": f"{num_services} × ~{int(avg_degree)} avg connections × 5µs",
        }

        # Social node property calculation
        property_time = num_services * 0.0002  # 0.2ms per service (inlined QoS)
        breakdown["property_calculation"] = {
            "label": "Social Node Properties",
            "time": property_time,
            "detail": f"{num_services} services × 0.2ms",
        }

        total_time = sum(item["time"] for item in breakdown.values())
        # Add 15% safety margin
        total_time_with_margin = total_time * 1.15

        result = {
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
            "safety_margin": "15%",
        }
        if status_note:
            result["status_note"] = status_note
        return jsonify(result)
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
        max_workers = min(int(data.get("max_workers", 10)), 20)  # cap at 20
        batch_size = min(int(data.get("batch_size", 5)), 10)     # cap at 10
        skip_annotated = data.get("skip_annotated", False)

        _log.info("POST /api/annotate/start  use_llm=%s  service_ids=%s  annotation_types=%s  workers=%d  batch=%d  skip=%s",
                   use_llm, service_ids if service_ids else "ALL", annotation_types, max_workers, batch_size, skip_annotated)

        if not app_state["services"]:
            _log.warning("Annotation start rejected — no services loaded")
            return jsonify({"error": "No services loaded"}), 400

        with state_lock:
            thread = app_state.get("annotation_thread")
            if thread and thread.is_alive():
                _log.warning("Annotation start rejected — already in progress")
                return jsonify({"error": "Annotation already in progress"}), 409
            # Mark as occupied immediately to prevent races
            app_state["annotation_thread"] = threading.current_thread()

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
                    max_workers=max_workers,
                    batch_size=batch_size,
                    skip_annotated=skip_annotated,
                )

                # Update services list
                svc_by_id = {s.id: s for s in annotated}
                for i, s in enumerate(app_state["services"]):
                    if s.id in svc_by_id:
                        app_state["services"][i] = svc_by_id[s.id]

                app_state["annotated_services"] = list(app_state["services"])

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
