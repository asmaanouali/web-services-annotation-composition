"""
Analytical Multi-Objective Reward Calculator for Service Composition.

Computes a scalar reward from three orthogonal signal sources:
    R = α · QoS_utility  +  β · Social_trust  +  γ · Chain_validity

This is the first reward function that combines measurable QoS metrics with
social trust annotations (trust degree, reputation, cooperativeness) derived
from a MOF-based Social Web Services metamodel.  No human labelling is needed.

Part of: QSRT — QoS-Driven Reinforcement Fine-Tuning with Social Trust Rewards
Phase 2: Reward Model

Copyright (c) 2026. All rights reserved.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Any, Tuple

from models.service import QoS, WebService, CompositionRequest
from utils.qos_calculator import (
    calculate_utility,
    aggregate_qos,
    normalize,
    normalize_inverse,
)


# ═══════════════════════════════════════════════════════════════════════
# Reward weight presets (can be tuned per domain)
# ═══════════════════════════════════════════════════════════════════════
DEFAULT_WEIGHTS = {
    "alpha": 0.50,   # QoS utility weight
    "beta":  0.35,   # Social trust weight
    "gamma": 0.15,   # Chain structural validity weight
}

# Sub-weights inside each component
QOS_SUB_WEIGHTS = {
    "reliability":    0.20,
    "availability":   0.20,
    "response_time":  0.15,   # inverse — lower is better
    "throughput":     0.10,
    "successability": 0.10,
    "latency":        0.10,   # inverse
    "compliance":     0.05,
    "best_practices": 0.05,
    "documentation":  0.05,
}

SOCIAL_SUB_WEIGHTS = {
    "trust_degree":      0.40,
    "reputation":        0.35,
    "cooperativeness":   0.25,
}

CHAIN_SUB_WEIGHTS = {
    "io_validity":       0.35,   # I/O chain correctness
    "goal_reached":      0.30,   # target output produced
    "constraint_sat":    0.20,   # QoS constraint satisfaction
    "chain_length_pen":  0.15,   # shorter chains preferred (parsimony)
}


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

class RewardCalculator:
    """
    Computes a composite, differentiable reward for a service composition.

    This class is usable both as a standalone analytical evaluator **and** as the
    label generator for training a neural reward model (see ``RewardModelTrainer``).

    Every sub-score is normalised to [0, 1] before weighting so that the final
    reward  R ∈ [0, 1]  regardless of the raw QoS scale.
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        w = weights or {}
        self.alpha = float(w.get("alpha", DEFAULT_WEIGHTS["alpha"]))
        self.beta  = float(w.get("beta",  DEFAULT_WEIGHTS["beta"]))
        self.gamma = float(w.get("gamma", DEFAULT_WEIGHTS["gamma"]))

        # Normalise so α+β+γ = 1
        total = self.alpha + self.beta + self.gamma
        if total > 0:
            self.alpha /= total
            self.beta  /= total
            self.gamma /= total

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def compute_reward(
        self,
        services: List[WebService],
        request: CompositionRequest,
        workflow: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Compute the full multi-objective reward for a composition.

        Args:
            services:  list of WebService objects used in the composition
            request:   the composition request (provides inputs, target, QoS constraints)
            workflow:   optional ordered list of service IDs (for chain validation)

        Returns:
            dict with keys:
                reward          – final scalar in [0, 1]
                qos_score       – normalised QoS component in [0, 1]
                social_score    – normalised social-trust component in [0, 1]
                chain_score     – normalised chain-validity component in [0, 1]
                detail          – full breakdown dict
        """
        qos_score, qos_detail     = self._compute_qos_score(services, request)
        social_score, soc_detail  = self._compute_social_score(services)
        chain_score, chain_detail = self._compute_chain_score(
            services, request, workflow,
        )

        reward = (
            self.alpha * qos_score
            + self.beta * social_score
            + self.gamma * chain_score
        )

        return {
            "reward": round(float(reward), 6),
            "qos_score": round(float(qos_score), 6),
            "social_score": round(float(social_score), 6),
            "chain_score": round(float(chain_score), 6),
            "weights": {
                "alpha": self.alpha,
                "beta": self.beta,
                "gamma": self.gamma,
            },
            "detail": {
                "qos": qos_detail,
                "social": soc_detail,
                "chain": chain_detail,
            },
        }

    # ------------------------------------------------------------------
    # Shorthand: reward only (for RL training loop)
    # ------------------------------------------------------------------

    def reward(
        self,
        services: List[WebService],
        request: CompositionRequest,
        workflow: Optional[List[str]] = None,
    ) -> float:
        """Return the scalar reward value only (no detail dict)."""
        return self.compute_reward(services, request, workflow)["reward"]

    # ══════════════════════════════════════════════════════════════════
    # Component 1: QoS utility  (α)
    # ══════════════════════════════════════════════════════════════════

    def _compute_qos_score(
        self, services: List[WebService], request: CompositionRequest,
    ) -> Tuple[float, Dict]:
        """
        Normalised QoS quality score ∈ [0, 1].

        Uses the same aggregate_qos logic as the existing system but
        re-normalises into a unit interval for reward compatibility.
        """
        if not services:
            return 0.0, {"raw_utility": 0, "note": "no services"}

        agg_qos = aggregate_qos(services) if len(services) > 1 else services[0].qos

        # Individual metric scores in [0, 1]
        scores = {
            "reliability":    _norm01(agg_qos.reliability,    0, 100),
            "availability":   _norm01(agg_qos.availability,   0, 100),
            "response_time":  _inv01(agg_qos.response_time,   0, 2000),
            "throughput":     _norm01(agg_qos.throughput,      0, 1000),
            "successability": _norm01(agg_qos.successability,  0, 100),
            "latency":        _inv01(agg_qos.latency,         0, 2000),
            "compliance":     _norm01(agg_qos.compliance,      0, 100),
            "best_practices": _norm01(agg_qos.best_practices,  0, 100),
            "documentation":  _norm01(agg_qos.documentation,   0, 100),
        }

        weighted = sum(
            scores[k] * QOS_SUB_WEIGHTS.get(k, 0) for k in scores
        )
        # Clamp
        weighted = max(0.0, min(1.0, weighted))

        # Also compute the existing system utility for reference
        qos_checks = agg_qos.meets_constraints(request.qos_constraints)
        raw_utility = calculate_utility(agg_qos, request.qos_constraints, qos_checks)

        detail = {
            "metric_scores": {k: round(v, 4) for k, v in scores.items()},
            "weighted_score": round(weighted, 4),
            "raw_utility": round(raw_utility, 3),
            "constraints_met": sum(qos_checks.values()),
            "constraints_total": len(qos_checks),
        }
        return weighted, detail

    # ══════════════════════════════════════════════════════════════════
    # Component 2: Social Trust  (β)
    # ══════════════════════════════════════════════════════════════════

    def _compute_social_score(
        self, services: List[WebService],
    ) -> Tuple[float, Dict]:
        """
        Normalised social-trust score ∈ [0, 1].

        Aggregates trust_degree, reputation, cooperativeness from every
        service's social-node annotation.  When annotations are absent
        a neutral score of 0.5 is used.
        """
        if not services:
            return 0.0, {"note": "no services"}

        trust_vals = []
        rep_vals = []
        coop_vals = []
        collab_density = 0.0   # average collaboration association count
        annotated_count = 0

        for s in services:
            ann = getattr(s, "annotations", None)
            if ann is not None:
                sn = ann.social_node
                trust_vals.append(float(sn.trust_degree.value))
                rep_vals.append(float(sn.reputation.value))
                coop_vals.append(float(sn.cooperativeness.value))

                # Collaboration density: richer social network → higher reward
                n_assoc = len(sn.associations)
                collab_density += n_assoc
                annotated_count += 1
            else:
                # Neutral defaults when not annotated
                trust_vals.append(0.5)
                rep_vals.append(0.5)
                coop_vals.append(0.5)

        avg_trust = sum(trust_vals) / len(trust_vals)
        avg_rep   = sum(rep_vals)   / len(rep_vals)
        avg_coop  = sum(coop_vals)  / len(coop_vals)

        # Clamp to [0, 1]
        avg_trust = max(0.0, min(1.0, avg_trust))
        avg_rep   = max(0.0, min(1.0, avg_rep))
        avg_coop  = max(0.0, min(1.0, avg_coop))

        score = (
            SOCIAL_SUB_WEIGHTS["trust_degree"]    * avg_trust
            + SOCIAL_SUB_WEIGHTS["reputation"]      * avg_rep
            + SOCIAL_SUB_WEIGHTS["cooperativeness"] * avg_coop
        )

        # Small bonus for dense social network (max 5 % boost)
        if annotated_count > 0:
            avg_assoc = collab_density / annotated_count
            network_bonus = min(avg_assoc / 20.0, 0.05)
            score = min(1.0, score + network_bonus)

        detail = {
            "avg_trust": round(avg_trust, 4),
            "avg_reputation": round(avg_rep, 4),
            "avg_cooperativeness": round(avg_coop, 4),
            "annotated_services": annotated_count,
            "total_services": len(services),
            "network_density": round(collab_density, 1),
            "weighted_score": round(score, 4),
        }
        return score, detail

    # ══════════════════════════════════════════════════════════════════
    # Component 3: Chain Structural Validity  (γ)
    # ══════════════════════════════════════════════════════════════════

    def _compute_chain_score(
        self,
        services: List[WebService],
        request: CompositionRequest,
        workflow: Optional[List[str]] = None,
    ) -> Tuple[float, Dict]:
        """
        Structural chain-validity score ∈ [0, 1].

        Checks:
        a) I/O validity — every service's inputs are satisfied by the
           provided params + outputs of preceding services.
        b) Goal reached — the target output appears in the final
           available-parameter set.
        c) QoS constraint satisfaction ratio.
        d) Chain parsimony — shorter valid chains score higher.
        """
        if not services:
            return 0.0, {"note": "no services"}

        provided = set(request.provided)
        available = set(provided)

        # a) I/O validity: fraction of services whose inputs are satisfied
        valid_steps = 0
        for s in services:
            inputs_ok = all(inp in available for inp in s.inputs)
            if inputs_ok:
                valid_steps += 1
            available.update(s.outputs)

        io_validity = valid_steps / len(services)

        # b) Goal reached?
        goal_reached = 1.0 if request.resultant in available else 0.0

        # c) QoS constraint satisfaction
        agg_qos = aggregate_qos(services) if len(services) > 1 else services[0].qos
        qos_checks = agg_qos.meets_constraints(request.qos_constraints)
        constraint_sat = sum(qos_checks.values()) / max(len(qos_checks), 1)

        # d) Chain parsimony — sigmoid penalty for long chains
        #    1 service → 1.0, 5 → ~0.73, 10 → ~0.5, 20 → ~0.27
        chain_len = len(services)
        parsimony = 1.0 / (1.0 + math.log1p(chain_len - 1) * 0.5)

        score = (
            CHAIN_SUB_WEIGHTS["io_validity"]      * io_validity
            + CHAIN_SUB_WEIGHTS["goal_reached"]     * goal_reached
            + CHAIN_SUB_WEIGHTS["constraint_sat"]   * constraint_sat
            + CHAIN_SUB_WEIGHTS["chain_length_pen"] * parsimony
        )
        score = max(0.0, min(1.0, score))

        detail = {
            "io_validity": round(io_validity, 4),
            "goal_reached": goal_reached,
            "constraint_satisfaction": round(constraint_sat, 4),
            "chain_length": chain_len,
            "parsimony": round(parsimony, 4),
            "weighted_score": round(score, 4),
        }
        return score, detail


# ═══════════════════════════════════════════════════════════════════════
# Preference-pair generation (for training the neural reward model)
# ═══════════════════════════════════════════════════════════════════════

class RewardDatasetBuilder:
    """
    Generates (chosen, rejected) preference pairs from composition examples.

    For each request that has a known-good solution:
      chosen   = the best-solution composition  (high reward)
      rejected = a worse composition (random, or lower-utility alternative)

    This produces training data for the neural ``RewardModelTrainer`` using
    the Bradley–Terry preference framework (same as InstructGPT / DPO).
    """

    def __init__(
        self,
        services: List[WebService],
        service_dict: Optional[Dict[str, WebService]] = None,
        reward_calculator: Optional[RewardCalculator] = None,
    ):
        self.services = services
        self.service_dict = service_dict or {s.id: s for s in services}
        self.reward_calc = reward_calculator or RewardCalculator()

    def build_preference_pairs(
        self,
        training_examples: List[Dict],
        negative_strategies: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Build preference pairs from training examples.

        Args:
            training_examples: list of {request, best_solution, ...}
            negative_strategies: how to build rejected samples
                'random'    — random service(s) from the catalog
                'degraded'  — real solution with one service swapped
                'partial'   — real solution with one service removed

        Returns:
            list of {"chosen": {...}, "rejected": {...}, "reward_margin": float}
        """
        import random as _rand

        if negative_strategies is None:
            negative_strategies = ["random", "degraded", "partial"]

        pairs: List[Dict[str, Any]] = []

        for example in training_examples:
            req_data = example.get("request", {})
            best_sol = example.get("best_solution")
            if not best_sol:
                continue

            solution_ids = best_sol.get("service_ids", [])
            if not solution_ids and best_sol.get("service_id"):
                solution_ids = [best_sol["service_id"]]
            if not solution_ids:
                continue

            # Build a temporary CompositionRequest
            from models.service import CompositionRequest as CR
            cr = CR(req_data.get("id", "tmp"))
            cr.provided = req_data.get("provided", [])
            cr.resultant = req_data.get("resultant", "")
            qos_data = req_data.get("qos_constraints", {})
            cr.qos_constraints = QoS(qos_data)

            # Resolve chosen services
            chosen_svcs = [
                self.service_dict[sid]
                for sid in solution_ids
                if sid in self.service_dict
            ]
            if not chosen_svcs:
                continue

            chosen_reward_info = self.reward_calc.compute_reward(
                chosen_svcs, cr, solution_ids,
            )
            chosen_reward = chosen_reward_info["reward"]

            # For each negative strategy, create a rejected sample
            for strategy in negative_strategies:
                rejected_svcs, rejected_ids = self._make_negative(
                    strategy, chosen_svcs, solution_ids, cr,
                )
                if not rejected_svcs:
                    continue

                rej_reward_info = self.reward_calc.compute_reward(
                    rejected_svcs, cr, rejected_ids,
                )
                rej_reward = rej_reward_info["reward"]

                # Only keep pairs with a meaningful margin
                margin = chosen_reward - rej_reward
                if margin <= 0.01:
                    continue

                pair = {
                    "chosen": {
                        "service_ids": solution_ids,
                        "reward": chosen_reward,
                        "detail": chosen_reward_info,
                    },
                    "rejected": {
                        "service_ids": rejected_ids,
                        "reward": rej_reward,
                        "detail": rej_reward_info,
                    },
                    "reward_margin": round(margin, 6),
                    "request": req_data,
                    "strategy": strategy,
                }
                pairs.append(pair)

        _rand.shuffle(pairs)
        return pairs

    # ------------------------------------------------------------------
    # Negative sampling strategies
    # ------------------------------------------------------------------

    def _make_negative(
        self, strategy: str,
        chosen_svcs: List[WebService],
        chosen_ids: List[str],
        request: CompositionRequest,
    ) -> Tuple[List[WebService], List[str]]:
        import random as _rand

        if strategy == "random":
            # Pick random service(s) — same chain length as chosen
            pool = [s for s in self.services if s.id not in set(chosen_ids)]
            if not pool:
                return [], []
            k = min(len(chosen_ids), len(pool))
            picked = _rand.sample(pool, k)
            return picked, [s.id for s in picked]

        elif strategy == "degraded":
            # Swap one service in the chain with a random one
            if len(chosen_ids) < 1:
                return [], []
            idx = _rand.randrange(len(chosen_ids))
            pool = [s for s in self.services if s.id not in set(chosen_ids)]
            if not pool:
                return [], []
            replacement = _rand.choice(pool)
            new_svcs = list(chosen_svcs)
            new_ids = list(chosen_ids)
            new_svcs[idx] = replacement
            new_ids[idx] = replacement.id
            return new_svcs, new_ids

        elif strategy == "partial":
            # Remove one service from the chain
            if len(chosen_ids) < 2:
                return [], []
            idx = _rand.randrange(len(chosen_ids))
            new_svcs = [s for i, s in enumerate(chosen_svcs) if i != idx]
            new_ids = [sid for i, sid in enumerate(chosen_ids) if i != idx]
            return new_svcs, new_ids

        return [], []

    def stats(self, pairs: List[Dict]) -> Dict[str, Any]:
        """Return summary statistics of the generated pairs."""
        if not pairs:
            return {"total_pairs": 0}
        margins = [p["reward_margin"] for p in pairs]
        by_strat = {}
        for p in pairs:
            s = p.get("strategy", "?")
            by_strat[s] = by_strat.get(s, 0) + 1
        return {
            "total_pairs": len(pairs),
            "avg_margin": round(sum(margins) / len(margins), 4),
            "max_margin": round(max(margins), 4),
            "min_margin": round(min(margins), 4),
            "by_strategy": by_strat,
        }


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _norm01(value: float, lo: float, hi: float) -> float:
    """Normalise *value* from [lo, hi] → [0, 1], clamped."""
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def _inv01(value: float, lo: float, hi: float) -> float:
    """Inverse normalisation (lower is better) → [0, 1], clamped."""
    return 1.0 - _norm01(value, lo, hi)
