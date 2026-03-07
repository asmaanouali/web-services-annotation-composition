"""
Tests for LLMComposer — knowledge-based composition logic.

Tests the core composition pipeline without requiring Ollama or GPU:
candidate finding, scoring, chain building, knowledge base training,
prompt construction, and continuous learning.
"""

import unittest
from models.service import WebService, QoS, CompositionRequest
from models.annotation import ServiceAnnotation, SNProperty
from services.llm_composer import LLMComposer


# ── Helpers ──────────────────────────────────────────────────────

def _svc(sid, inputs, outputs, qos_overrides=None):
    """Create a WebService with given I/O and QoS."""
    base = {
        "ResponseTime": 50, "Availability": 90, "Throughput": 80,
        "Successability": 85, "Reliability": 90, "Compliance": 75,
        "BestPractices": 60, "Latency": 30, "Documentation": 50,
    }
    if qos_overrides:
        base.update(qos_overrides)
    s = WebService(sid)
    s.inputs = list(inputs)
    s.outputs = list(outputs)
    s.qos = QoS(base)
    return s


def _req(rid, provided, resultant):
    """Create a CompositionRequest."""
    req = CompositionRequest(rid)
    req.provided = list(provided)
    req.resultant = resultant
    return req


def _build_services():
    """Small service graph: a→b→c→d, with alternative paths."""
    return [
        _svc("S1", ["a"], ["b"]),
        _svc("S2", ["b"], ["c"]),
        _svc("S3", ["c"], ["d"]),
        _svc("S4", ["a"], ["c"]),       # shortcut: skips S1+S2
        _svc("S5", ["a", "b"], ["d"]),  # direct if both available
    ]


def _annotate_services(services):
    """Add minimal annotations to services."""
    for s in services:
        ann = ServiceAnnotation(s.id)
        ann.social_node.trust_degree = SNProperty("trust_degree", 0.8)
        ann.social_node.reputation = SNProperty("reputation", 0.7)
        ann.social_node.cooperativeness = SNProperty("cooperativeness", 0.6)
        s.annotations = ann
    return services


# ── Index Building ───────────────────────────────────────────────

class TestLLMComposerInit(unittest.TestCase):
    """Test composer construction and index building."""

    def test_indexes_built(self):
        services = _build_services()
        composer = LLMComposer(services)
        # S1 produces 'b' → should be in output_index['b']
        out_b = [s.id for s in composer._output_index["b"]]
        self.assertIn("S1", out_b)
        # S2 consumes 'b' → should be in input_index['b']
        in_b = [s.id for s in composer._input_index["b"]]
        self.assertIn("S2", in_b)

    def test_service_dict(self):
        services = _build_services()
        composer = LLMComposer(services)
        self.assertEqual(len(composer.service_dict), 5)
        self.assertIn("S3", composer.service_dict)

    def test_empty_services(self):
        composer = LLMComposer([])
        self.assertEqual(len(composer.services), 0)
        self.assertEqual(len(composer._output_index), 0)


# ── Candidate Finding ────────────────────────────────────────────

class TestFindCandidates(unittest.TestCase):
    """Test _find_candidates method."""

    def setUp(self):
        self.services = _build_services()
        self.composer = LLMComposer(self.services)

    def test_finds_direct_producers(self):
        """Services producing the target output should be candidates."""
        req = _req("R1", ["a"], "d")
        candidates = self.composer._find_candidates(req)
        cids = {c.id for c in candidates}
        # S3 and S5 produce 'd'
        self.assertIn("S3", cids)
        self.assertIn("S5", cids)

    def test_finds_input_consumers(self):
        """Services consuming provided inputs should be candidates."""
        req = _req("R1", ["a"], "d")
        candidates = self.composer._find_candidates(req)
        cids = {c.id for c in candidates}
        # S1, S4, S5 all consume 'a'
        self.assertIn("S1", cids)
        self.assertIn("S4", cids)

    def test_includes_chain_services(self):
        """Second-hop chaining should bring in intermediate services."""
        req = _req("R1", ["a"], "d")
        candidates = self.composer._find_candidates(req)
        cids = {c.id for c in candidates}
        # S2 should be found through chaining (S1 produces b → S2 consumes b)
        self.assertIn("S2", cids)

    def test_no_candidates_for_unknown_params(self):
        """No candidates when parameters don't match any service."""
        req = _req("R-miss", ["zzz"], "www")
        candidates = self.composer._find_candidates(req)
        self.assertEqual(len(candidates), 0)


