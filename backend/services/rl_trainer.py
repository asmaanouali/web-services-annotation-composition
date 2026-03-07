"""
Reinforcement Learning Fine-Tuning for Web Service Composition.

Implements two RL algorithms for policy optimisation on top of the
SFT-initialised model (Phase 1) using the trained reward model (Phase 2):

    ┌─────────────────────────────────────────────────────────────────┐
    │  GRPO  (Group Relative Policy Optimisation)                    │
    │  ─ Generates *G* candidate compositions per prompt             │
    │  ─ Scores each with the neural reward model                    │
    │  ─ Uses group-normalised advantages (no critic needed)         │
    │  ─ Applies clipped surrogate loss (PPO-style) with KL penalty  │
    │                                                                │
    │  PPO   (Proximal Policy Optimisation)                          │
    │  ─ Classic actor-critic: generates one response per prompt     │
    │  ─ Uses GAE for advantage estimation                           │
    │  ─ Clip ratio ε = 0.2, KL coefficient β = 0.04                │
    └─────────────────────────────────────────────────────────────────┘

Why GRPO is preferred for service composition:
    • Multiple candidate compositions are naturally available (we
      already generate top-K candidates during composition).
    • No value network required → lower memory & no critic drift.
    • Group-normalised advantages are more stable for small batches
      typical in composition tasks.

Part of: QSRT — QoS-Driven Reinforcement Fine-Tuning with Social Trust Rewards
Phase 3: Reinforcement Learning Fine-Tuning

Copyright (c) 2026. All rights reserved.
"""

from __future__ import annotations

import os
import json
import time
import math
import copy
import random
from typing import Dict, Any, Optional, List, Callable, Tuple

# ---------------------------------------------------------------------------
# Lazy imports (graceful degradation when ML deps are absent)
# ---------------------------------------------------------------------------
_TORCH_AVAILABLE = False
_HF_AVAILABLE = False
_PEFT_AVAILABLE = False
_DATASETS_AVAILABLE = False

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    _TORCH_AVAILABLE = True
except ImportError:
    pass

try:
    from transformers import (
        AutoTokenizer,
        AutoModelForCausalLM,
    )
    _HF_AVAILABLE = True
except ImportError:
    pass

try:
    from peft import LoraConfig, get_peft_model, PeftModel, TaskType
    _PEFT_AVAILABLE = True
except ImportError:
    pass

try:
    from datasets import Dataset
    _DATASETS_AVAILABLE = True
except ImportError:
    pass


def _deps_available() -> bool:
    return _TORCH_AVAILABLE and _HF_AVAILABLE and _PEFT_AVAILABLE


def _missing_packages() -> List[str]:
    m: List[str] = []
    if not _TORCH_AVAILABLE:
        m.append("torch")
    if not _HF_AVAILABLE:
        m.append("transformers")
    if not _PEFT_AVAILABLE:
        m.append("peft")
    return m


# ═══════════════════════════════════════════════════════════════════════
#  Prompt builder  (shared by both PPO & GRPO)
# ═══════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = (
    "You are a web service composition engine.  Given a composition "
    "request (required input/output, QoS constraints) and a set of "
    "candidate services with their QoS metrics and social trust "
    "annotations, select the optimal service(s) to fulfil the request.  "
    "Respond with a JSON object: {\"selected\": [<service_ids>], "
    "\"reasoning\": \"<brief explanation>\"}."
)


def build_rl_prompt(
    request_data: Dict,
    candidate_services: Dict[str, Any],
    *,
    max_candidates: int = 15,
) -> str:
    """Build a prompt for the RL policy model.

    This is the *input* the policy sees; the *output* it generates is
    scored by the reward model.
    """
    lines = [
        f"<|system|>\n{SYSTEM_PROMPT}",
        "<|user|>",
        f"Request: produce '{request_data.get('resultant', '?')}'",
        f"Provided: {', '.join(request_data.get('provided', [])[:10]) or 'none'}",
    ]

    # QoS constraints
    qos = request_data.get("qos_constraints", {})
    if qos:
        parts = [f"{k}={v}" for k, v in qos.items() if v]
        if parts:
            lines.append(f"Constraints: {', '.join(parts)}")

    # Candidate services (truncated)
    svc_items = list(candidate_services.items())[:max_candidates]
    lines.append(f"\nCandidates ({len(svc_items)}):")
    for sid, svc in svc_items:
        qos_str = ""
        trust_str = ""
        if hasattr(svc, "qos") and svc.qos:
            qos_str = (
                f"rel={svc.qos.reliability:.1f}% "
                f"rt={svc.qos.response_time:.0f}ms "
                f"avl={svc.qos.availability:.1f}%"
            )
        if hasattr(svc, "annotations") and svc.annotations:
            sn = svc.annotations.social_node
            trust_str = (
                f" trust={sn.trust_degree.value:.2f}"
                f" rep={sn.reputation.value:.2f}"
                f" coop={sn.cooperativeness.value:.2f}"
            )
        lines.append(f"  {sid}: {qos_str}{trust_str}")

    lines.append("<|assistant|>")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
#  Experience buffer  (stores (prompt, response, reward) tuples)
# ═══════════════════════════════════════════════════════════════════════

