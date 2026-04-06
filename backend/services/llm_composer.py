"""
Production-grade LLM-based Web Service Composer.

Uses a fine-tuned LoRA model (Phase 1 SFT) for intelligent service selection with:
- Real Supervised Fine-Tuning via LoRA adapters (QSRT Phase 1)
- Knowledge base of composition patterns
- Continuous learning from composition history
- Fallback to Ollama / knowledge-based selection when SFT model is unavailable

Part of: QSRT — QoS-Driven Reinforcement Fine-Tuning with Social Trust Rewards
"""

import os
import time
import json
import heapq
import requests as http_requests
from collections import defaultdict
from models.service import CompositionResult, QoS
from utils.qos_calculator import calculate_utility, aggregate_qos

# SFT components (graceful if missing)
try:
    from services.sft_trainer import SFTLoRATrainer
    from services.sft_dataset import SFTDatasetBuilder
    _SFT_AVAILABLE = SFTLoRATrainer.is_available()
except Exception:
    _SFT_AVAILABLE = False

# Reward Model components (Phase 2 — graceful if missing)
try:
    from services.reward_calculator import RewardCalculator, RewardDatasetBuilder
    _REWARD_CALC_AVAILABLE = True
except Exception:
    _REWARD_CALC_AVAILABLE = False

try:
    from services.reward_model import RewardModelTrainer
    _REWARD_MODEL_AVAILABLE = RewardModelTrainer.is_available()
except Exception:
    _REWARD_MODEL_AVAILABLE = False

# RL Trainer components (Phase 3 — graceful if missing)
try:
    from services.rl_trainer import GRPOTrainer, PPOTrainer, build_rl_prompt
    _RL_AVAILABLE = GRPOTrainer.is_available()
except Exception:
    _RL_AVAILABLE = False


