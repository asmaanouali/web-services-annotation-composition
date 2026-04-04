"""
SFT Dataset Builder for QoS-Driven Service Composition.

Converts training examples (requests + best solutions + service catalog)
into instruction-response pairs suitable for Supervised Fine-Tuning.

Part of: QSRT — QoS-Driven Reinforcement Fine-Tuning with Social Trust Rewards
Phase 1: Supervised Fine-Tuning (SFT)

Copyright (c) 2026. All rights reserved.
"""

import json
import random
from typing import List, Dict, Any


class SFTDatasetBuilder:
    """
    Builds instruction-tuning datasets from service composition examples.

    Each training example becomes a (instruction, response) pair:
      - instruction: composition request + candidate services with QoS & social trust
      - response: optimal service selection as structured JSON with reasoning

    This is the data foundation for Phase 1 SFT, which teaches the LLM
    the "language" of web service composition before RL alignment (Phase 3).
    """

    SYSTEM_PROMPT = (
        "You are a web service composition engine. Given a composition request "
        "with provided input parameters, a target output parameter, QoS constraints, "
        "and a set of candidate services with their QoS metrics and social trust "
        "annotations, select the optimal service(s) to compose. "
        "Respond ONLY in JSON format."
    )

    def __init__(self, services, service_dict=None):
        """
        Args:
            services: List of WebService objects (full catalog)
            service_dict: Optional pre-built {id: WebService} mapping
        """
        self.services = services
        self.service_dict = service_dict or {s.id: s for s in services}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_dataset(self, training_examples: List[Dict],
                      augment: bool = True,
                      max_candidates_shown: int = 10) -> List[Dict[str, str]]:
        """
        Build SFT dataset from training examples.

        Args:
            training_examples: List of {request, best_solution, service} dicts
            augment: Whether to apply data augmentation (shuffled order, fewer candidates)
            max_candidates_shown: Max candidate services included in each prompt

        Returns:
            List of {"text": str} dicts ready for tokenization
        """
        dataset = []

        for example in training_examples:
            request_data = example.get('request', {})
            best_solution = example.get('best_solution')

            if not best_solution:
                continue

            # Get the service IDs used in the best solution
            service_ids = best_solution.get('service_ids', [])
            if not service_ids and best_solution.get('service_id'):
                service_ids = [best_solution['service_id']]

            if not service_ids:
                continue

            # Build candidate set (solution + plausible distractors)
            candidates = self._build_candidate_set(
                request_data, service_ids, max_candidates_shown
            )
            if not candidates:
                continue

            # Build the training pair
            instruction = self._format_instruction(request_data, candidates)
            response = self._format_response(
                service_ids, best_solution, candidates
            )

            dataset.append(self._to_text(instruction, response))

            # Data augmentation: create variations
            if augment:
                augmented = self._augment_example(
                    request_data, service_ids, best_solution,
                    candidates, max_candidates_shown
                )
                dataset.extend(augmented)

        random.shuffle(dataset)
        return dataset

    def stats(self, dataset: List[Dict[str, str]]) -> Dict[str, Any]:
        """Compute dataset statistics for logging."""
        if not dataset:
            return {"total_examples": 0}

        lengths = [len(d["text"]) for d in dataset]
        return {
            "total_examples": len(dataset),
            "avg_text_length": sum(lengths) / len(dataset),
            "max_text_length": max(lengths),
            "min_text_length": min(lengths),
            "total_chars": sum(lengths),
        }

    def to_jsonl(self, dataset: List[Dict[str, str]], filepath: str):
        """Save dataset to JSONL file for reproducibility."""
        with open(filepath, 'w', encoding='utf-8') as f:
            for item in dataset:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def _to_text(self, instruction: str, response: str) -> Dict[str, str]:
        """Package instruction + response into the chat-style text format
        used for causal-LM SFT training."""
        text = (
            f"<|system|>\n{self.SYSTEM_PROMPT}\n"
            f"<|user|>\n{instruction}\n"
            f"<|assistant|>\n{response}<|end|>"
        )
        return {"text": text}

    def _format_instruction(self, request_data: Dict,
                            candidates: Dict) -> str:
        """Format a composition request as an instruction prompt."""
        provided = request_data.get('provided', [])
        resultant = request_data.get('resultant', '')
        qos = request_data.get('qos_constraints', {})

        lines = [f"Compose services to produce '{resultant}'."]
        lines.append(f"Provided inputs ({len(provided)}): "
                     f"{json.dumps(provided[:20])}")

        # QoS constraints
        constraints = []
        mapping = [
            ('ResponseTime', 'RT<=', 0, '0f', 'ms'),
            ('Reliability', 'Rel>=', 0, '1f', '%'),
            ('Availability', 'Avl>=', 0, '1f', '%'),
            ('Throughput', 'TP>=', 0, '1f', ''),
        ]
        for key, prefix, threshold, fmt, unit in mapping:
            val = qos.get(key, 0)
            if val > threshold:
                constraints.append(f"{prefix}{val:{fmt}}{unit}")
        if constraints:
            lines.append(f"QoS constraints: {', '.join(constraints)}")

        lines.append("")
        lines.append("Candidate services:")

        for sid, svc in candidates.items():
            info: Dict[str, Any] = {
                "id": sid,
                "in": svc.inputs[:6],
                "out": svc.outputs[:6],
                "qos": {
                    "rt": round(svc.qos.response_time, 1),
                    "rel": round(svc.qos.reliability, 1),
                    "avl": round(svc.qos.availability, 1),
                    "tp": round(svc.qos.throughput, 1),
                },
            }
            # Social trust annotations (key novelty of QSRT)
            if hasattr(svc, 'annotations') and svc.annotations:
                sn = svc.annotations.social_node
                info["trust"] = round(sn.trust_degree.value, 3)
                info["reputation"] = round(sn.reputation.value, 3)
                info["coop"] = round(sn.cooperativeness.value, 3)

            lines.append(f"  {json.dumps(info, separators=(',', ':'))}")

        return "\n".join(lines)

    def _format_response(self, service_ids: List[str],
                         best_solution: Dict,
                         candidates: Dict) -> str:
        """Format the optimal service selection as a JSON response."""
        utility = best_solution.get('utility', 0)
        is_chain = best_solution.get('is_workflow', len(service_ids) > 1)

        resp: Dict[str, Any] = {
            "selected": service_ids,
            "workflow": service_ids,
            "utility": round(float(utility), 3),
            "is_chain": is_chain,
        }

        # Brief reasoning based on QoS of selected services
        reasons = []
        for sid in service_ids:
            svc = candidates.get(sid) or self.service_dict.get(sid)
            if svc:
                parts = [f"{sid}:"]
                parts.append(f"rel={svc.qos.reliability:.1f}%")
                parts.append(f"rt={svc.qos.response_time:.0f}ms")
                if hasattr(svc, 'annotations') and svc.annotations:
                    sn = svc.annotations.social_node
                    parts.append(f"trust={sn.trust_degree.value:.2f}")
                reasons.append(" ".join(parts))

        if reasons:
            resp["reasoning"] = "; ".join(reasons)

        return json.dumps(resp, separators=(',', ':'))

    # ------------------------------------------------------------------
    # Candidate set construction
    # ------------------------------------------------------------------

    def _build_candidate_set(self, request_data: Dict,
                             solution_ids: List[str],
                             max_candidates: int) -> Dict:
        """Build candidate set: solution services + plausible distractors."""
        provided = set(request_data.get('provided', []))
        resultant = request_data.get('resultant', '')

        candidates = {}

        # Always include solution services
        for sid in solution_ids:
            if sid in self.service_dict:
                candidates[sid] = self.service_dict[sid]

        # Add distractors: services that share I/O with the request
        for s in self.services:
            if s.id in candidates:
                continue
            if resultant in s.outputs:
                candidates[s.id] = s
            elif any(inp in provided for inp in s.inputs):
                candidates[s.id] = s
            if len(candidates) >= max_candidates:
                break

        # Pad with random services if needed
        if len(candidates) < min(max_candidates, len(self.services)):
            remaining = [s for s in self.services if s.id not in candidates]
            random.shuffle(remaining)
            for s in remaining[:max_candidates - len(candidates)]:
                candidates[s.id] = s

        return candidates

    # ------------------------------------------------------------------
    # Data augmentation
    # ------------------------------------------------------------------

    def _augment_example(self, request_data, solution_ids, best_solution,
                         original_candidates, max_candidates):
        """Create augmented variations of a training example."""
        augmented = []

        # Variation 1: shuffled candidate order
        items = list(original_candidates.items())
        random.shuffle(items)
        shuffled = dict(items)

        instruction = self._format_instruction(request_data, shuffled)
        response = self._format_response(
            solution_ids, best_solution, shuffled
        )
        augmented.append(self._to_text(instruction, response))

        # Variation 2: reduced candidate set (makes the task harder)
        # Ensure at least as many distractors as solution services remain
        n_solution = sum(1 for sid in solution_ids if sid in original_candidates)
        min_distractors = max(2, n_solution)
        if len(original_candidates) > n_solution + min_distractors:
            reduced = {}
            for sid in solution_ids:
                if sid in original_candidates:
                    reduced[sid] = original_candidates[sid]
            distractors = [
                (k, v) for k, v in original_candidates.items()
                if k not in solution_ids
            ]
            random.shuffle(distractors)
            for k, v in distractors[:min_distractors]:
                reduced[k] = v

            instruction = self._format_instruction(request_data, reduced)
            response = self._format_response(
                solution_ids, best_solution, reduced
            )
            augmented.append(self._to_text(instruction, response))

        return augmented