# ── Candidate Scoring ────────────────────────────────────────────

class TestScoreCandidates(unittest.TestCase):
    """Test _score_candidates method."""

    def setUp(self):
        self.services = _build_services()
        self.composer = LLMComposer(self.services)

    def test_direct_producer_scored_highest(self):
        """A service that directly produces the target should score highest."""
        req = _req("R1", ["a"], "d")
        candidates = self.composer._find_candidates(req)
        scored = self.composer._score_candidates(candidates, req)
        # S3 or S5 produce 'd' directly → should be near top
        top_ids = [s.id for s, _ in scored[:3]]
        direct_producers = {"S3", "S5"}
        self.assertTrue(
            direct_producers & set(top_ids),
            f"Expected a direct producer in top 3, got {top_ids}"
        )

    def test_scores_are_numeric(self):
        req = _req("R1", ["a"], "d")
        candidates = self.composer._find_candidates(req)
        scored = self.composer._score_candidates(candidates, req)
        for _, score in scored:
            self.assertIsInstance(score, (int, float))

    def test_sorted_descending(self):
        req = _req("R1", ["a"], "d")
        candidates = self.composer._find_candidates(req)
        scored = self.composer._score_candidates(candidates, req)
        scores = [s for _, s in scored]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_annotation_bonus(self):
        """Annotated services should get higher scores."""
        services = _build_services()
        composer_no_ann = LLMComposer(services)
        req = _req("R1", ["a"], "d")
        candidates_no = composer_no_ann._find_candidates(req)
        scored_no = composer_no_ann._score_candidates(candidates_no, req)

        ann_services = _annotate_services(_build_services())
        composer_ann = LLMComposer(ann_services)
        candidates_ann = composer_ann._find_candidates(req)
        scored_ann = composer_ann._score_candidates(candidates_ann, req)

        # Find same service in both and check annotation bonus
        no_dict = {s.id: sc for s, sc in scored_no}
        ann_dict = {s.id: sc for s, sc in scored_ann}
        for sid in no_dict:
            if sid in ann_dict:
                self.assertGreater(
                    ann_dict[sid], no_dict[sid],
                    f"Service {sid} should score higher with annotations"
                )


# ── Chain Building ───────────────────────────────────────────────

class TestBuildChain(unittest.TestCase):
    """Test _build_chain method."""

    def setUp(self):
        self.services = _build_services()
        self.composer = LLMComposer(self.services)

    def test_simple_chain(self):
        """Should find a→b→c→d chain."""
        req = _req("R1", ["a"], "d")
        candidates = self.composer._find_candidates(req)
        scored = self.composer._score_candidates(candidates, req)
        result = self.composer._build_chain(req, scored)
        self.assertIsNotNone(result, "Should find a valid chain a→...→d")
        self.assertIn("d", {
            o for s in result["services"] for o in s.outputs
        })

    def test_chain_has_required_fields(self):
        req = _req("R1", ["a"], "d")
        candidates = self.composer._find_candidates(req)
        scored = self.composer._score_candidates(candidates, req)
        result = self.composer._build_chain(req, scored)
        self.assertIsNotNone(result)
        self.assertIn("services", result)
        self.assertIn("workflow", result)
        self.assertIn("utility", result)
        self.assertIn("qos", result)

    def test_chain_utility_positive(self):
        req = _req("R1", ["a"], "d")
        candidates = self.composer._find_candidates(req)
        scored = self.composer._score_candidates(candidates, req)
        result = self.composer._build_chain(req, scored)
        self.assertIsNotNone(result)
        self.assertGreater(result["utility"], 0)

    def test_impossible_chain_returns_none(self):
        """No chain possible if target is unreachable."""
        req = _req("R-miss", ["a"], "zzz")
        candidates = self.composer._find_candidates(req)
        scored = self.composer._score_candidates(candidates, req)
        result = self.composer._build_chain(req, scored)
        self.assertIsNone(result)

    def test_direct_path(self):
        """S5 takes [a,b] → d. With provided=[a,b], it should be direct."""
        req = _req("R-direct", ["a", "b"], "d")
        candidates = self.composer._find_candidates(req)
        scored = self.composer._score_candidates(candidates, req)
        result = self.composer._build_chain(req, scored)
        self.assertIsNotNone(result)
        # Should use S5 (direct) or S3 (c→d after S2: b→c)
        self.assertGreater(len(result["workflow"]), 0)


# ── Knowledge Base Training ──────────────────────────────────────