class LLMComposer:
    """
    Intelligent service composer using LLM (Ollama) + knowledge base.

    Architecture:
    1. Knowledge Base: patterns extracted from training data
    2. Service Index: fast lookup structures for candidate services
    3. LLM Inference: Ollama-based reasoning for service selection
    4. Fallback: knowledge-based selection when LLM is unavailable
    """

    def __init__(self, services, training_examples=None,
                 ollama_url="http://localhost:11434",
                 sft_model_name=None,
                 sft_output_dir=None):
        self.services = services
        self.service_dict = {s.id: s for s in services}
        self.ollama_url = ollama_url
        self.model = "llama3.2:3b"

        # Fast lookup indexes
        self._output_index = defaultdict(list)
        self._input_index = defaultdict(list)
        self._service_input_sets = {}
        self._build_indexes()

        # Knowledge base populated during training
        self.knowledge_base = {
            'patterns': [],
            'service_rankings': {},
            'io_chains': [],
        }

        # Training quality metrics
        self.training_metrics = {
            'total_examples': 0,
            'examples_with_solutions': 0,
            'avg_solution_utility': 0.0,
            'patterns_extracted': 0,
            'coverage_rate': 0.0,
        }

        # SFT LoRA trainer (Phase 1 of QSRT)
        self.sft_trainer = None
        self.sft_dataset_builder = None
        self.sft_metrics = {}           # metrics from real SFT training
        self._sft_model_name = sft_model_name
        self._sft_output_dir = sft_output_dir
        self._sft_available = _SFT_AVAILABLE
        self._sft_trained = False       # True after successful SFT

        # Reward Model (Phase 2 of QSRT)
        self.reward_calculator = None
        self.reward_model_trainer = None
        self.reward_metrics = {}        # metrics from reward model training
        self._reward_calc_available = _REWARD_CALC_AVAILABLE
        self._reward_model_available = _REWARD_MODEL_AVAILABLE
        self._reward_model_trained = False

        if self._reward_calc_available:
            self.reward_calculator = RewardCalculator()

        # RL Trainer (Phase 3 of QSRT)
        self.rl_trainer = None          # GRPOTrainer or PPOTrainer instance
        self.rl_metrics = {}            # metrics from RL training
        self._rl_available = _RL_AVAILABLE
        self._rl_trained = False
        self._rl_algorithm = None       # "GRPO" or "PPO"

        # Try to load previously trained adapters from disk
        self._try_load_existing_adapter()
        self._try_load_existing_reward_model()
        self._try_load_existing_rl_adapter()

        # Continuous learning state
        self.composition_history = []
        self.success_patterns = []
        self.error_patterns = []

        if training_examples:
            self.train(training_examples)

    def _try_load_existing_adapter(self):
        """Attempt to load a LoRA adapter saved from a previous session."""
        if not self._sft_available:
            return
        try:
            self.sft_trainer = SFTLoRATrainer(
                model_name=self._sft_model_name,
                output_dir=self._sft_output_dir,
            )
            if self.sft_trainer.load_adapter():
                self.sft_dataset_builder = SFTDatasetBuilder(
                    self.services, self.service_dict
                )
                self._sft_trained = True
                print("[LLMComposer] Loaded existing SFT adapter ✓")
            else:
                self.sft_trainer = None
        except Exception as e:
            print(f"[LLMComposer] No existing adapter: {e}")
            self.sft_trainer = None

    def _try_load_existing_reward_model(self):
        """Attempt to load a reward model saved from a previous session."""
        if not self._reward_model_available:
            return
        try:
            self.reward_model_trainer = RewardModelTrainer()
            if self.reward_model_trainer.load():
                self._reward_model_trained = True
                print("[LLMComposer] Loaded existing reward model \u2713")
            else:
                self.reward_model_trainer = None
        except Exception as e:
            print(f"[LLMComposer] No existing reward model: {e}")
            self.reward_model_trainer = None

    def _try_load_existing_rl_adapter(self):
        """Attempt to load an RL adapter saved from a previous session."""
        if not self._rl_available:
            return
        # Try GRPO first, then PPO
        sft_path = None
        if self.sft_trainer and self._sft_trained:
            sft_path = self.sft_trainer.output_dir
            if sft_path:
                sft_path = os.path.join(sft_path, 'final_adapter')
        for TrainerCls, algo in [(GRPOTrainer, 'GRPO'), (PPOTrainer, 'PPO')]:
            try:
                trainer = TrainerCls(sft_adapter_path=sft_path)
                if trainer.load_adapter():
                    self.rl_trainer = trainer
                    self._rl_trained = True
                    self._rl_algorithm = algo
                    print(f"[LLMComposer] Loaded existing RL adapter ({algo}) \u2713")
                    return
            except Exception as e:
                print(f"[LLMComposer] No existing {algo} adapter: {e}")
        self.rl_trainer = None

    # ------------------------------------------------------------------
    # Index building
    # ------------------------------------------------------------------

    def _build_indexes(self):
        """Build fast lookup indexes for services."""
        self._output_index.clear()
        self._input_index.clear()
        self._service_input_sets.clear()

        for s in self.services:
            self._service_input_sets[s.id] = frozenset(s.inputs)
            for out in s.outputs:
                self._output_index[out].append(s)
            for inp in s.inputs:
                self._input_index[inp].append(s)

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(self, training_examples):
        """
        Process training examples to build a knowledge base AND, when
        SFT dependencies are available, perform real Supervised Fine-Tuning
        with LoRA adapters (Phase 1 of QSRT).

        If torch/transformers/peft are not installed, the method falls back
        to the knowledge-base-only approach (still useful for scoring).

        Returns training quality metrics (knowledge-base + SFT combined).
        """
        self.knowledge_base = {
            'patterns': [],
            'service_rankings': {},
            'io_chains': [],
        }

        examples_with_solutions = 0
        total_utility = 0.0
        service_usage_count = defaultdict(int)
        service_success_utility = defaultdict(list)

        for example in training_examples:
            request_data = example.get('request', {})
            best_solution = example.get('best_solution')

            if not best_solution:
                continue

            examples_with_solutions += 1
            utility = float(best_solution.get('utility', 0))
            total_utility += utility

            # Collect service ids from the solution
            service_ids = best_solution.get('service_ids', [])
            if not service_ids and best_solution.get('service_id'):
                service_ids = [best_solution['service_id']]

            for sid in service_ids:
                service_usage_count[sid] += 1
                service_success_utility[sid].append(utility)

            # Build composition pattern
            pattern = {
                'provided_count': len(request_data.get('provided', [])),
                'resultant': request_data.get('resultant'),
                'service_ids': service_ids,
                'utility': utility,
                'is_workflow': best_solution.get('is_workflow', False),
            }

            # Attach service I/O signatures when available
            for sid in service_ids:
                svc = self.service_dict.get(sid)
                if svc:
                    pattern.setdefault('service_ios', []).append({
                        'id': sid,
                        'inputs': svc.inputs,
                        'outputs': svc.outputs,
                    })

            self.knowledge_base['patterns'].append(pattern)

            # Build I/O chain entry
            if pattern.get('resultant'):
                self.knowledge_base['io_chains'].append({
                    'target': pattern['resultant'],
                    'services': service_ids,
                    'utility': utility,
                })

        # Build service rankings from training frequency + utility
        for sid, count in service_usage_count.items():
            utilities = service_success_utility.get(sid, [])
            avg_util = sum(utilities) / len(utilities) if utilities else 0
            self.knowledge_base['service_rankings'][sid] = {
                'usage_count': count,
                'avg_utility': avg_util,
                'score': count * 0.3 + avg_util * 0.7,
            }

        # Compute training quality metrics
        total = len(training_examples)
        self.training_metrics = {
            'total_examples': total,
            'examples_with_solutions': examples_with_solutions,
            'avg_solution_utility': (
                total_utility / max(examples_with_solutions, 1)
            ),
            'patterns_extracted': len(self.knowledge_base['patterns']),
            'coverage_rate': (
                (examples_with_solutions / total * 100) if total > 0 else 0
            ),
        }

        return self.training_metrics

    # ------------------------------------------------------------------
    # Phase 1: Real SFT with LoRA
    # ------------------------------------------------------------------

    def run_sft(self, training_examples, sft_config=None, progress_callback=None):
        """
        Run real Supervised Fine-Tuning with LoRA adapters.

        This method:
        1. Builds an instruction-tuning dataset from training examples.
        2. Fine-tunes a causal LM with LoRA (only ~0.1% of params trained).
        3. Saves the adapter to disk for future sessions.

        Args:
            training_examples: same format as train()
            sft_config: optional dict with keys:
                - model_name: HuggingFace model ID (default TinyLlama-1.1B)
                - lora_config: dict of LoRA hyper-parameters
                - training_config: dict of training hyper-parameters

        Returns:
            dict with SFT training metrics (loss, steps, time, etc.)

        Raises:
            ImportError if SFT dependencies are not installed.
        """
        if not self._sft_available:
            missing = SFTLoRATrainer.missing_packages() if _SFT_AVAILABLE else [
                'torch', 'transformers', 'peft', 'datasets'
            ]
            raise ImportError(
                f"SFT training requires: {', '.join(missing)}. "
                f"Install with: pip install {' '.join(missing)}"
            )

        sft_config = sft_config or {}

        # 1. Build the dataset
        self.sft_dataset_builder = SFTDatasetBuilder(
            self.services, self.service_dict
        )
        dataset = self.sft_dataset_builder.build_dataset(
            training_examples, augment=True
        )
        dataset_stats = self.sft_dataset_builder.stats(dataset)
        print(f"[SFT] Dataset built: {dataset_stats}")

        if not dataset:
            raise ValueError(
                "Could not build any SFT examples from the training data. "
                "Ensure training_examples contain 'best_solution' entries."
            )

        # 2. Initialise the trainer
        self.sft_trainer = SFTLoRATrainer(
            model_name=sft_config.get('model_name', self._sft_model_name),
            output_dir=sft_config.get('output_dir', self._sft_output_dir),
            lora_config=sft_config.get('lora_config'),
            training_config=sft_config.get('training_config'),
        )

        # 3. Train!
        self.sft_metrics = self.sft_trainer.train(
            dataset, progress_callback=progress_callback,
        )
        self._sft_trained = True

        return {
            'sft_metrics': self.sft_metrics,
            'dataset_stats': dataset_stats,
        }

    def get_training_metrics(self):
        """Return training quality metrics (knowledge-base + SFT + Reward + RL)."""
        metrics = dict(self.training_metrics)
        metrics['sft_available'] = self._sft_available
        metrics['sft_trained'] = self._sft_trained
        if self.sft_metrics:
            metrics['sft'] = self.sft_metrics
        metrics['reward_calc_available'] = self._reward_calc_available
        metrics['reward_model_available'] = self._reward_model_available
        metrics['reward_model_trained'] = self._reward_model_trained
        if self.reward_metrics:
            metrics['reward_model'] = self.reward_metrics
        metrics['rl_available'] = self._rl_available
        metrics['rl_trained'] = self._rl_trained
        metrics['rl_algorithm'] = self._rl_algorithm
        if self.rl_metrics:
            metrics['rl'] = self.rl_metrics
        return metrics

    # ------------------------------------------------------------------
    # Phase 2: Reward Model Training
    # ------------------------------------------------------------------

    def compute_reward(self, services, request, workflow=None):
        """
        Compute the analytical multi-objective reward for a composition.

        R = \u03b1 \u00b7 QoS_utility + \u03b2 \u00b7 Social_trust + \u03b3 \u00b7 Chain_validity

        Returns dict with reward breakdown or None if reward calculator
        is unavailable.
        """
        if not self.reward_calculator:
            return None
        return self.reward_calculator.compute_reward(services, request, workflow)

    def run_reward_training(self, training_examples, reward_config=None, progress_callback=None):
        """
        Phase 2: Train the neural reward model.

        Steps:
        1. Generate (chosen, rejected) preference pairs using the
           analytical RewardCalculator as ground truth.
        2. Train a neural reward model (LoRA + reward head) with
           Bradley\u2013Terry preference loss.
        3. Save the model to disk.

        Args:
            training_examples: same format as train()
            reward_config: optional dict with training hyper-params

        Returns:
            dict with reward model training metrics
        """
        if not self._reward_calc_available:
            raise RuntimeError(
                "RewardCalculator not available. "
                "Check services/reward_calculator.py imports."
            )
        if not self._reward_model_available:
            missing = RewardModelTrainer.missing_packages()
            raise ImportError(
                f"Reward model training requires: {', '.join(missing)}. "
                f"Install with: pip install {' '.join(missing)}"
            )

        reward_config = reward_config or {}

        # 1. Build preference pairs
        dataset_builder = RewardDatasetBuilder(
            self.services, self.service_dict, self.reward_calculator,
        )
        pairs = dataset_builder.build_preference_pairs(training_examples)
        pair_stats = dataset_builder.stats(pairs)
        print(f"[Phase 2] Preference pairs built: {pair_stats}")

        if not pairs:
            raise ValueError(
                "No preference pairs could be generated. "
                "Ensure training_examples contain 'best_solution' entries "
                "and services are loaded."
            )

        # 2. Train neural reward model
        self.reward_model_trainer = RewardModelTrainer(
            config=reward_config,
        )
        self.reward_metrics = self.reward_model_trainer.train(
            pairs, self.service_dict,
            progress_callback=progress_callback,
        )
        self._reward_model_trained = True

        return {
            'reward_metrics': self.reward_metrics,
            'pair_stats': pair_stats,
        }

    def predict_reward(self, service_ids, request_data):
        """
        Predict reward using the trained neural reward model.

        Falls back to the analytical calculator if the neural model
        is unavailable.
        """
        # Try neural model first
        if self._reward_model_trained and self.reward_model_trainer:
            try:
                return self.reward_model_trainer.predict_reward(
                    service_ids, self.service_dict, request_data,
                )
            except Exception as e:
                print(f"Neural reward fallback: {e}")

        # Fallback: analytical
        if self.reward_calculator:
            services = [
                self.service_dict[sid]
                for sid in service_ids
                if sid in self.service_dict
            ]
            if not services:
                return 0.0
            from models.service import CompositionRequest as CR
            cr = CR(request_data.get('id', 'tmp'))
            cr.provided = request_data.get('provided', [])
            cr.resultant = request_data.get('resultant', '')
            cr.qos_constraints = QoS(request_data.get('qos_constraints', {}))
            result = self.reward_calculator.compute_reward(
                services, cr, service_ids,
            )
            return result['reward']

        return 0.0

    # ------------------------------------------------------------------
    # Phase 3: RL Fine-Tuning (GRPO / PPO)
    # ------------------------------------------------------------------

    def run_rl_training(self, training_examples, rl_config=None,
                        algorithm="GRPO", progress_callback=None):
        """
        Phase 3: Reinforcement Learning fine-tuning.

        Uses the reward model (Phase 2) to provide reward signals and
        optimises the policy model via GRPO or PPO.

        Prerequisites:
            - Knowledge-base training (train()) must be done first.
            - A reward signal must be available (analytical or neural).

        Args:
            training_examples: same format as train()
            rl_config: optional dict with RL hyper-parameters
            algorithm: "GRPO" (default, recommended) or "PPO"

        Returns:
            dict with RL training metrics
        """
        if not self._rl_available:
            missing = GRPOTrainer.missing_packages()
            raise ImportError(
                f"RL training requires: {', '.join(missing)}. "
                f"Install with: pip install {' '.join(missing)}"
            )

        rl_config = rl_config or {}
        algorithm = algorithm.upper()

        # Determine SFT adapter path for warm start
        sft_adapter_path = None
        if self._sft_trained and self.sft_trainer:
            candidate = os.path.join(
                self.sft_trainer.output_dir, "final_adapter",
            )
            if os.path.exists(candidate):
                sft_adapter_path = candidate

        # 1. Build RL prompts from training examples
        prompts = self._build_rl_prompts(training_examples)
        if not prompts:
            raise ValueError(
                "Could not build any RL prompts from the training data. "
                "Ensure training_examples contain 'best_solution' entries "
                "and services are loaded."
            )

        # 2. Initialise the RL trainer
        TrainerCls = GRPOTrainer if algorithm == "GRPO" else PPOTrainer
        self.rl_trainer = TrainerCls(
            config=rl_config,
            sft_adapter_path=sft_adapter_path,
        )

        # 3. Train using predict_reward as the reward function
        self.rl_metrics = self.rl_trainer.train(
            prompts,
            reward_fn=self.predict_reward,
            progress_callback=progress_callback,
        )
        self._rl_trained = True
        self._rl_algorithm = algorithm

        return {
            'rl_metrics': self.rl_metrics,
            'algorithm': algorithm,
            'num_prompts': len(prompts),
            'sft_warm_start': sft_adapter_path is not None,
        }

    def _build_rl_prompts(self, training_examples):
        """Convert training examples into RL prompt dicts.

        Each prompt contains the request data and a subset of candidate
        services so the RL policy can learn to select among them.
        """
        prompts = []
        for example in training_examples:
            request_data = example.get('request', {})
            best_solution = example.get('best_solution')
            if not best_solution:
                continue

            # Collect candidate services for this request
            resultant = request_data.get('resultant', '')
            provided = request_data.get('provided', [])
            candidate_ids = set()

            # Services that produce the target
            for s in self.services:
                if resultant in s.outputs:
                    candidate_ids.add(s.id)

            # Services that accept provided inputs
            for p in provided:
                for s in self._input_index.get(p, []):
                    candidate_ids.add(s.id)

            # Include best-solution services
            solution_ids = best_solution.get('service_ids',
                                             best_solution.get('workflow', []))
            for sid in solution_ids:
                candidate_ids.add(sid)

            # Build candidate dict
            candidates = {}
            for sid in list(candidate_ids)[:20]:  # cap at 20
                if sid in self.service_dict:
                    candidates[sid] = self.service_dict[sid]

            if not candidates:
                continue

            prompts.append({
                'request_data': request_data,
                'candidate_services': candidates,
            })

        return prompts

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------

    def compose(self, request, enable_reasoning=True,
                enable_adaptation=True):
        """
        Compose services using knowledge base + optional LLM reasoning.

        Strategy:
        1. Find candidate services via indexes
        2. Score them using knowledge base + QoS + annotations
        3. Try direct (single-service) composition first
        4. If no direct solution, build a multi-service chain
        5. Optionally adapt using historical composition data
        """
        start_time = time.time()
        result = CompositionResult()
        result.algorithm_used = "llm"

        try:
            # Step 1: find candidates
            candidates = self._find_candidates(request)
            if not candidates:
                result.success = False
                result.explanation = (
                    "No candidate services found that can contribute "
                    "to this composition."
                )
                result.computation_time = time.time() - start_time
                return result

            # Step 2: score candidates
            scored = self._score_candidates(candidates, request)

            # Step 3: try direct composition
            direct_solutions = [
                (s, sc) for s, sc in scored
                if (request.resultant in s.outputs
                    and s.has_required_inputs(request.provided))
            ]

            if direct_solutions:
                selected = self._select_best_direct(
                    request, direct_solutions, enable_reasoning
                )
                result.services = [selected]
                result.workflow = [selected.id]
                qos_checks = selected.qos.meets_constraints(
                    request.qos_constraints
                )
                result.utility_value = calculate_utility(
                    selected.qos, request.qos_constraints, qos_checks
                )
                result.qos_achieved = selected.qos
                result.success = True
                result.states_explored = len(candidates)
                result.explanation = self._generate_explanation(
                    request, result, scored, "direct"
                )
            else:
                # Step 4: build a multi-service chain
                chain = self._build_chain(request, scored)
                if chain:
                    result.services = chain['services']
                    result.workflow = chain['workflow']
                    result.utility_value = chain['utility']
                    result.qos_achieved = chain['qos']
                    result.success = True
                    result.states_explored = chain.get(
                        'explored', len(candidates)
                    )
                    result.explanation = self._generate_explanation(
                        request, result, scored, "chain"
                    )
                else:
                    result.success = False
                    result.explanation = (
                        "Could not build a valid service composition "
                        "for this request."
                    )

            # Step 5: try adaptation from history
            if (enable_adaptation and result.success
                    and self.composition_history):
                result = self._try_adapt(request, result)

        except Exception as e:
            result.success = False
            result.explanation = f"LLM composition error: {str(e)}"
            import traceback
            traceback.print_exc()

        result.computation_time = time.time() - start_time
        return result

    # ------------------------------------------------------------------
    # Candidate finding & scoring
    # ------------------------------------------------------------------

    def _find_candidates(self, request):
        """Find candidate services using forward+backward reachability
        (same strategy as classic composer for fair comparison)."""

        # --- Forward reachability: what params can we produce? ---
        reachable_params = set(request.provided)
        forward_ids = set()
        frontier = set(request.provided)

        while frontier:
            next_frontier = set()
            for param in frontier:
                for s in self._input_index.get(param, []):
                    if s.id in forward_ids:
                        continue
                    if self._service_input_sets.get(s.id, frozenset()) <= reachable_params:
                        forward_ids.add(s.id)
                        new_out = set(s.outputs) - reachable_params
                        reachable_params |= new_out
                        next_frontier |= new_out
            frontier = next_frontier

        if request.resultant not in reachable_params:
            return []  # goal unreachable

        # --- Backward reachability: what services lead to the goal? ---
        needed = {request.resultant}
        backward_ids = set()
        frontier = {request.resultant}

        while frontier:
            next_frontier = set()
            for param in frontier:
                for s in self._output_index.get(param, []):
                    if s.id in backward_ids:
                        continue
                    backward_ids.add(s.id)
                    new_inputs = set(s.inputs) - needed - set(request.provided)
                    needed |= new_inputs
                    next_frontier |= new_inputs
            frontier = next_frontier

        # Intersection = services both reachable and useful
        relevant_ids = forward_ids & backward_ids
        if len(relevant_ids) < 3:
            relevant_ids = forward_ids | backward_ids

        return [
            self.service_dict[sid]
            for sid in relevant_ids
            if sid in self.service_dict
        ]

    def _score_candidates(self, candidates, request):
        """Score and rank candidates using QoS, knowledge base, and
        annotations.  Bonuses are capped so that QoS utility remains
        the dominant factor (fair comparison with classic approach)."""
        scored = []

        for service in candidates:
            qos_checks = service.qos.meets_constraints(
                request.qos_constraints
            )
            utility = calculate_utility(
                service.qos, request.qos_constraints, qos_checks
            )

            # Knowledge base bonus (small — should not dominate utility)
            kb_bonus = 0.0
            ranking = self.knowledge_base['service_rankings'].get(service.id)
            if ranking:
                kb_bonus = min(ranking['score'] * 0.5, 1.0)

            # Annotation-based trust bonus (small)
            annotation_bonus = 0.0
            if hasattr(service, 'annotations') and service.annotations:
                sn = service.annotations.social_node
                annotation_bonus = (
                    sn.trust_degree.value * 0.3
                    + sn.reputation.value * 0.3
                    + sn.cooperativeness.value * 0.15
                )

            total_score = utility + kb_bonus + annotation_bonus
            scored.append((service, total_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    # ------------------------------------------------------------------
    # Selection strategies
    # ------------------------------------------------------------------

    def _select_best_direct(self, request, direct_solutions,
                            enable_reasoning):
        """Select the best service among direct solutions.
        Uses LLM reasoning when available and beneficial."""

        if len(direct_solutions) == 1 or not enable_reasoning:
            return direct_solutions[0][0]

        top = direct_solutions[:5]

        # ── Try RL-tuned model first (Phase 3 QSRT — best model) ──
        if self._rl_trained and self.rl_trainer:
            try:
                instruction = self.sft_dataset_builder._format_instruction(
                    request.to_dict(),
                    {s.id: s for s, _ in top},
                ) if self.sft_dataset_builder else str(request.to_dict())
                raw = self.rl_trainer.generate(instruction)
                selected_id = self._extract_service_id_from_json(
                    raw, [s.id for s, _ in top]
                )
                if selected_id and selected_id in self.service_dict:
                    return self.service_dict[selected_id]
            except Exception as e:
                print(f"RL selection fallback: {e}")

        # ── Try SFT fine-tuned model (Phase 1 QSRT) ──
        if self._sft_trained and self.sft_trainer and self.sft_dataset_builder:
            try:
                instruction = self.sft_dataset_builder._format_instruction(
                    request.to_dict(),
                    {s.id: s for s, _ in top},
                )
                raw = self.sft_trainer.generate(instruction)
                selected_id = self._extract_service_id_from_json(
                    raw, [s.id for s, _ in top]
                )
                if selected_id and selected_id in self.service_dict:
                    return self.service_dict[selected_id]
            except Exception as e:
                print(f"SFT selection fallback: {e}")

        # ── Fallback: Ollama few-shot prompting ──
        prompt = self._build_selection_prompt(request, top)
        try:
            response = self._call_ollama(prompt)
            selected_id = self._extract_service_id_from_response(
                response, [s.id for s, _ in top]
            )
            if selected_id and selected_id in self.service_dict:
                return self.service_dict[selected_id]
        except Exception as e:
            print(f"Ollama selection fallback (direct): {e}")

        # Fallback: highest utility (not composite score)
        best_direct = max(direct_solutions, key=lambda x: calculate_utility(
            x[0].qos, request.qos_constraints,
            x[0].qos.meets_constraints(request.qos_constraints)
        ))
        return best_direct[0]

    def _build_chain(self, request, scored):
        """Build a multi-service chain using beam search — explores
        multiple paths in parallel, comparable to classic's Dijkstra."""
        beam_width = 200
        max_depth = 30
        max_states = 500000

        # Beam state: (available_params, path_ids, path_services)
        initial = (frozenset(request.provided), [], [])
        # Priority queue: (neg_utility, counter, state)
        beam = [(0.0, 0, initial)]
        counter = 1

        best_solution = None
        best_utility = -float('inf')
        best_seen = {}  # frozenset(params) -> best running utility
        states_explored = 0

        for _depth in range(max_depth):
            if not beam or states_explored >= max_states:
                break

            next_beam = []

            for neg_util, _, (available, path_ids, path_services) in beam:
                current_utility = -neg_util

                # Goal check
                if request.resultant in available and path_services:
                    # Use running average utility (same as classic Dijkstra)
                    # for fair comparison
                    if current_utility > best_utility:
                        best_utility = current_utility
                        best_solution = {
                            'services': list(path_services),
                            'workflow': list(path_ids),
                            'utility': current_utility,
                            'qos': aggregate_qos(path_services),
                            'explored': states_explored,
                        }
                    continue  # don't expand completed paths

                # Expand with each feasible service
                used = set(path_ids)
                for service, _base_score in scored:
                    if service.id in used:
                        continue
                    svc_inputs = self._service_input_sets.get(
                        service.id, frozenset()
                    )
                    if not (svc_inputs <= available):
                        continue

                    states_explored += 1
                    if states_explored >= max_states:
                        break

                    new_available = available | frozenset(service.outputs)
                    new_path_ids = path_ids + [service.id]
                    new_path_services = path_services + [service]

                    # Running average utility (same as classic Dijkstra)
                    svc_checks = service.qos.meets_constraints(
                        request.qos_constraints
                    )
                    svc_utility = calculate_utility(
                        service.qos, request.qos_constraints, svc_checks
                    )
                    if path_services:
                        new_utility = (
                            current_utility * len(path_services)
                            + svc_utility
                        ) / (len(path_services) + 1)
                    else:
                        new_utility = svc_utility

                    # Prune dominated states
                    params_key = new_available
                    if (params_key in best_seen
                            and best_seen[params_key] >= new_utility):
                        continue
                    best_seen[params_key] = new_utility

                    # Use pure utility for beam priority (no artificial bonuses)
                    priority = -new_utility
                    counter += 1
                    next_beam.append((
                        priority, counter,
                        (new_available, new_path_ids, new_path_services),
                    ))

            # Keep top beam_width states
            beam = heapq.nsmallest(beam_width, next_beam)

        return best_solution

    def _try_adapt(self, request, result):
        """Try to improve the result using historical successes."""
        previous = [
            h for h in self.composition_history
            if h.get('request_id') == request.id and h.get('success')
        ]
        if not previous:
            return result

        best_prev = max(previous, key=lambda h: h.get('utility', 0))
        if best_prev.get('utility', 0) <= result.utility_value:
            return result

        prev_workflow = best_prev.get('result', {}).get('workflow', [])
        if not all(sid in self.service_dict for sid in prev_workflow):
            return result

        # Verify the previous workflow is still valid
        services = [self.service_dict[sid] for sid in prev_workflow]
        avail = set(request.provided)
        valid = True
        for svc in services:
            if not svc.has_required_inputs(avail):
                valid = False
                break
            avail.update(svc.outputs)

        if not valid or request.resultant not in avail:
            return result

        chain_qos = aggregate_qos(services)
        qos_checks = chain_qos.meets_constraints(request.qos_constraints)
        utility = calculate_utility(
            chain_qos, request.qos_constraints, qos_checks
        )

        if utility > result.utility_value:
            result.services = services
            result.workflow = prev_workflow
            result.utility_value = utility
            result.qos_achieved = chain_qos
            result.explanation += (
                "\n[Adapted from previous successful composition]"
            )

        return result

    # ------------------------------------------------------------------
    # LLM interaction
    # ------------------------------------------------------------------

    def _build_selection_prompt(self, request, candidates):
        """Build an Ollama prompt with few-shot examples."""
        prompt = (
            "You are an expert web service composition engine. "
            "Select the single BEST service for the request below.\n\n"
        )

        # Few-shot examples from training patterns
        matching_patterns = [
            p for p in self.knowledge_base['patterns']
            if p.get('resultant') == request.resultant
        ][:3]

        if matching_patterns:
            prompt += "=== LEARNED EXAMPLES ===\n"
            for i, pat in enumerate(matching_patterns, 1):
                ids = ', '.join(pat.get('service_ids', []))
                prompt += (
                    f"Example {i}: target={pat.get('resultant')}, "
                    f"selected=[{ids}], utility={pat.get('utility', 0):.2f}\n"
                )
            prompt += "\n"

        prompt += "=== CURRENT REQUEST ===\n"
        prompt += f"Target parameter: {request.resultant}\n"
        prompt += (
            f"Provided parameters: {len(request.provided)} "
            f"({', '.join(request.provided[:5])}"
            f"{'...' if len(request.provided) > 5 else ''})\n"
        )
        prompt += (
            f"QoS constraints: RT<={request.qos_constraints.response_time}, "
            f"Rel>={request.qos_constraints.reliability}%, "
            f"Avl>={request.qos_constraints.availability}%\n\n"
        )

        prompt += "=== CANDIDATES (ranked by score) ===\n"
        for svc, score in candidates:
            prompt += (
                f"- {svc.id}: "
                f"Rel={svc.qos.reliability:.1f}%, "
                f"RT={svc.qos.response_time:.0f}ms, "
                f"Avl={svc.qos.availability:.1f}%, "
                f"score={score:.1f}\n"
            )

        prompt += (
            "\nRespond with ONLY the service ID of the best candidate. "
            "Nothing else."
        )
        return prompt

    def _call_ollama(self, prompt):
        """Call the Ollama API."""
        try:
            resp = http_requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "top_p": 0.9,
                        "num_predict": 200,
                    },
                },
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.json()['response']
            raise Exception(f"Ollama API error: {resp.status_code}")
        except http_requests.exceptions.ConnectionError:
            raise Exception("Cannot connect to Ollama. Is it running?")

    def _extract_service_id_from_response(self, response, valid_ids):
        """Extract a valid service ID from LLM text output."""
        text = response.strip()
        # Direct match
        if text in valid_ids:
            return text
        # Search within response
        for sid in valid_ids:
            if sid in text:
                return sid
        return None

    def _extract_service_id_from_json(self, response, valid_ids):
        """Extract a valid service ID from the SFT model's JSON output."""
        try:
            data = json.loads(response)
            # The SFT model is trained to produce {"selected": [...]}
            selected = data.get('selected', [])
            if isinstance(selected, list):
                for sid in selected:
                    if sid in valid_ids:
                        return sid
            # Also check 'workflow'
            workflow = data.get('workflow', [])
            if isinstance(workflow, list):
                for sid in workflow:
                    if sid in valid_ids:
                        return sid
        except (json.JSONDecodeError, AttributeError):
            pass
        # Fallback to text matching
        return self._extract_service_id_from_response(response, valid_ids)

    # ------------------------------------------------------------------
    # Explanation
    # ------------------------------------------------------------------

    def _generate_explanation(self, request, result, scored, strategy):
        """Generate a human-readable explanation."""
        lines = []

        if strategy == "direct":
            lines.append("LLM Composition: Direct service selection")
            lines.append(f"Selected: {result.workflow[0]}")
        else:
            n = len(result.workflow)
            lines.append(
                f"LLM Composition: Multi-service chain ({n} services)"
            )
            lines.append(f"Path: {' → '.join(result.workflow)}")

        lines.append(f"Utility Score: {result.utility_value:.3f}")
        lines.append(f"Candidates Evaluated: {len(scored)}")

        # Indicate which QSRT phases are active
        phases = []
        if self._sft_trained:
            phases.append("Phase 1 (SFT LoRA)")
        if self._reward_model_trained:
            phases.append("Phase 2 (Reward Model)")
        if self._rl_trained:
            phases.append(f"Phase 3 (RL {self._rl_algorithm or 'GRPO'})")
        if phases:
            lines.append(f"QSRT Active: {' + '.join(phases)}")
            if self._rl_trained:
                lines.append(f"Inference: RL-optimised model ({self._rl_algorithm})")
            else:
                lines.append("Inference: QSRT fine-tuned model")
        else:
            lines.append("Inference: Ollama few-shot prompting")

        # Show reward score if reward model is available
        if self._reward_model_trained and self.reward_model_trainer:
            try:
                reward_score = self.predict_reward(
                    result.workflow,
                    {
                        'resultant': request.resultant,
                        'provided': request.provided,
                        'qos_constraints': request.qos_constraints.to_dict(),
                    },
                )
                lines.append(f"Reward Score (QSRT): {reward_score:.4f}")
            except Exception:
                pass

        matched = sum(
            1 for p in self.knowledge_base['patterns']
            if p.get('resultant') == request.resultant
        )
        if matched:
            lines.append(f"Training patterns matched: {matched}")

        if self.composition_history:
            lines.append(
                f"Historical compositions: {len(self.composition_history)}"
            )

        return '\n'.join(lines)

    # ------------------------------------------------------------------
    # Continuous learning
    # ------------------------------------------------------------------

    def learn_from_composition(self, record):
        """Update knowledge base from a composition result."""
        self.composition_history.append(record)

        if record.get('success'):
            self.success_patterns.append({
                'request': record.get('request'),
                'result': record.get('result'),
                'utility': record.get('utility'),
            })

            # Update service rankings incrementally
            workflow = record.get('result', {}).get('workflow', [])
            utility = record.get('utility', 0)
            for sid in workflow:
                if sid not in self.knowledge_base['service_rankings']:
                    self.knowledge_base['service_rankings'][sid] = {
                        'usage_count': 0,
                        'avg_utility': 0.0,
                        'score': 0.0,
                    }
                r = self.knowledge_base['service_rankings'][sid]
                r['usage_count'] += 1
                n = r['usage_count']
                r['avg_utility'] = (
                    (r['avg_utility'] * (n - 1) + utility) / n
                )
                r['score'] = r['usage_count'] * 0.3 + r['avg_utility'] * 0.7
        else:
            self.error_patterns.append({
                'request': record.get('request'),
                'error': record.get('result', {}).get('explanation'),
            })

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    def chat(self, message):
        """Chat with the LLM about composition decisions."""
        n_services = len(self.services)
        n_patterns = len(self.knowledge_base['patterns'])
        n_history = len(self.composition_history)
        n_success = len(self.success_patterns)
        sft_status = "trained ✓" if self._sft_trained else "not trained"
        reward_status = "trained ✓" if self._reward_model_trained else "not trained"
        rl_status = f"trained ✓ ({self._rl_algorithm})" if self._rl_trained else "not trained"

        context = (
            "You are an AI assistant for a web service composition system.\n"
            f"Current state:\n"
            f"- Total services loaded: {n_services}\n"
            f"- Training patterns learned: {n_patterns}\n"
            f"- SFT LoRA model (Phase 1): {sft_status}\n"
            f"- Reward model (Phase 2): {reward_status}\n"
            f"- RL fine-tuned model (Phase 3): {rl_status}\n"
            f"- Compositions performed: {n_history}\n"
            f"- Successful compositions: {n_success}\n\n"
            f"User question: {message}\n\n"
            "Answer concisely and helpfully."
        )

        # Try RL model first (best quality), then SFT, then Ollama
        if self._rl_trained and self.rl_trainer:
            try:
                return self.rl_trainer.generate(context)
            except Exception:
                pass

        if self._sft_trained and self.sft_trainer:
            try:
                return self.sft_trainer.generate(context)
            except Exception:
                pass  # fallback to Ollama

        try:
            return self._call_ollama(context)
        except Exception as e:
            return (
                f"LLM unavailable: {str(e)}. "
                f"The system has {n_services} services loaded "
                f"with {n_patterns} learned patterns. "
                f"SFT model: {sft_status}. "
                f"RL model: {rl_status}."
            )