class RLExperienceBuffer:
    """Collects RL rollout data for a training step."""

    def __init__(self):
        self.prompts: List[str] = []
        self.responses: List[str] = []
        self.rewards: List[float] = []
        self.log_probs: List[Any] = []       # per-token log-probs
        self.ref_log_probs: List[Any] = []   # reference model log-probs (KL)
        self.advantages: List[float] = []

    def add(self, prompt: str, response: str, reward: float,
            log_prob=None, ref_log_prob=None):
        self.prompts.append(prompt)
        self.responses.append(response)
        self.rewards.append(reward)
        if log_prob is not None:
            self.log_probs.append(log_prob)
        if ref_log_prob is not None:
            self.ref_log_probs.append(ref_log_prob)

    def __len__(self):
        return len(self.prompts)

    def clear(self):
        self.prompts.clear()
        self.responses.clear()
        self.rewards.clear()
        self.log_probs.clear()
        self.ref_log_probs.clear()
        self.advantages.clear()


# ═══════════════════════════════════════════════════════════════════════
#  GRPO  Trainer  (preferred algorithm)
# ═══════════════════════════════════════════════════════════════════════

class GRPOTrainer:
    """
    Group Relative Policy Optimisation for service composition.

    For each composition prompt the policy generates *G* candidate
    responses.  Each is scored by the reward model.  Advantages are
    computed group-relative (mean/std within the group) eliminating
    the need for a learned value function.

    Loss:
        L = -E[ min( r_θ · A_g , clip(r_θ, 1-ε, 1+ε) · A_g ) ]
            + β · KL( π_θ ‖ π_ref )

    where  r_θ = π_θ(a|s) / π_old(a|s)   (importance ratio)
           A_g = (R_i - μ_G) / σ_G          (group advantage)
    """

    DEFAULT_CONFIG = {
        # Model
        "model_name": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        # LoRA (starts from Phase 1 SFT adapter if available)
        "lora_r": 16,
        "lora_alpha": 32,
        "lora_dropout": 0.05,
        # GRPO-specific
        "group_size": 4,          # G — candidates per prompt
        "clip_epsilon": 0.2,      # ε — PPO clip ratio
        "kl_coeff": 0.04,         # β — KL penalty coefficient
        "entropy_coeff": 0.01,    # η — entropy bonus (exploration)
        # Optimiser
        "learning_rate": 5e-6,    # smaller LR than SFT — policy is delicate
        "weight_decay": 0.01,
        "max_grad_norm": 1.0,
        # Schedule
        "num_episodes": 3,        # outer episodes (each uses all prompts)
        "batch_size": 2,          # prompts per optimisation step
        "max_seq_length": 512,
        "max_new_tokens": 128,
        # Generation
        "temperature": 0.7,       # sampling temperature (diversity)
        "top_p": 0.9,
    }

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        output_dir: Optional[str] = None,
        sft_adapter_path: Optional[str] = None,
    ):
        if not _deps_available():
            raise ImportError(
                f"RL training requires: {', '.join(_missing_packages())}. "
                f"Install with: pip install {' '.join(_missing_packages())}"
            )

        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self.output_dir = output_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "models", "rl_adapter",
        )
        self.sft_adapter_path = sft_adapter_path

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None          # policy π_θ  (LoRA on base)
        self.ref_model = None      # frozen reference π_ref  (for KL)
        self.tokenizer = None
        self.is_trained = False
        self.training_metrics: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Static availability helpers
    # ------------------------------------------------------------------
    @staticmethod
    def is_available() -> bool:
        return _deps_available()

    @staticmethod
    def missing_packages() -> List[str]:
        return _missing_packages()

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load_model(self):
        """Load the policy model (from SFT adapter if available)."""
        cfg = self.config
        dtype = torch.float16 if self.device == "cuda" else torch.float32

        print("[RL 1/4] Loading tokenizer …")
        # Try SFT adapter tokenizer first
        tok_path = self.sft_adapter_path or cfg["model_name"]
        self.tokenizer = AutoTokenizer.from_pretrained(
            tok_path, trust_remote_code=True,
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

        print("[RL 2/4] Loading base model …")
        base_model = AutoModelForCausalLM.from_pretrained(
            cfg["model_name"],
            torch_dtype=dtype,
            trust_remote_code=True,
        )
        base_model = base_model.to(self.device)

        # Load the SFT adapter if available (warm start)
        if self.sft_adapter_path and os.path.exists(self.sft_adapter_path):
            print(f"[RL] Loading SFT adapter from {self.sft_adapter_path} …")
            self.model = PeftModel.from_pretrained(
                base_model, self.sft_adapter_path
            )
            # Merge the SFT adapter and re-apply fresh LoRA for RL
            self.model = self.model.merge_and_unload()
            print("[RL] SFT adapter merged into base weights ✓")
        else:
            self.model = base_model
            print("[RL] No SFT adapter found — training from base model")

        # Create a frozen copy for KL reference BEFORE adding RL LoRA
        print("[RL 3/4] Creating reference model (frozen) …")
        self.ref_model = copy.deepcopy(self.model)
        self.ref_model.eval()
        for p in self.ref_model.parameters():
            p.requires_grad = False

        # Apply fresh LoRA adapters for the RL phase
        print("[RL 4/4] Attaching RL LoRA adapters …")
        lora_cfg = LoraConfig(
            r=cfg["lora_r"],
            lora_alpha=cfg["lora_alpha"],
            lora_dropout=cfg["lora_dropout"],
            target_modules=[
                "q_proj", "k_proj", "v_proj", "o_proj",
                "gate_proj", "up_proj", "down_proj",
            ],
            bias="none",
            task_type=TaskType.CAUSAL_LM,
        )
        self.model = get_peft_model(self.model, lora_cfg)

        trainable, total = self.model.get_nb_trainable_parameters()
        print(f"  RL LoRA params: {trainable:,} / {total:,} "
              f"({100 * trainable / total:.2f}%)")

        return trainable, total

    # ------------------------------------------------------------------
    # Log-probability computation
    # ------------------------------------------------------------------

    def _compute_log_probs(self, model, input_ids, attention_mask,
                           response_start_idx: int):
        """Compute per-token log-probabilities for the response portion."""
        with torch.no_grad():
            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
            )
        # logits shape: (1, seq_len, vocab_size)
        logits = outputs.logits[:, :-1, :]   # shift left
        targets = input_ids[:, 1:]            # shift right

        log_probs = F.log_softmax(logits, dim=-1)
        # Gather the log-prob of the actually generated token
        token_log_probs = log_probs.gather(
            2, targets.unsqueeze(-1)
        ).squeeze(-1)

        # Only keep the response tokens (after the prompt)
        resp_log_probs = token_log_probs[:, max(response_start_idx - 1, 0):]
        return resp_log_probs.sum(dim=-1)   # sum over response tokens

    # ------------------------------------------------------------------
    # Generation (sample G responses per prompt)
    # ------------------------------------------------------------------

    def _generate_responses(self, prompt: str, num_responses: int):
        """
        Sample *num_responses* different completions for a single prompt.

        Returns:
            list of (response_text, prompt_len) tuples
        """
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=self.config["max_seq_length"],
        ).to(self.device)

        prompt_len = inputs["input_ids"].shape[1]
        results = []

        self.model.eval()
        with torch.no_grad():
            for _ in range(num_responses):
                out = self.model.generate(
                    **inputs,
                    max_new_tokens=self.config["max_new_tokens"],
                    temperature=self.config["temperature"],
                    top_p=self.config["top_p"],
                    do_sample=True,
                    pad_token_id=self.tokenizer.pad_token_id,
                )
                gen_ids = out[0][prompt_len:]
                text = self.tokenizer.decode(
                    gen_ids, skip_special_tokens=True,
                )
                if "<|end|>" in text:
                    text = text[:text.index("<|end|>")]
                results.append((text.strip(), prompt_len))

        return results

    # ------------------------------------------------------------------
    # Reward scoring (delegates to reward model / calculator)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_service_ids(response_text: str) -> List[str]:
        """Extract service IDs from a model-generated JSON response."""
        try:
            data = json.loads(response_text)
            ids = data.get("selected", [])
            if isinstance(ids, list):
                return [str(s) for s in ids]
        except (json.JSONDecodeError, AttributeError):
            pass
        # Fallback: look for service ID patterns (e.g., p1a123456789)
        import re
        ids = re.findall(r'p\d+a\d+', response_text)
        if ids:
            return ids
        # Also try generic patterns
        return re.findall(r'serv[\w-]+', response_text)

    @staticmethod
    def _score_response(
        response_text: str,
        request_data: Dict,
        reward_fn: Callable,
    ) -> float:
        """Score a generated response using the reward function.

        Args:
            response_text: model-generated text (expected JSON)
            request_data: original composition request dict
            reward_fn: callable(service_ids, request_data) -> float

        Returns:
            Scalar reward.
        """
        service_ids = GRPOTrainer._parse_service_ids(response_text)
        if not service_ids:
            return -0.5   # penalty for unparseable output

        try:
            return float(reward_fn(service_ids, request_data))
        except Exception:
            return -0.5

    # ------------------------------------------------------------------
    # GRPO advantage computation
    # ------------------------------------------------------------------

    @staticmethod
    def _group_advantages(rewards: List[float]) -> List[float]:
        """Compute group-normalised advantages.

            A_i = (R_i - μ) / (σ + ε)

        This eliminates the need for a learned value function / critic.
        """
        if len(rewards) < 2:
            return [0.0] * len(rewards)
        mu = sum(rewards) / len(rewards)
        var = sum((r - mu) ** 2 for r in rewards) / len(rewards)
        sigma = math.sqrt(var) + 1e-8
        return [(r - mu) / sigma for r in rewards]

    # ------------------------------------------------------------------
    # Core training loop
    # ------------------------------------------------------------------

    def train(
        self,
        prompts: List[Dict[str, Any]],
        reward_fn: Callable,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Run GRPO reinforcement learning fine-tuning.

        Args:
            prompts: list of dicts with keys:
                - request_data: composition request dict
                - candidate_services: {sid: WebService} for the prompt
            reward_fn: callable(service_ids, request_data) -> float
                       (typically LLMComposer.predict_reward)
            progress_callback: optional callable(step, total, metrics)

        Returns:
            dict with RL training metrics
        """
        start = time.time()
        cfg = self.config
        G = cfg["group_size"]
        eps = cfg["clip_epsilon"]
        beta = cfg["kl_coeff"]
        eta = cfg["entropy_coeff"]

        print(f"\n{'=' * 60}")
        print("PHASE 3 — RL Fine-Tuning (GRPO)")
        print(f"{'=' * 60}")
        print(f"  Model          : {cfg['model_name']}")
        print(f"  Device         : {self.device}")
        print(f"  Prompts        : {len(prompts)}")
        print(f"  Group size (G) : {G}")
        print(f"  Episodes       : {cfg['num_episodes']}")
        print(f"  Clip ε         : {eps}")
        print(f"  KL coeff β     : {beta}")
        print(f"  Entropy η      : {eta}")
        print(f"  LR             : {cfg['learning_rate']}")
        print(f"  SFT adapter    : {self.sft_adapter_path or 'none'}")
        print(f"  Output dir     : {self.output_dir}")
        print(f"{'=' * 60}\n")

        # 1. Load model
        trainable, total_params = self._load_model()

        # 2. Optimiser  (only RL LoRA params)
        optimizer = torch.optim.AdamW(
            [p for p in self.model.parameters() if p.requires_grad],
            lr=cfg["learning_rate"],
            weight_decay=cfg["weight_decay"],
        )

        # 3. Training loop
        n_prompts = len(prompts)
        bs = cfg["batch_size"]
        total_steps = cfg["num_episodes"] * ((n_prompts + bs - 1) // bs)
        step = 0
        episode_stats: List[Dict[str, float]] = []
        all_rewards: List[float] = []

        for episode in range(cfg["num_episodes"]):
            random.shuffle(prompts)
            ep_rewards: List[float] = []
            ep_losses: List[float] = []
            ep_kl: List[float] = []

            for batch_start in range(0, n_prompts, bs):
                batch = prompts[batch_start: batch_start + bs]
                batch_loss = torch.tensor(0.0, device=self.device)
                batch_count = 0

                for item in batch:
                    request_data = item["request_data"]
                    candidate_services = item["candidate_services"]

                    # Build the RL prompt
                    prompt_text = build_rl_prompt(
                        request_data, candidate_services,
                    )

                    # ── Generate G candidate responses ──
                    responses = self._generate_responses(prompt_text, G)
                    if not responses:
                        continue

                    # ── Score each with the reward model ──
                    group_rewards = []
                    group_texts = []
                    for resp_text, _ in responses:
                        r = self._score_response(
                            resp_text, request_data, reward_fn,
                        )
                        group_rewards.append(r)
                        group_texts.append(resp_text)

                    # ── Compute group-normalised advantages ──
                    advantages = self._group_advantages(group_rewards)

                    # ── Policy optimisation step ──
                    self.model.train()
                    for idx, (resp_text, prompt_len) in enumerate(responses):
                        adv = advantages[idx]
                        if abs(adv) < 1e-8:
                            continue   # skip zero-advantage samples

                        full_text = prompt_text + resp_text
                        enc = self.tokenizer(
                            full_text,
                            return_tensors="pt",
                            truncation=True,
                            max_length=cfg["max_seq_length"],
                        ).to(self.device)

                        input_ids = enc["input_ids"]
                        attn_mask = enc["attention_mask"]

                        # Log-probs under current policy
                        outputs = self.model(
                            input_ids=input_ids,
                            attention_mask=attn_mask,
                        )
                        logits = outputs.logits[:, :-1, :]
                        targets = input_ids[:, 1:]

                        log_probs_all = F.log_softmax(logits, dim=-1)
                        token_lp = log_probs_all.gather(
                            2, targets.unsqueeze(-1)
                        ).squeeze(-1)

                        # Response-only mask
                        resp_mask = torch.zeros_like(
                            token_lp, dtype=torch.bool
                        )
                        resp_start = max(prompt_len - 1, 0)
                        resp_mask[:, resp_start:] = True
                        resp_token_lp = token_lp * resp_mask.float()

                        # Log-probs under reference model (KL)
                        with torch.no_grad():
                            ref_out = self.ref_model(
                                input_ids=input_ids,
                                attention_mask=attn_mask,
                            )
                        ref_logits = ref_out.logits[:, :-1, :]
                        ref_lp_all = F.log_softmax(ref_logits, dim=-1)
                        ref_token_lp = ref_lp_all.gather(
                            2, targets.unsqueeze(-1)
                        ).squeeze(-1)
                        ref_resp_lp = ref_token_lp * resp_mask.float()

                        # Importance ratio  r_θ = exp(lp - old_lp)
                        # For GRPO we use current vs. ref (not old policy)
                        ratio = torch.exp(
                            resp_token_lp.sum() - ref_resp_lp.sum()
                        )
                        adv_tensor = torch.tensor(
                            adv, device=self.device, dtype=ratio.dtype,
                        )

                        # Clipped surrogate objective
                        surr1 = ratio * adv_tensor
                        surr2 = torch.clamp(
                            ratio, 1.0 - eps, 1.0 + eps,
                        ) * adv_tensor
                        policy_loss = -torch.min(surr1, surr2)

                        # KL penalty  (KL(π_θ ‖ π_ref) ≈ policy_lp - ref_lp)
                        kl = (resp_token_lp.sum() - ref_resp_lp.sum()).detach()
                        kl_penalty = beta * kl

                        # Entropy bonus (encourages exploration)
                        probs = F.softmax(logits, dim=-1)
                        entropy = -(probs * log_probs_all).sum(-1)
                        entropy_resp = (entropy * resp_mask[:, :entropy.shape[1]].float()).mean()
                        entropy_bonus = -eta * entropy_resp

                        sample_loss = policy_loss + kl_penalty + entropy_bonus
                        batch_loss = batch_loss + sample_loss
                        batch_count += 1

                        ep_kl.append(max(float(kl.item()), 0.0))

                    ep_rewards.extend(group_rewards)
                    all_rewards.extend(group_rewards)

                # Optimise
                if batch_count > 0:
                    loss = batch_loss / batch_count
                    optimizer.zero_grad()
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(
                        [p for p in self.model.parameters() if p.requires_grad],
                        cfg["max_grad_norm"],
                    )
                    optimizer.step()
                    ep_losses.append(float(loss.item()))

                step += 1

                # Progress callback
                if progress_callback and step % max(total_steps // 20, 1) == 0:
                    progress_callback(
                        step=step,
                        total=total_steps,
                        metrics={
                            "loss": ep_losses[-1] if ep_losses else 0,
                            "mean_reward": (
                                sum(ep_rewards) / max(len(ep_rewards), 1)
                            ),
                            "episode": episode + 1,
                        },
                    )

            # Episode summary
            mean_r = sum(ep_rewards) / max(len(ep_rewards), 1)
            mean_l = sum(ep_losses) / max(len(ep_losses), 1)
            mean_kl = sum(ep_kl) / max(len(ep_kl), 1)
            episode_stats.append({
                "episode": episode + 1,
                "mean_reward": round(mean_r, 4),
                "mean_loss": round(mean_l, 6),
                "mean_kl": round(mean_kl, 6),
                "num_samples": len(ep_rewards),
            })
            print(
                f"  Episode {episode + 1}/{cfg['num_episodes']}  "
                f"reward={mean_r:.4f}  loss={mean_l:.6f}  kl={mean_kl:.4f}"
            )

        # ── Save RL adapter ──
        os.makedirs(self.output_dir, exist_ok=True)
        adapter_path = os.path.join(self.output_dir, "final_adapter")
        os.makedirs(adapter_path, exist_ok=True)
        self.model.save_pretrained(adapter_path)
        self.tokenizer.save_pretrained(adapter_path)

        with open(os.path.join(adapter_path, "rl_config.json"), "w") as f:
            json.dump({
                "algorithm": "GRPO",
                "config": self.config,
                "sft_adapter": self.sft_adapter_path,
                "trainable_params": trainable,
                "total_params": total_params,
                "total_prompts": n_prompts,
            }, f, indent=2)

        elapsed = time.time() - start
        overall_mean_reward = (
            sum(all_rewards) / max(len(all_rewards), 1)
        )
        reward_improvement = 0.0
        if len(episode_stats) >= 2:
            reward_improvement = (
                episode_stats[-1]["mean_reward"]
                - episode_stats[0]["mean_reward"]
            )

        self.is_trained = True
        self.training_metrics = {
            "algorithm": "GRPO",
            "total_steps": step,
            "training_time_seconds": round(elapsed, 2),
            "num_prompts": n_prompts,
            "group_size": G,
            "episodes_completed": cfg["num_episodes"],
            "overall_mean_reward": round(overall_mean_reward, 4),
            "reward_improvement": round(reward_improvement, 4),
            "episode_stats": episode_stats,
            "trainable_parameters": trainable,
            "total_parameters": total_params,
            "parameter_efficiency": f"{100 * trainable / total_params:.2f}%",
            "adapter_path": adapter_path,
            "device_used": self.device,
            "model_name": cfg["model_name"],
        }

        print(f"\n{'=' * 60}")
        print("RL (GRPO) TRAINING COMPLETE")
        print(f"{'=' * 60}")
        print(f"  Mean reward    : {overall_mean_reward:.4f}")
        print(f"  Improvement    : {reward_improvement:+.4f}")
        print(f"  Steps          : {step}")
        print(f"  Time           : {elapsed:.1f} s")
        print(f"  Adapter saved  : {adapter_path}")
        print(f"{'=' * 60}\n")

        return self.training_metrics

    # ------------------------------------------------------------------
    # Adapter persistence
    # ------------------------------------------------------------------

    def load_adapter(self, adapter_path: Optional[str] = None) -> bool:
        """Load a previously saved RL adapter from disk."""
        if adapter_path is None:
            adapter_path = os.path.join(self.output_dir, "final_adapter")

        if not os.path.exists(adapter_path):
            print(f"[RL] No adapter at {adapter_path}")
            return False

        print(f"[RL] Loading RL adapter from {adapter_path} …")

        cfg_path = os.path.join(adapter_path, "rl_config.json")
        if os.path.exists(cfg_path):
            with open(cfg_path) as f:
                saved = json.load(f)
            self.config.update(saved.get("config", {}))
            self.training_metrics = {
                "algorithm": saved.get("algorithm", "GRPO"),
                "adapter_path": adapter_path,
                "model_name": self.config["model_name"],
            }

        dtype = torch.float16 if self.device == "cuda" else torch.float32
        self.tokenizer = AutoTokenizer.from_pretrained(
            adapter_path, trust_remote_code=True,
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        base = AutoModelForCausalLM.from_pretrained(
            self.config["model_name"],
            torch_dtype=dtype,
            trust_remote_code=True,
        ).to(self.device)

        # If an SFT adapter was used, merge it first
        if self.sft_adapter_path and os.path.exists(self.sft_adapter_path):
            base = PeftModel.from_pretrained(base, self.sft_adapter_path)
            base = base.merge_and_unload()

        self.model = PeftModel.from_pretrained(base, adapter_path)
        self.model = self.model.to(self.device)
        self.is_trained = True

        print("[RL] Adapter loaded ✓")
        return True

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def generate(self, instruction: str,
                 max_new_tokens: int = 256) -> str:
        """Generate a service-selection response using the RL-tuned model."""
        if not self.is_trained or self.model is None:
            raise RuntimeError(
                "RL model not ready. Call train() or load_adapter() first."
            )

        prompt = f"<|system|>\n{SYSTEM_PROMPT}\n<|user|>\n{instruction}\n<|assistant|>\n"

        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=self.config["max_seq_length"],
        ).to(self.device)

        self.model.eval()
        with torch.no_grad():
            out = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=0.3,
                top_p=0.9,
                do_sample=True,
                pad_token_id=self.tokenizer.pad_token_id,
            )

        gen_ids = out[0][inputs["input_ids"].shape[1]:]
        text = self.tokenizer.decode(gen_ids, skip_special_tokens=True)
        if "<|end|>" in text:
            text = text[:text.index("<|end|>")]
        return text.strip()

    # ------------------------------------------------------------------
    # Getters
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, Any]:
        return self.training_metrics


# ═══════════════════════════════════════════════════════════════════════
#  PPO Trainer (classic alternative)
# ═══════════════════════════════════════════════════════════════════════

class PPOTrainer:
    """
    Classic PPO for service composition (alternative to GRPO).

    Uses Generalised Advantage Estimation (GAE) with a simple value
    baseline instead of group-relative normalisation.  Prefer GRPO
    for this domain — PPO is included for comparison / ablation.

    The implementation shares the model loading and generation code
    with GRPOTrainer but uses a different advantage estimation.
    """

    DEFAULT_CONFIG = {
        "model_name": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        "lora_r": 16,
        "lora_alpha": 32,
        "lora_dropout": 0.05,
        "clip_epsilon": 0.2,
        "kl_coeff": 0.04,
        "gamma": 1.0,              # discount factor
        "gae_lambda": 0.95,        # GAE λ
        "value_loss_coeff": 0.5,
        "entropy_coeff": 0.01,
        "learning_rate": 5e-6,
        "weight_decay": 0.01,
        "max_grad_norm": 1.0,
        "num_episodes": 3,
        "batch_size": 2,
        "max_seq_length": 512,
        "max_new_tokens": 128,
        "temperature": 0.7,
        "top_p": 0.9,
    }

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        output_dir: Optional[str] = None,
        sft_adapter_path: Optional[str] = None,
    ):
        if not _deps_available():
            raise ImportError(
                f"RL training requires: {', '.join(_missing_packages())}. "
                f"Install with: pip install {' '.join(_missing_packages())}"
            )

        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self.output_dir = output_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "models", "rl_adapter_ppo",
        )
        self.sft_adapter_path = sft_adapter_path

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None
        self.ref_model = None
        self.value_head = None    # simple linear value baseline
        self.tokenizer = None
        self.is_trained = False
        self.training_metrics: Dict[str, Any] = {}

    @staticmethod
    def is_available() -> bool:
        return _deps_available()

    @staticmethod
    def missing_packages() -> List[str]:
        return _missing_packages()

    def _load_model(self):
        """Load model — same as GRPO but also initialises a value head."""
        cfg = self.config
        dtype = torch.float16 if self.device == "cuda" else torch.float32

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.sft_adapter_path or cfg["model_name"],
            trust_remote_code=True,
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

        base = AutoModelForCausalLM.from_pretrained(
            cfg["model_name"],
            torch_dtype=dtype,
            trust_remote_code=True,
        ).to(self.device)

        if self.sft_adapter_path and os.path.exists(self.sft_adapter_path):
            base = PeftModel.from_pretrained(base, self.sft_adapter_path)
            base = base.merge_and_unload()

        self.ref_model = copy.deepcopy(base)
        self.ref_model.eval()
        for p in self.ref_model.parameters():
            p.requires_grad = False

        lora_cfg = LoraConfig(
            r=cfg["lora_r"],
            lora_alpha=cfg["lora_alpha"],
            lora_dropout=cfg["lora_dropout"],
            target_modules=[
                "q_proj", "k_proj", "v_proj", "o_proj",
                "gate_proj", "up_proj", "down_proj",
            ],
            bias="none",
            task_type=TaskType.CAUSAL_LM,
        )
        self.model = get_peft_model(base, lora_cfg)

        # Simple value baseline (single linear layer → scalar)
        hidden_size = self.model.config.hidden_size
        self.value_head = nn.Linear(hidden_size, 1).to(self.device, dtype=dtype)

        trainable, total = self.model.get_nb_trainable_parameters()
        val_params = sum(p.numel() for p in self.value_head.parameters())
        trainable += val_params
        return trainable, total + val_params

    # ------------------------------------------------------------------
    # Generation helper (mirrors GRPOTrainer._generate_responses)
    # ------------------------------------------------------------------

    def _generate_responses(self, prompt: str, num_responses: int):
        """Sample *num_responses* completions for a single prompt."""
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=self.config["max_seq_length"],
        ).to(self.device)

        prompt_len = inputs["input_ids"].shape[1]
        results = []

        self.model.eval()
        with torch.no_grad():
            for _ in range(num_responses):
                out = self.model.generate(
                    **inputs,
                    max_new_tokens=self.config["max_new_tokens"],
                    temperature=self.config["temperature"],
                    top_p=self.config["top_p"],
                    do_sample=True,
                    pad_token_id=self.tokenizer.pad_token_id,
                )
                gen_ids = out[0][prompt_len:]
                text = self.tokenizer.decode(gen_ids, skip_special_tokens=True)
                if "<|end|>" in text:
                    text = text[:text.index("<|end|>")]
                results.append((text.strip(), prompt_len))
        return results

    def train(
        self,
        prompts: List[Dict[str, Any]],
        reward_fn: Callable,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Run PPO reinforcement learning fine-tuning.

        Same interface as GRPOTrainer.train().
        """
        start = time.time()
        cfg = self.config
        eps = cfg["clip_epsilon"]
        beta = cfg["kl_coeff"]
        gamma = cfg["gamma"]
        lam = cfg["gae_lambda"]
        v_coeff = cfg["value_loss_coeff"]
        eta = cfg["entropy_coeff"]

        print(f"\n{'=' * 60}")
        print("PHASE 3 — RL Fine-Tuning (PPO)")
        print(f"{'=' * 60}")
        print(f"  Model          : {cfg['model_name']}")
        print(f"  Device         : {self.device}")
        print(f"  Prompts        : {len(prompts)}")
        print(f"  Episodes       : {cfg['num_episodes']}")
        print(f"  Clip ε         : {eps}")
        print(f"  KL coeff β     : {beta}")
        print(f"  GAE λ          : {lam}")
        print(f"  LR             : {cfg['learning_rate']}")
        print(f"{'=' * 60}\n")

        trainable, total_params = self._load_model()

        all_params = (
            list(self.model.parameters())
            + list(self.value_head.parameters())
        )
        optimizer = torch.optim.AdamW(
            [p for p in all_params if p.requires_grad],
            lr=cfg["learning_rate"],
            weight_decay=cfg["weight_decay"],
        )

        n = len(prompts)
        bs = cfg["batch_size"]
        total_steps = cfg["num_episodes"] * ((n + bs - 1) // bs)
        step = 0
        episode_stats = []
        all_rewards = []

        for episode in range(cfg["num_episodes"]):
            random.shuffle(prompts)
            ep_rewards = []
            ep_losses = []

            for bi in range(0, n, bs):
                batch = prompts[bi: bi + bs]
                batch_loss = torch.tensor(0.0, device=self.device)
                count = 0

                for item in batch:
                    req = item["request_data"]
                    cands = item["candidate_services"]
                    prompt_text = build_rl_prompt(req, cands)

                    # Single response (PPO is actor-critic, not group-based)
                    responses = self._generate_responses(prompt_text, 1)
                    if not responses:
                        continue
                    resp_text, prompt_len = responses[0]

                    reward = GRPOTrainer._score_response(
                        resp_text, req, reward_fn,
                    )
                    ep_rewards.append(reward)
                    all_rewards.append(reward)

                    # Encode full sequence
                    full = prompt_text + resp_text
                    enc = self.tokenizer(
                        full, return_tensors="pt", truncation=True,
                        max_length=cfg["max_seq_length"],
                    ).to(self.device)
                    input_ids = enc["input_ids"]
                    attn_mask = enc["attention_mask"]

                    # Policy forward
                    self.model.train()
                    outputs = self.model(
                        input_ids=input_ids, attention_mask=attn_mask,
                        output_hidden_states=True,
                    )
                    logits = outputs.logits[:, :-1, :]
                    targets = input_ids[:, 1:]

                    log_probs_all = F.log_softmax(logits, dim=-1)
                    token_lp = log_probs_all.gather(
                        2, targets.unsqueeze(-1),
                    ).squeeze(-1)

                    resp_mask = torch.zeros_like(token_lp, dtype=torch.bool)
                    resp_start = max(prompt_len - 1, 0)
                    resp_mask[:, resp_start:] = True

                    # Value estimate from last hidden state
                    last_hidden = outputs.hidden_states[-1][:, -1, :]
                    value = self.value_head(last_hidden).squeeze(-1)

                    # Advantage = reward - value estimate (simple baseline)
                    advantage = (
                        torch.tensor(reward, device=self.device)
                        - value.detach()
                    )

                    # Reference log-probs
                    with torch.no_grad():
                        ref_out = self.ref_model(
                            input_ids=input_ids, attention_mask=attn_mask,
                        )
                    ref_lp = F.log_softmax(
                        ref_out.logits[:, :-1, :], dim=-1,
                    ).gather(2, targets.unsqueeze(-1)).squeeze(-1)

                    resp_lp = (token_lp * resp_mask.float()).sum()
                    ref_resp_lp = (ref_lp * resp_mask.float()).sum()
                    ratio = torch.exp(resp_lp - ref_resp_lp)

                    # Clipped surrogate
                    surr1 = ratio * advantage
                    surr2 = torch.clamp(ratio, 1 - eps, 1 + eps) * advantage
                    policy_loss = -torch.min(surr1, surr2)

                    # Value loss
                    value_target = torch.tensor(
                        reward, device=self.device, dtype=value.dtype,
                    )
                    value_loss = v_coeff * F.mse_loss(value, value_target)

                    # KL penalty  (KL(π_θ ‖ π_ref) ≈ policy_lp - ref_lp)
                    kl = (resp_lp - ref_resp_lp).detach()
                    kl_loss = beta * kl

                    sample_loss = policy_loss + value_loss + kl_loss
                    batch_loss = batch_loss + sample_loss
                    count += 1

                if count > 0:
                    loss = batch_loss / count
                    optimizer.zero_grad()
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(
                        [p for p in all_params if p.requires_grad],
                        cfg["max_grad_norm"],
                    )
                    optimizer.step()
                    ep_losses.append(float(loss.item()))

                step += 1
                if progress_callback and step % max(total_steps // 20, 1) == 0:
                    progress_callback(
                        step=step, total=total_steps,
                        metrics={
                            "loss": ep_losses[-1] if ep_losses else 0,
                            "mean_reward": (
                                sum(ep_rewards) / max(len(ep_rewards), 1)
                            ),
                            "episode": episode + 1,
                        },
                    )

            mean_r = sum(ep_rewards) / max(len(ep_rewards), 1)
            mean_l = sum(ep_losses) / max(len(ep_losses), 1)
            episode_stats.append({
                "episode": episode + 1,
                "mean_reward": round(mean_r, 4),
                "mean_loss": round(mean_l, 6),
                "num_samples": len(ep_rewards),
            })
            print(
                f"  Episode {episode + 1}/{cfg['num_episodes']}  "
                f"reward={mean_r:.4f}  loss={mean_l:.6f}"
            )

        # Save
        os.makedirs(self.output_dir, exist_ok=True)
        adapter_path = os.path.join(self.output_dir, "final_adapter")
        os.makedirs(adapter_path, exist_ok=True)
        self.model.save_pretrained(adapter_path)
        self.tokenizer.save_pretrained(adapter_path)

        head_path = os.path.join(self.output_dir, "value_head.pt")
        torch.save(self.value_head.state_dict(), head_path)

        with open(os.path.join(adapter_path, "rl_config.json"), "w") as f:
            json.dump({
                "algorithm": "PPO",
                "config": self.config,
                "sft_adapter": self.sft_adapter_path,
            }, f, indent=2)

        elapsed = time.time() - start
        overall_mean_reward = sum(all_rewards) / max(len(all_rewards), 1)
        improvement = 0.0
        if len(episode_stats) >= 2:
            improvement = (
                episode_stats[-1]["mean_reward"]
                - episode_stats[0]["mean_reward"]
            )

        self.is_trained = True
        self.training_metrics = {
            "algorithm": "PPO",
            "total_steps": step,
            "training_time_seconds": round(elapsed, 2),
            "num_prompts": n,
            "episodes_completed": cfg["num_episodes"],
            "overall_mean_reward": round(overall_mean_reward, 4),
            "reward_improvement": round(improvement, 4),
            "episode_stats": episode_stats,
            "trainable_parameters": trainable,
            "total_parameters": total_params,
            "adapter_path": adapter_path,
            "device_used": self.device,
        }

        print(f"\n{'=' * 60}")
        print("RL (PPO) TRAINING COMPLETE")
        print(f"{'=' * 60}")
        print(f"  Mean reward    : {overall_mean_reward:.4f}")
        print(f"  Improvement    : {improvement:+.4f}")
        print(f"  Steps          : {step}")
        print(f"  Time           : {elapsed:.1f} s")
        print(f"{'=' * 60}\n")

        return self.training_metrics

    def load_adapter(self, adapter_path: Optional[str] = None) -> bool:
        """Load a previously saved PPO adapter."""
        if adapter_path is None:
            adapter_path = os.path.join(self.output_dir, "final_adapter")
        if not os.path.exists(adapter_path):
            return False

        cfg = self.config
        dtype = torch.float16 if self.device == "cuda" else torch.float32

        cfg_path = os.path.join(adapter_path, "rl_config.json")
        if os.path.exists(cfg_path):
            with open(cfg_path) as f:
                saved = json.load(f)
            self.config.update(saved.get("config", {}))

        self.tokenizer = AutoTokenizer.from_pretrained(
            adapter_path, trust_remote_code=True,
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        base = AutoModelForCausalLM.from_pretrained(
            cfg["model_name"], torch_dtype=dtype, trust_remote_code=True,
        ).to(self.device)

        if self.sft_adapter_path and os.path.exists(self.sft_adapter_path):
            base = PeftModel.from_pretrained(base, self.sft_adapter_path)
            base = base.merge_and_unload()

        self.model = PeftModel.from_pretrained(base, adapter_path)
        self.model = self.model.to(self.device)
        self.is_trained = True
        print(f"[PPO] Adapter loaded from {adapter_path} ✓")
        return True

    def generate(self, instruction: str, max_new_tokens: int = 256) -> str:
        """Generate using the PPO-tuned model."""
        if not self.is_trained or self.model is None:
            raise RuntimeError("PPO model not ready.")

        prompt = f"<|system|>\n{SYSTEM_PROMPT}\n<|user|>\n{instruction}\n<|assistant|>\n"
        inputs = self.tokenizer(
            prompt, return_tensors="pt", truncation=True,
            max_length=self.config["max_seq_length"],
        ).to(self.device)

        self.model.eval()
        with torch.no_grad():
            out = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=0.3, top_p=0.9, do_sample=True,
                pad_token_id=self.tokenizer.pad_token_id,
            )
        gen_ids = out[0][inputs["input_ids"].shape[1]:]
        text = self.tokenizer.decode(gen_ids, skip_special_tokens=True)
        if "<|end|>" in text:
            text = text[:text.index("<|end|>")]
        return text.strip()

    def get_metrics(self) -> Dict[str, Any]:
        return self.training_metrics