class TestTraining(unittest.TestCase):
    """Test knowledge base training."""

    def setUp(self):
        self.services = _build_services()
        self.composer = LLMComposer(self.services)

    def _make_examples(self):
        return [
            {
                "request": {
                    "provided": ["a"],
                    "resultant": "d",
                },
                "best_solution": {
                    "service_ids": ["S1", "S2", "S3"],
                    "utility": 0.85,
                },
            },
            {
                "request": {
                    "provided": ["a"],
                    "resultant": "c",
                },
                "best_solution": {
                    "service_ids": ["S4"],
                    "utility": 0.92,
                },
            },
            {
                "request": {
                    "provided": ["a"],
                    "resultant": "x",
                },
                "best_solution": None,  # no solution
            },
        ]

    def test_training_returns_metrics(self):
        metrics = self.composer.train(self._make_examples())
        self.assertEqual(metrics["total_examples"], 3)
        self.assertEqual(metrics["examples_with_solutions"], 2)
        self.assertGreater(metrics["avg_solution_utility"], 0)

    def test_knowledge_base_populated(self):
        self.composer.train(self._make_examples())
        self.assertEqual(len(self.composer.knowledge_base["patterns"]), 2)
        self.assertGreater(
            len(self.composer.knowledge_base["service_rankings"]), 0
        )

    def test_service_rankings_correct(self):
        self.composer.train(self._make_examples())
        rankings = self.composer.knowledge_base["service_rankings"]
        # S1 appears in 1 example
        self.assertIn("S1", rankings)
        self.assertEqual(rankings["S1"]["usage_count"], 1)
        # S4 appears in 1 example
        self.assertIn("S4", rankings)

    def test_io_chains_built(self):
        self.composer.train(self._make_examples())
        chains = self.composer.knowledge_base["io_chains"]
        targets = [c["target"] for c in chains]
        self.assertIn("d", targets)
        self.assertIn("c", targets)

    def test_coverage_rate(self):
        metrics = self.composer.train(self._make_examples())
        # 2 out of 3 have solutions
        self.assertAlmostEqual(
            metrics["coverage_rate"], 2 / 3 * 100, places=1
        )

    def test_training_improves_scoring(self):
        """After training, known-good services should score higher."""
        req = _req("R1", ["a"], "d")
        candidates = self.composer._find_candidates(req)

        # Score before training
        scored_before = self.composer._score_candidates(candidates, req)
        before_dict = {s.id: sc for s, sc in scored_before}

        # Train and score again
        self.composer.train(self._make_examples())
        scored_after = self.composer._score_candidates(candidates, req)
        after_dict = {s.id: sc for s, sc in scored_after}

        # S1 is in training data → should have higher score after training
        if "S1" in before_dict and "S1" in after_dict:
            self.assertGreater(after_dict["S1"], before_dict["S1"])


# ── Prompt Building ──────────────────────────────────────────────

class TestBuildSelectionPrompt(unittest.TestCase):
    """Test that prompt construction produces valid strings."""

    def setUp(self):
        self.services = _build_services()
        self.composer = LLMComposer(self.services)

    def test_prompt_contains_request_info(self):
        req = _req("R1", ["a"], "d")
        candidates = self.composer._find_candidates(req)
        scored = self.composer._score_candidates(candidates, req)
        prompt = self.composer._build_selection_prompt(req, scored)
        self.assertIsInstance(prompt, str)
        self.assertIn("d", prompt)  # target output
        self.assertGreater(len(prompt), 50)

    def test_prompt_lists_candidates(self):
        req = _req("R1", ["a"], "d")
        candidates = self.composer._find_candidates(req)
        scored = self.composer._score_candidates(candidates, req)
        prompt = self.composer._build_selection_prompt(req, scored)
        # At least one service ID should appear
        found = any(s.id in prompt for s, _ in scored)
        self.assertTrue(found, "Prompt should mention candidate service IDs")


# ── Composition End-to-End (knowledge-based, no LLM) ────────────

