"""
Shared application state and dependency availability flags.

All mutable state lives here so that it can be imported by any
Blueprint / route module without circular dependencies.
"""

import threading

from services.wsdl_parser import WSDLParser
from models.interaction_history import InteractionHistoryStore

# ── Dependency availability checks (graceful degradation) ──────────

# Phase 1: SFT
try:
    from services.sft_trainer import SFTLoRATrainer
    SFT_DEPS_AVAILABLE = SFTLoRATrainer.is_available()
    SFT_MISSING = SFTLoRATrainer.missing_packages()
except Exception:
    SFT_DEPS_AVAILABLE = False
    SFT_MISSING = ["torch", "transformers", "peft", "datasets"]

# Phase 2: Reward Model
try:
    from services.reward_model import RewardModelTrainer
    from services.reward_calculator import RewardCalculator, RewardDatasetBuilder
    REWARD_DEPS_AVAILABLE = RewardModelTrainer.is_available()
    REWARD_MISSING = RewardModelTrainer.missing_packages()
except Exception:
    REWARD_DEPS_AVAILABLE = False
    REWARD_MISSING = ["torch", "transformers", "peft"]

# Phase 3: RL
try:
    from services.rl_trainer import GRPOTrainer, PPOTrainer
    RL_DEPS_AVAILABLE = GRPOTrainer.is_available()
    RL_MISSING = GRPOTrainer.missing_packages()
except Exception:
    RL_DEPS_AVAILABLE = False
    RL_MISSING = ["torch", "transformers", "peft"]

# ── Thread-safety lock for shared mutable state ───────────────────

state_lock = threading.Lock()

# ── Global interaction history store (persistent, shared) ─────────

interaction_store = InteractionHistoryStore()

# ── Global application state ──────────────────────────────────────

app_state = {
    "services": [],
    "annotated_services": [],
    "requests": [],
    "best_solutions": {},
    "results_classic": {},
    "results_llm": {},
    "parser": WSDLParser(),
    "annotator": None,
    "classic_composer": None,
    "llm_composer": None,
    "interaction_store": interaction_store,
    "annotation_thread": None,
    "annotation_progress": {
        "current": 0,
        "total": 0,
        "current_service": "",
        "completed": False,
        "error": None,
    },
    "annotation_status": {
        "services_annotated": False,
        "annotation_count": 0,
        "total_services": 0,
    },
    "training_data": {
        "services": [],
        "requests": [],
        "solutions": {},
        "best_solutions": {},
    },
    "learning_state": {
        "is_trained": False,
        "training_examples": [],
        "composition_history": [],
        "success_patterns": [],
        "error_patterns": [],
        "performance_metrics": {
            "total_compositions": 0,
            "successful_compositions": 0,
            "average_utility": 0,
            "learning_rate": 0,
        },
    },
    "sft_state": {
        "is_training": False,
        "is_trained": False,
        "progress": {"step": 0, "total": 0, "loss": 0, "epoch": 0},
        "metrics": {},
        "error": None,
        "thread": None,
    },
    "reward_state": {
        "is_training": False,
        "is_trained": False,
        "progress": {"step": 0, "total": 0, "loss": 0, "epoch": 0},
        "metrics": {},
        "error": None,
        "thread": None,
    },
    "rl_state": {
        "is_training": False,
        "is_trained": False,
        "algorithm": None,
        "progress": {
            "step": 0,
            "total": 0,
            "loss": 0,
            "episode": 0,
            "mean_reward": 0,
        },
        "metrics": {},
        "error": None,
        "thread": None,
    },
}


def compute_annotation_status():
    """Single source of truth for annotation status."""
    annotated = sum(
        1
        for s in app_state["services"]
        if hasattr(s, "annotations") and s.annotations is not None
    )
    total = len(app_state["services"])
    return {
        "services_annotated": annotated > 0,
        "annotation_count": annotated,
        "total_services": total,
        "percentage": (annotated / total * 100) if total > 0 else 0,
    }
