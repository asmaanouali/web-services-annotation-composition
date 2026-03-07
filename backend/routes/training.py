"""Training endpoints — knowledge-base, SFT Phase 1, Reward Phase 2, RL Phase 3."""

import threading
from flask import Blueprint, request, jsonify

from state import (
    app_state, state_lock,
    SFT_DEPS_AVAILABLE, SFT_MISSING,
    REWARD_DEPS_AVAILABLE, REWARD_MISSING,
    RL_DEPS_AVAILABLE, RL_MISSING,
)
from helpers import parse_xml_upload
from validators import require_json, validate_rl_algorithm, safe_route
from services.wsdl_parser import parse_requests_xml, parse_best_solutions_xml
from services.llm_composer import LLMComposer

training_bp = Blueprint("training", __name__)


# ── Helper: ensure LLM composer exists ────────────────────────────

def _ensure_llm_composer():
    if not app_state["llm_composer"]:
        services = app_state["annotated_services"] or app_state["services"]
        app_state["llm_composer"] = LLMComposer(services)


# ============== DATA UPLOAD ==============

@training_bp.route("/api/training/upload-data", methods=["POST"])
@safe_route
def upload_training_data():
    """Upload training data (WSDL + requests + solutions + best solutions)."""
    try:
        wsdl_files = request.files.getlist("wsdl_files")
        requests_file = request.files.get("requests_file")
        solutions_file = request.files.get("solutions_file")
        best_solutions_file = request.files.get("best_solutions_file")

        training_services = []
        training_requests = []
        training_solutions = {}
        training_best_solutions = {}

        # Parse WSDL files
        if wsdl_files:
            for file in wsdl_files:
                if file.filename.endswith((".wsdl", ".xml")):
                    try:
                        content = file.read().decode("utf-8")
                        service = app_state["parser"].parse_content(content, file.filename)
                        if service:
                            training_services.append(service)
                    except Exception as e:
                        print(f"Error parsing {file.filename}: {e}")

        if requests_file:
            training_requests = parse_xml_upload(requests_file, parse_requests_xml)
            print(f"Parsed {len(training_requests)} requests")

        if solutions_file:
            training_solutions = parse_xml_upload(solutions_file, parse_best_solutions_xml)
            print(f"Parsed {len(training_solutions)} solutions")

        if best_solutions_file:
            training_best_solutions = parse_xml_upload(best_solutions_file, parse_best_solutions_xml)
            print(f"Parsed {len(training_best_solutions)} best solutions")

        app_state["training_data"]["services"] = training_services
        app_state["training_data"]["requests"] = training_requests
        app_state["training_data"]["solutions"] = training_solutions
        app_state["training_data"]["best_solutions"] = training_best_solutions

        return jsonify({
            "message": "Training data uploaded successfully",
            "training_services": len(training_services),
            "training_requests": len(training_requests),
            "training_solutions": len(training_solutions),
            "training_best_solutions": len(training_best_solutions),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@training_bp.route("/api/training/upload-wsdl-batch", methods=["POST"])
@safe_route
def upload_training_wsdl_batch():
    """Upload training WSDL files in batches."""
    try:
        wsdl_files = request.files.getlist("wsdl_files")
        batch_num = request.form.get("batch_num", 0)

        services = []
        for file in wsdl_files:
            if file.filename.endswith((".wsdl", ".xml")):
                try:
                    content = file.read().decode("utf-8")
                    service = app_state["parser"].parse_content(content, file.filename)
                    if service:
                        services.append(service)
                except Exception as e:
                    print(f"Error parsing {file.filename}: {e}")

        app_state["training_data"]["services"].extend(services)
        total = len(app_state["training_data"]["services"])
        print(f"Batch {batch_num}: {len(services)} training services (total: {total})")

        return jsonify({
            "message": f"Batch {batch_num}: {len(services)} services added",
            "batch_services": len(services),
            "total_training_services": total,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@training_bp.route("/api/training/upload-xml-files", methods=["POST"])
@safe_route
def upload_training_xml_files():
    """Upload XML files (requests, solutions, best solutions) for training."""
    try:
        requests_file = request.files.get("requests_file")
        solutions_file = request.files.get("solutions_file")
        best_solutions_file = request.files.get("best_solutions_file")

        training_requests = []
        training_solutions = {}
        training_best_solutions = {}

        if requests_file:
            training_requests = parse_xml_upload(requests_file, parse_requests_xml)
            print(f"Parsed {len(training_requests)} training requests")

        if solutions_file:
            training_solutions = parse_xml_upload(solutions_file, parse_best_solutions_xml)
            print(f"Parsed {len(training_solutions)} solutions")

        if best_solutions_file:
            training_best_solutions = parse_xml_upload(best_solutions_file, parse_best_solutions_xml)
            print(f"Parsed {len(training_best_solutions)} best solutions")

        app_state["training_data"]["requests"] = training_requests
        app_state["training_data"]["solutions"] = training_solutions
        app_state["training_data"]["best_solutions"] = training_best_solutions

        return jsonify({
            "message": "XML files uploaded successfully",
            "training_requests": len(training_requests),
            "training_solutions": len(training_solutions),
            "training_best_solutions": len(training_best_solutions),
            "total_training_services": len(app_state["training_data"]["services"]),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@training_bp.route("/api/training/reset-wsdl", methods=["POST"])
@safe_route
def reset_training_wsdl():
    """Reset training WSDL data (before a new batch upload)."""
    app_state["training_data"]["services"] = []
    return jsonify({"message": "Training WSDL reset"})


# ============== KNOWLEDGE-BASE TRAINING ==============

@training_bp.route("/api/training/start", methods=["POST"])
@safe_route
def start_training():
    """Train the LLM knowledge base with uploaded training data."""
    try:
        if not app_state["training_data"]["services"]:
            return jsonify({"error": "No training data available"}), 400

        # (Re)create LLM composer with current services
        services = app_state["annotated_services"] or app_state["services"]
        app_state["llm_composer"] = LLMComposer(services)

        # Build training examples from training data
        training_examples = []
        for req in app_state["training_data"]["requests"]:
            example = {
                "request": req.to_dict(),
                "solution": app_state["training_data"]["solutions"].get(req.id),
                "best_solution": app_state["training_data"]["best_solutions"].get(req.id),
            }
            if example["best_solution"]:
                service_id = example["best_solution"].get("service_id")
                service = next(
                    (s for s in app_state["training_data"]["services"] if s.id == service_id),
                    None,
                )
                if service:
                    example["service"] = service.to_dict()
            training_examples.append(example)

        training_quality = app_state["llm_composer"].train(training_examples)

        # Update learning state
        app_state["learning_state"]["is_trained"] = True
        app_state["learning_state"]["training_examples"] = training_examples

        total_examples = len(training_examples)
        examples_with_solutions = sum(
            1 for e in training_examples if e.get("best_solution")
        )
        total_utility = sum(
            (e.get("best_solution") or {}).get("utility", 0)
            for e in training_examples if e.get("best_solution")
        )
        avg_utility = total_utility / max(examples_with_solutions, 1)
        coverage = (
            (examples_with_solutions / total_examples * 100) if total_examples > 0 else 0
        )

        app_state["learning_state"]["performance_metrics"] = {
            "total_compositions": total_examples,
            "successful_compositions": examples_with_solutions,
            "average_utility": avg_utility,
            "learning_rate": coverage,
        }
        app_state["learning_state"]["training_quality"] = training_quality

        # Import into interaction history
        app_state["interaction_store"].import_from_training(training_examples)
        if app_state["annotator"]:
            app_state["annotator"].refresh_history_stats()

        return jsonify({
            "message": "LLM training completed",
            "training_examples_count": total_examples,
            "is_trained": True,
            "training_quality": training_quality,
            "history_records": app_state["interaction_store"].total_records,
            "sft_available": SFT_DEPS_AVAILABLE,
            "sft_hint": (
                "Call POST /api/training/sft to run real Phase 1 LoRA fine-tuning"
                if SFT_DEPS_AVAILABLE else
                f"Install {' '.join(SFT_MISSING)} to enable real SFT training"
            ),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============== PHASE 1: SFT ==============

@training_bp.route("/api/training/sft", methods=["POST"])
@safe_route
def start_sft_training():
    """Phase 1 QSRT: Supervised Fine-Tuning with LoRA adapters (background)."""
    try:
        if not SFT_DEPS_AVAILABLE:
            return jsonify({
                "error": "SFT dependencies not installed",
                "missing": SFT_MISSING,
                "install_cmd": f"pip install {' '.join(SFT_MISSING)}",
            }), 400

        if not app_state["learning_state"]["is_trained"]:
            return jsonify({
                "error": "Knowledge-base training must complete first. "
                         "Call POST /api/training/start before SFT."
            }), 400

        if app_state["sft_state"]["is_training"]:
            return jsonify({"error": "SFT training is already running"}), 409

        data = request.json or {}
        sft_config = {"model_name": data.get("model_name"), "lora_config": {}, "training_config": {}}
        for key, target, cast in [
            ("lora_r", "lora_config", int), ("lora_alpha", "lora_config", int),
            ("epochs", "training_config", int), ("batch_size", "training_config", int),
            ("learning_rate", "training_config", float), ("max_seq_length", "training_config", int),
        ]:
            if key in data:
                mapped = {
                    "epochs": "num_train_epochs",
                    "batch_size": "per_device_train_batch_size",
                    "lora_r": "r",
                }.get(key, key)
                sft_config[target][mapped] = cast(data[key])

        with state_lock:
            app_state["sft_state"] = {
                "is_training": True, "is_trained": False,
                "progress": {"step": 0, "total": 0, "loss": 0, "epoch": 0},
                "metrics": {}, "error": None, "thread": None,
            }

        training_examples = app_state["learning_state"]["training_examples"]

        def _sft_worker():
            try:
                _ensure_llm_composer()

                def _progress(step, total, metrics):
                    with state_lock:
                        app_state["sft_state"]["progress"] = {
                            "step": step, "total": total,
                            "loss": metrics.get("loss", 0),
                            "epoch": metrics.get("epoch", 0),
                        }

                result = app_state["llm_composer"].run_sft(
                    training_examples, sft_config=sft_config,
                    progress_callback=_progress,
                )
                with state_lock:
                    app_state["sft_state"]["is_training"] = False
                    app_state["sft_state"]["is_trained"] = True
                    app_state["sft_state"]["metrics"] = result
                print("[SFT] Phase 1 training complete")
            except Exception as exc:
                import traceback; traceback.print_exc()
                with state_lock:
                    app_state["sft_state"]["is_training"] = False
                    app_state["sft_state"]["error"] = str(exc)

        t = threading.Thread(target=_sft_worker, daemon=True)
        app_state["sft_state"]["thread"] = t
        t.start()

        return jsonify({
            "message": "SFT Phase 1 training started in background",
            "poll_url": "/api/training/sft/status",
        }), 202
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@training_bp.route("/api/training/sft/status", methods=["GET"])
@safe_route
def get_sft_status():
    """Poll SFT Phase 1 progress."""
    with state_lock:
        s = app_state["sft_state"]
        return jsonify({
            "is_training": s["is_training"], "is_trained": s["is_trained"],
            "progress": s["progress"], "metrics": s["metrics"],
            "error": s["error"], "sft_available": SFT_DEPS_AVAILABLE,
        })


# ============== PHASE 2: REWARD MODEL ==============

@training_bp.route("/api/training/reward", methods=["POST"])
@safe_route
def start_reward_training():
    """Phase 2 QSRT: Train the reward model (background)."""
    try:
        if not REWARD_DEPS_AVAILABLE:
            return jsonify({
                "error": "Reward model dependencies not installed",
                "missing": REWARD_MISSING,
                "install_cmd": f"pip install {' '.join(REWARD_MISSING)}",
            }), 400

        if not app_state["learning_state"]["is_trained"]:
            return jsonify({"error": "Knowledge-base training must complete first."}), 400

        if app_state["reward_state"]["is_training"]:
            return jsonify({"error": "Reward model training is already running"}), 409

        data = request.json or {}
        reward_config = {
            "model_name": data.get("model_name"),
            "lora_r": int(data.get("lora_r", 8)),
            "lora_alpha": int(data.get("lora_alpha", 16)),
            "num_epochs": int(data.get("epochs", 5)),
            "batch_size": int(data.get("batch_size", 4)),
            "learning_rate": float(data.get("learning_rate", 1e-4)),
            "n_pairs": int(data.get("n_pairs", 200)),
            "alpha": float(data.get("alpha", 0.50)),
            "beta": float(data.get("beta", 0.35)),
            "gamma": float(data.get("gamma", 0.15)),
        }

        with state_lock:
            app_state["reward_state"] = {
                "is_training": True, "is_trained": False,
                "progress": {"step": 0, "total": 0, "loss": 0, "epoch": 0},
                "metrics": {}, "error": None, "thread": None,
            }

        training_examples = app_state["learning_state"]["training_examples"]

        def _reward_worker():
            try:
                _ensure_llm_composer()

                def _progress(step, total, metrics):
                    with state_lock:
                        app_state["reward_state"]["progress"] = {
                            "step": step, "total": total,
                            "loss": metrics.get("loss", 0),
                            "epoch": metrics.get("epoch", 0),
                        }

                result = app_state["llm_composer"].run_reward_training(
                    training_examples, reward_config=reward_config,
                    progress_callback=_progress,
                )
                with state_lock:
                    app_state["reward_state"]["is_training"] = False
                    app_state["reward_state"]["is_trained"] = True
                    app_state["reward_state"]["metrics"] = result
                print("[REWARD] Phase 2 training complete")
            except Exception as exc:
                import traceback; traceback.print_exc()
                with state_lock:
                    app_state["reward_state"]["is_training"] = False
                    app_state["reward_state"]["error"] = str(exc)

        t = threading.Thread(target=_reward_worker, daemon=True)
        app_state["reward_state"]["thread"] = t
        t.start()

        return jsonify({
            "message": "Reward Model Phase 2 training started in background",
            "poll_url": "/api/training/reward/status",
        }), 202
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@training_bp.route("/api/training/reward/status", methods=["GET"])
@safe_route
def get_reward_status():
    """Poll Reward Model Phase 2 progress."""
    with state_lock:
        s = app_state["reward_state"]
        return jsonify({
            "is_training": s["is_training"], "is_trained": s["is_trained"],
            "progress": s["progress"], "metrics": s["metrics"],
            "error": s["error"], "reward_available": REWARD_DEPS_AVAILABLE,
        })


@training_bp.route("/api/reward/compute", methods=["POST"])
@safe_route
@require_json
def compute_reward():
    """Compute analytical reward score for a composition."""
    try:
        data = request.json
        workflow = data.get("workflow", [])
        resultant = data.get("resultant", "")

        if not workflow:
            return jsonify({"error": "workflow list is required"}), 400
        if not app_state["llm_composer"]:
            return jsonify({"error": "LLM composer not initialized"}), 400

        composer = app_state["llm_composer"]
        services = [
            composer.service_dict[sid] for sid in workflow
            if sid in composer.service_dict
        ]
        if not services:
            return jsonify({"error": "No valid service IDs in workflow"}), 400

        from models.service import CompositionRequest as CR, QoS as QoSModel
        cr = CR("reward_compute")
        cr.resultant = resultant
        cr.provided = data.get("provided", [])
        cr.qos_constraints = QoSModel(data.get("qos_constraints", {}))

        reward_info = composer.compute_reward(services, cr, workflow)

        neural_reward = None
        if composer._reward_model_trained and composer.reward_model_trainer:
            try:
                neural_reward = composer.predict_reward(
                    workflow,
                    {"resultant": resultant, "provided": cr.provided,
                     "qos_constraints": data.get("qos_constraints", {})},
                )
            except Exception:
                pass

        return jsonify({
            "analytical_reward": reward_info,
            "neural_reward": neural_reward,
            "reward_model_trained": composer._reward_model_trained,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============== PHASE 3: RL ==============

@training_bp.route("/api/training/rl", methods=["POST"])
@safe_route
def start_rl_training():
    """Phase 3 QSRT: Reinforcement Learning fine-tuning (GRPO or PPO)."""
    try:
        if not RL_DEPS_AVAILABLE:
            return jsonify({
                "error": "RL dependencies not installed",
                "missing": RL_MISSING,
                "install_cmd": f"pip install {' '.join(RL_MISSING)}",
            }), 400

        if not app_state["learning_state"]["is_trained"]:
            return jsonify({"error": "Knowledge-base training must complete first."}), 400

        if app_state["rl_state"]["is_training"]:
            return jsonify({"error": "RL training is already running"}), 409

        data = request.json or {}
        algorithm = data.get("algorithm", "GRPO").upper()
        err = validate_rl_algorithm(algorithm)
        if err:
            return err

        rl_config = {}
        for key in ("group_size", "num_episodes", "batch_size",
                     "max_seq_length", "max_new_tokens"):
            if key in data:
                rl_config[key] = int(data[key])
        for key in ("clip_epsilon", "kl_coeff", "entropy_coeff",
                     "learning_rate", "temperature", "top_p",
                     "weight_decay", "max_grad_norm"):
            if key in data:
                rl_config[key] = float(data[key])
        if "lora_r" in data:
            rl_config["lora_r"] = int(data["lora_r"])
        if "lora_alpha" in data:
            rl_config["lora_alpha"] = int(data["lora_alpha"])
        if "model_name" in data:
            rl_config["model_name"] = data["model_name"]

        with state_lock:
            app_state["rl_state"] = {
                "is_training": True, "is_trained": False, "algorithm": algorithm,
                "progress": {"step": 0, "total": 0, "loss": 0, "episode": 0, "mean_reward": 0},
                "metrics": {}, "error": None, "thread": None,
            }

        training_examples = app_state["learning_state"]["training_examples"]

        def _rl_progress(step, total, metrics):
            with state_lock:
                app_state["rl_state"]["progress"] = {
                    "step": step, "total": total,
                    "loss": metrics.get("loss", 0),
                    "episode": metrics.get("episode", 0),
                    "mean_reward": metrics.get("mean_reward", 0),
                }

        def _rl_worker():
            try:
                _ensure_llm_composer()
                result = app_state["llm_composer"].run_rl_training(
                    training_examples,
                    rl_config=rl_config,
                    algorithm=algorithm,
                    progress_callback=_rl_progress,
                )
                with state_lock:
                    app_state["rl_state"]["is_training"] = False
                    app_state["rl_state"]["is_trained"] = True
                    app_state["rl_state"]["metrics"] = result
                print(f"[RL] Phase 3 training complete ({algorithm})")
            except Exception as exc:
                import traceback; traceback.print_exc()
                with state_lock:
                    app_state["rl_state"]["is_training"] = False
                    app_state["rl_state"]["error"] = str(exc)

        t = threading.Thread(target=_rl_worker, daemon=True)
        app_state["rl_state"]["thread"] = t
        t.start()

        return jsonify({
            "message": f"RL Phase 3 training started ({algorithm})",
            "algorithm": algorithm,
            "poll_url": "/api/training/rl/status",
        }), 202
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@training_bp.route("/api/training/rl/status", methods=["GET"])
@safe_route
def get_rl_status():
    """Poll RL Phase 3 progress."""
    with state_lock:
        s = app_state["rl_state"]
        return jsonify({
            "is_training": s["is_training"], "is_trained": s["is_trained"],
            "algorithm": s["algorithm"], "progress": s["progress"],
            "metrics": s["metrics"], "error": s["error"],
            "rl_available": RL_DEPS_AVAILABLE,
        })


# ============== COMBINED STATUS ==============

@training_bp.route("/api/training/status", methods=["GET"])
@safe_route
def get_training_status():
    """Get combined training status across all phases."""
    return jsonify({
        "is_trained": app_state["learning_state"]["is_trained"],
        "training_examples": len(app_state["learning_state"]["training_examples"]),
        "composition_history": len(app_state["learning_state"]["composition_history"]),
        "success_patterns": len(app_state["learning_state"]["success_patterns"]),
        "performance_metrics": app_state["learning_state"]["performance_metrics"],
        "training_quality": app_state["learning_state"].get("training_quality", {}),
        "sft_available": SFT_DEPS_AVAILABLE,
        "sft_missing_packages": SFT_MISSING if not SFT_DEPS_AVAILABLE else [],
        "sft_state": {
            "is_training": app_state["sft_state"]["is_training"],
            "is_trained": app_state["sft_state"]["is_trained"],
            "progress": app_state["sft_state"]["progress"],
            "metrics": app_state["sft_state"]["metrics"],
            "error": app_state["sft_state"]["error"],
        },
        "reward_available": REWARD_DEPS_AVAILABLE,
        "reward_missing_packages": REWARD_MISSING if not REWARD_DEPS_AVAILABLE else [],
        "reward_state": {
            "is_training": app_state["reward_state"]["is_training"],
            "is_trained": app_state["reward_state"]["is_trained"],
            "progress": app_state["reward_state"]["progress"],
            "metrics": app_state["reward_state"]["metrics"],
            "error": app_state["reward_state"]["error"],
        },
        "rl_available": RL_DEPS_AVAILABLE,
        "rl_missing_packages": RL_MISSING if not RL_DEPS_AVAILABLE else [],
        "rl_state": {
            "is_training": app_state["rl_state"]["is_training"],
            "is_trained": app_state["rl_state"]["is_trained"],
            "algorithm": app_state["rl_state"]["algorithm"],
            "progress": app_state["rl_state"]["progress"],
            "metrics": app_state["rl_state"]["metrics"],
            "error": app_state["rl_state"]["error"],
        },
    })