class TestComposeEndToEnd(unittest.TestCase):
    """Test the full compose method without LLM (knowledge-based fallback)."""

    def setUp(self):
        self.services = _build_services()
        self.composer = LLMComposer(
            self.services,
            ollama_url="http://nonexistent:11434",  # force fallback
        )

    def test_compose_simple_request(self):
        req = _req("R1", ["a"], "d")
        result = self.composer.compose(req, enable_reasoning=False)
        self.assertTrue(result.success, f"Composition should succeed: {result.explanation}")
        self.assertGreater(result.utility_value, 0)
        self.assertGreater(len(result.services), 0)

    def test_compose_impossible_request(self):
        req = _req("R-miss", ["a"], "zzz")
        result = self.composer.compose(req, enable_reasoning=False)
        self.assertFalse(result.success)

    def test_compose_returns_workflow(self):
        req = _req("R1", ["a"], "d")
        result = self.composer.compose(req, enable_reasoning=False)
        if result.success:
            self.assertIsInstance(result.workflow, list)
            self.assertGreater(len(result.workflow), 0)

    def test_compose_with_training(self):
        """Trained composer should still compose successfully."""
        examples = [
            {
                "request": {"provided": ["a"], "resultant": "d"},
                "best_solution": {"service_ids": ["S1", "S2", "S3"], "utility": 0.85},
            },
        ]
        self.composer.train(examples)
        req = _req("R1", ["a"], "d")
        result = self.composer.compose(req, enable_reasoning=False)
        self.assertTrue(result.success)

    def test_compose_returns_computation_time(self):
        req = _req("R1", ["a"], "d")
        result = self.composer.compose(req)
        self.assertGreaterEqual(result.computation_time, 0)


# ── Continuous Learning ──────────────────────────────────────────

class TestContinuousLearning(unittest.TestCase):
    """Test learn_from_composition."""

    def setUp(self):
        self.services = _build_services()
        self.composer = LLMComposer(self.services)

    def test_learn_from_success(self):
        record = {
            "request_id": "R1",
            "success": True,
            "utility": 0.85,
            "services": ["S1", "S2", "S3"],
            "algorithm": "llm",
        }
        self.composer.learn_from_composition(record)
        self.assertEqual(len(self.composer.composition_history), 1)
        self.assertEqual(len(self.composer.success_patterns), 1)

    def test_learn_from_failure(self):
        record = {
            "request_id": "R1",
            "success": False,
            "utility": 0.0,
            "services": [],
            "algorithm": "llm",
        }
        self.composer.learn_from_composition(record)
        self.assertEqual(len(self.composer.composition_history), 1)
        self.assertEqual(len(self.composer.error_patterns), 1)

    def test_multiple_learns_accumulate(self):
        for i in range(5):
            self.composer.learn_from_composition({
                "request_id": f"R{i}",
                "success": True,
                "utility": 0.8 + i * 0.02,
                "services": ["S1"],
                "algorithm": "llm",
            })
        self.assertEqual(len(self.composer.composition_history), 5)


# ── Annotation from_dict Roundtrip ───────────────────────────────

class TestAnnotationRoundtrip(unittest.TestCase):
    """Ensure annotations survive to_dict → from_dict roundtrip."""

    def test_full_roundtrip(self):
        from models.annotation import ServiceAnnotation
        ann = ServiceAnnotation("SvcA")
        ann.social_node.trust_degree.value = 0.9
        ann.social_node.reputation.value = 0.8
        ann.social_node.cooperativeness.value = 0.75
        ann.social_node.add_property("custom_prop", 0.42)
        ann.social_node.add_association("SvcB", "collaboration", 0.65)
        ann.interaction.can_call = ["SvcB", "SvcC"]
        ann.interaction.role = "orchestrator"
        ann.context.context_aware = True
        ann.context.observed_locations = {"Paris": 10}
        ann.policy.gdpr_compliant = True
        ann.policy.security_level = "high"
        ann.policy.compliance_standards = ["ISO27001", "SOC2"]

        d = ann.to_dict()
        restored = ServiceAnnotation.from_dict(d)

        self.assertEqual(restored.social_node.trust_degree.value, 0.9)
        self.assertEqual(restored.social_node.reputation.value, 0.8)
        self.assertEqual(restored.social_node.cooperativeness.value, 0.75)
        self.assertEqual(len(restored.social_node.properties), 1)
        self.assertEqual(len(restored.social_node.associations), 1)
        self.assertEqual(restored.interaction.can_call, ["SvcB", "SvcC"])
        self.assertEqual(restored.interaction.role, "orchestrator")
        self.assertTrue(restored.context.context_aware)
        self.assertEqual(restored.context.observed_locations, {"Paris": 10})
        self.assertTrue(restored.policy.gdpr_compliant)
        self.assertEqual(restored.policy.security_level, "high")
        self.assertIn("ISO27001", restored.policy.compliance_standards)


if __name__ == "__main__":
    unittest.main()
