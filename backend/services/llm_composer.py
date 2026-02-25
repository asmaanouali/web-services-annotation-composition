"""
Production-grade LLM-based Web Service Composer.

Uses Ollama for intelligent service selection with:
- Few-shot learning from training data
- Knowledge base of composition patterns
- Continuous learning from composition history
- Fallback to knowledge-based selection when LLM is unavailable
"""

import time
import json
import requests as http_requests
from collections import defaultdict
from models.service import CompositionResult, QoS
from utils.qos_calculator import calculate_utility, aggregate_qos


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
                 ollama_url="http://localhost:11434"):
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

        # Continuous learning state
        self.composition_history = []
        self.success_patterns = []
        self.error_patterns = []

        if training_examples:
            self.train(training_examples)

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
        Process training examples to build a knowledge base.

        Extracts:
        - Composition patterns (request -> service mapping)
        - Service quality rankings (usage frequency + utility)
        - I/O chain knowledge (parameter -> known service chains)

        Returns training quality metrics.
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

    def get_training_metrics(self):
        """Return training quality metrics."""
        return self.training_metrics

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
        """Find candidate services using indexes (not brute force)."""
        candidate_ids = set()

        # Services that can accept provided parameters
        for param in request.provided:
            for s in self._input_index.get(param, []):
                candidate_ids.add(s.id)

        # Services that produce the target parameter
        for s in self._output_index.get(request.resultant, []):
            candidate_ids.add(s.id)

        # Second-hop chaining: outputs of current candidates -> inputs of
        # other services that may eventually produce the target
        chain_ids = set()
        for sid in list(candidate_ids):
            s = self.service_dict.get(sid)
            if not s:
                continue
            for out in s.outputs:
                for s2 in self._input_index.get(out, []):
                    chain_ids.add(s2.id)
        candidate_ids |= chain_ids

        return [
            self.service_dict[sid]
            for sid in candidate_ids
            if sid in self.service_dict
        ]

    def _score_candidates(self, candidates, request):
        """Score and rank candidates using QoS, knowledge base, and
        annotations."""
        scored = []

        for service in candidates:
            qos_checks = service.qos.meets_constraints(
                request.qos_constraints
            )
            utility = calculate_utility(
                service.qos, request.qos_constraints, qos_checks
            )

            # Knowledge base bonus (from training patterns)
            kb_bonus = 0.0
            ranking = self.knowledge_base['service_rankings'].get(service.id)
            if ranking:
                kb_bonus = ranking['score'] * 10

            # Direct producer bonus
            direct_bonus = 50.0 if request.resultant in service.outputs else 0.0

            # Input satisfaction bonus
            input_match = sum(
                1 for inp in service.inputs if inp in request.provided
            )
            input_ratio = input_match / max(len(service.inputs), 1)
            input_bonus = input_ratio * 20.0

            # Annotation-based trust/reputation bonus
            annotation_bonus = 0.0
            if hasattr(service, 'annotations') and service.annotations:
                sn = service.annotations.social_node
                annotation_bonus = (
                    sn.trust_degree.value * 10
                    + sn.reputation.value * 10
                    + sn.cooperativeness.value * 5
                )

            total_score = (
                utility + kb_bonus + direct_bonus
                + input_bonus + annotation_bonus
            )
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

        # Try LLM-guided selection for top candidates
        top = direct_solutions[:5]
        prompt = self._build_selection_prompt(request, top)

        try:
            response = self._call_ollama(prompt)
            selected_id = self._extract_service_id_from_response(
                response, [s.id for s, _ in top]
            )
            if selected_id and selected_id in self.service_dict:
                return self.service_dict[selected_id]
        except Exception as e:
            print(f"LLM selection fallback (direct): {e}")

        # Fallback: highest scored
        return direct_solutions[0][0]

    def _build_chain(self, request, scored):
        """Build a multi-service chain using greedy knowledge-guided
        search."""
        available_params = set(request.provided)
        path = []
        path_services = []
        used = set()
        max_depth = 30  # allow long chains

        for _ in range(max_depth):
            if request.resultant in available_params:
                break

            best_service = None
            best_score = -1.0

            for service, base_score in scored:
                if service.id in used:
                    continue
                if not (self._service_input_sets.get(service.id, frozenset())
                        <= available_params):
                    continue

                # Goal proximity bonus
                goal_bonus = (
                    100.0 if request.resultant in service.outputs else 0.0
                )

                # Does this service enable reaching the goal?
                chain_bonus = 0.0
                for out in service.outputs:
                    for s2 in self._output_index.get(
                            request.resultant, []):
                        if out in s2.inputs:
                            chain_bonus += 30.0
                            break  # one bonus per output

                adjusted = base_score + goal_bonus + chain_bonus
                if adjusted > best_score:
                    best_score = adjusted
                    best_service = service

            if not best_service:
                break

            path.append(best_service.id)
            path_services.append(best_service)
            used.add(best_service.id)
            available_params.update(best_service.outputs)

        if request.resultant in available_params and path_services:
            chain_qos = aggregate_qos(path_services)
            qos_checks = chain_qos.meets_constraints(
                request.qos_constraints
            )
            chain_utility = calculate_utility(
                chain_qos, request.qos_constraints, qos_checks
            )
            return {
                'services': path_services,
                'workflow': path,
                'utility': chain_utility,
                'qos': chain_qos,
                'explored': len(scored),
            }

        return None

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

        context = (
            "You are an AI assistant for a web service composition system.\n"
            f"Current state:\n"
            f"- Total services loaded: {n_services}\n"
            f"- Training patterns learned: {n_patterns}\n"
            f"- Compositions performed: {n_history}\n"
            f"- Successful compositions: {n_success}\n\n"
            f"User question: {message}\n\n"
            "Answer concisely and helpfully."
        )

        try:
            return self._call_ollama(context)
        except Exception as e:
            return (
                f"LLM unavailable: {str(e)}. "
                f"The system has {n_services} services loaded "
                f"with {n_patterns} learned patterns."
            )
