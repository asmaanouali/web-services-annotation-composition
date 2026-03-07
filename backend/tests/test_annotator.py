"""
Tests for ServiceAnnotator — heuristic annotation generation.

Tests the classic (rule-based) annotation path that doesn't require
Ollama or any external service.  Covers interaction, context, and
policy annotation generation, the _extract_json helper, and the
social association builder.
"""

import unittest
import json
from datetime import datetime

from models.service import WebService, QoS
from models.annotation import (
    ServiceAnnotation, InteractionAnnotation,
    ContextAnnotation, PolicyAnnotation,
    SNNode, SNAssociation, SNProperty,
)
from models.interaction_history import InteractionHistoryStore
from services.annotator import ServiceAnnotator


# ── Helpers ──────────────────────────────────────────────────────

def _svc(sid, inputs, outputs, qos_overrides=None):
    """Create a minimal WebService for testing."""
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


def _build_services():
    """Build a small network of services with known I/O relationships."""
    return [
        _svc("S1", ["a"], ["b"]),
        _svc("S2", ["b"], ["c"]),
        _svc("S3", ["c"], ["d"]),
        _svc("S4", ["a"], ["c"]),          # alternative to S1+S2
        _svc("S5", ["b", "c"], ["e"]),     # aggregator
        _svc("S6", ["a"], ["b"],            # substitute for S1 but low quality
             {"Reliability": 40, "Compliance": 50, "BestPractices": 30}),
    ]


# ── Test Suite ───────────────────────────────────────────────────

class TestAnnotatorInit(unittest.TestCase):
    """Test annotator construction and index building."""

    def test_indexes_built(self):
        services = _build_services()
        ann = ServiceAnnotator(services=services)
        # S1 and S6 both produce 'b'
        self.assertIn("S1", ann._output_index["b"])
        self.assertIn("S6", ann._output_index["b"])
        # S5 consumes 'b' and 'c'
        self.assertIn("S5", ann._input_index["b"])
        self.assertIn("S5", ann._input_index["c"])

    def test_qos_caches(self):
        services = _build_services()
        ann = ServiceAnnotator(services=services)
        self.assertEqual(ann._qos_reliability["S1"], 90)
        self.assertEqual(ann._qos_reliability["S6"], 40)

    def test_no_services(self):
        ann = ServiceAnnotator(services=[])
        self.assertEqual(len(ann.services), 0)
        self.assertEqual(len(ann._output_index), 0)


class TestInteractionAnnotation(unittest.TestCase):
    """Test heuristic interaction annotation generation."""

    def setUp(self):
        self.services = _build_services()
        self.annotator = ServiceAnnotator(services=self.services)

    def test_can_call_via_output_match(self):
        """S1 produces 'b'; S2 and S5 consume 'b' → S1 can_call S2 and S5."""
        interaction = self.annotator._generate_interaction_annotations(
            self.services[0]  # S1
        )
        self.assertIn("S2", interaction.can_call)
        self.assertIn("S5", interaction.can_call)

    def test_depends_on(self):
        """S2 consumes 'b'; S1 and S6 produce 'b' → S2 depends on S1, S6."""
        interaction = self.annotator._generate_interaction_annotations(
            self.services[1]  # S2
        )
        self.assertIn("S1", interaction.depends_on)
        self.assertIn("S6", interaction.depends_on)

    def test_role_orchestrator(self):
        """A service with many can_call gets role=orchestrator."""
        # S1 can call S2 and S5 (only 2, so should be worker)
        interaction = self.annotator._generate_interaction_annotations(
            self.services[0]
        )
        # With only 2 can_call, it should be 'worker' (threshold > 3)
        self.assertIn(interaction.role, ["worker", "orchestrator", "aggregator"])

    def test_collaboration_associations_populated(self):
        interaction = self.annotator._generate_interaction_annotations(
            self.services[0]
        )
        self.assertEqual(
            set(interaction.collaboration_associations),
            set(interaction.can_call),
        )

    def test_empty_service_no_crash(self):
        """A service with no I/O overlap should produce empty annotations."""
        lonely = _svc("Lonely", ["z"], ["w"])
        annotator = ServiceAnnotator(services=self.services + [lonely])
        interaction = annotator._generate_interaction_annotations(lonely)
        self.assertEqual(interaction.can_call, [])
        self.assertEqual(interaction.depends_on, [])


class TestContextAnnotation(unittest.TestCase):
    """Test heuristic context annotation generation."""

    def setUp(self):
        self.services = _build_services()
        self.annotator = ServiceAnnotator(services=self.services)

    def test_time_critical_based_on_response_time(self):
        ctx = self.annotator._generate_context_annotations(self.services[0])
        # S1 has response_time=50 → time_critical="low" (< 50 is low)
        self.assertIn(ctx.time_critical, ["low", "medium"])

    def test_high_response_time_service(self):
        slow = _svc("Slow", ["x"], ["y"], {"ResponseTime": 500})
        annotator = ServiceAnnotator(services=[slow])
        ctx = annotator._generate_context_annotations(slow)
        self.assertEqual(ctx.time_critical, "high")

    def test_context_adaptation_score_range(self):
        ctx = self.annotator._generate_context_annotations(self.services[0])
        self.assertGreaterEqual(ctx.context_adaptation_score, 0.0)
        self.assertLessEqual(ctx.context_adaptation_score, 1.0)

    def test_returns_context_annotation_type(self):
        ctx = self.annotator._generate_context_annotations(self.services[0])
        self.assertIsInstance(ctx, ContextAnnotation)


class TestPolicyAnnotation(unittest.TestCase):
    """Test heuristic policy annotation generation."""

    def setUp(self):
        self.services = _build_services()
        self.annotator = ServiceAnnotator(services=self.services)

    def test_gdpr_based_on_compliance(self):
        # S1 has compliance=75 → gdpr_compliant=True (threshold > 70)
        policy = self.annotator._generate_policy_annotations(self.services[0])
        self.assertTrue(policy.gdpr_compliant)

    def test_low_compliance_not_gdpr(self):
        bad = _svc("Bad", ["x"], ["y"], {"Compliance": 50})
        annotator = ServiceAnnotator(services=[bad])
        policy = annotator._generate_policy_annotations(bad)
        self.assertFalse(policy.gdpr_compliant)

    def test_security_level_from_reliability(self):
        # S1 reliability=90 → security_level='medium' (threshold > 90 for high)
        policy = self.annotator._generate_policy_annotations(self.services[0])
        self.assertIn(policy.security_level, ["low", "medium", "high"])

    def test_high_reliability_high_security(self):
        secure = _svc("Secure", ["x"], ["y"], {"Reliability": 95, "Compliance": 90})
        annotator = ServiceAnnotator(services=[secure])
        policy = annotator._generate_policy_annotations(secure)
        self.assertEqual(policy.security_level, "high")

    def test_compliance_standards_populated(self):
        high_comp = _svc("HC", ["x"], ["y"], {"Compliance": 90})
        annotator = ServiceAnnotator(services=[high_comp])
        policy = annotator._generate_policy_annotations(high_comp)
        self.assertIn("ISO27001", policy.compliance_standards)
        self.assertIn("SOC2", policy.compliance_standards)

    def test_encryption_required_for_high_security(self):
        secure = _svc("Secure", ["x"], ["y"], {"Reliability": 95, "Compliance": 90})
        annotator = ServiceAnnotator(services=[secure])
        policy = annotator._generate_policy_annotations(secure)
        self.assertTrue(policy.encryption_required)

    def test_returns_policy_annotation_type(self):
        policy = self.annotator._generate_policy_annotations(self.services[0])
        self.assertIsInstance(policy, PolicyAnnotation)


class TestAnnotateAllClassic(unittest.TestCase):
    """Test bulk annotation (classic mode, no LLM)."""

    def setUp(self):
        self.services = _build_services()
        self.annotator = ServiceAnnotator(services=self.services)

    def test_annotate_all_services(self):
        annotated = self.annotator.annotate_all(use_llm=False)
        self.assertEqual(len(annotated), len(self.services))
        for svc in annotated:
            self.assertIsNotNone(svc.annotations)
            self.assertIsNotNone(svc.annotations.interaction)
            self.assertIsNotNone(svc.annotations.context)
            self.assertIsNotNone(svc.annotations.policy)

    def test_annotate_subset(self):
        annotated = self.annotator.annotate_all(
            service_ids=["S1", "S2"], use_llm=False
        )
        ids = {s.id for s in annotated}
        self.assertIn("S1", ids)
        self.assertIn("S2", ids)

    def test_annotate_specific_types(self):
        annotated = self.annotator.annotate_all(
            service_ids=["S1"],
            use_llm=False,
            annotation_types=["interaction"],
        )
        svc = annotated[0]
        self.assertIsNotNone(svc.annotations)

    def test_social_node_populated(self):
        annotated = self.annotator.annotate_all(use_llm=False)
        for svc in annotated:
            sn = svc.annotations.social_node
            self.assertEqual(sn.node_id, svc.id)
            self.assertGreater(sn.trust_degree.value, 0)
            self.assertGreater(sn.reputation.value, 0)

    def test_progress_callback(self):
        progress_values = []
        def cb(current, total, svc_id):
            progress_values.append((current, total))
        self.annotator.annotate_all(use_llm=False, progress_callback=cb)
        self.assertGreater(len(progress_values), 0)

    def test_annotations_serializable(self):
        annotated = self.annotator.annotate_all(use_llm=False)
        for svc in annotated:
            d = svc.annotations.to_dict()
            self.assertIn("social_node", d)
            self.assertIn("interaction", d)
            self.assertIn("context", d)
            self.assertIn("policy", d)
            # Verify JSON-serializable
            json.dumps(d)


class TestExtractJson(unittest.TestCase):
    """Test the JSON extraction helper."""

    def setUp(self):
        self.annotator = ServiceAnnotator(services=[])

    def test_clean_json(self):
        result = self.annotator._extract_json('{"key": "value"}')
        self.assertEqual(result, {"key": "value"})

    def test_json_with_surrounding_text(self):
        text = 'Here is the result: {"role": "worker"} end of message'
        result = self.annotator._extract_json(text)
        self.assertEqual(result["role"], "worker")

    def test_invalid_json(self):
        result = self.annotator._extract_json("no json here")
        self.assertIsNone(result)

    def test_empty_string(self):
        result = self.annotator._extract_json("")
        self.assertIsNone(result)

    def test_nested_json(self):
        text = '{"interaction": {"role": "orchestrator"}, "context": {"context_aware": true}}'
        result = self.annotator._extract_json(text)
        self.assertEqual(result["interaction"]["role"], "orchestrator")
        self.assertTrue(result["context"]["context_aware"])


class TestAnnotationWithHistory(unittest.TestCase):
    """Test annotation generation with interaction history data."""

    def test_history_enriches_annotations(self):
        import tempfile, os
        from models.interaction_history import InteractionRecord
        services = _build_services()
        tmp = tempfile.mktemp(suffix=".json")
        try:
            store = InteractionHistoryStore(path=tmp)
            # Record some synthetic interactions
            store.record(InteractionRecord(
                service_id="S1",
                composition_id="comp-1",
                co_services=["S2", "S3"],
                success=True,
                utility=0.85,
                context={"location": "Paris", "network_type": "wifi", "device_type": "desktop"},
            ))
            store.record(InteractionRecord(
                service_id="S1",
                composition_id="comp-2",
                co_services=["S2"],
                success=True,
                utility=0.90,
                context={"location": "London", "network_type": "4G", "device_type": "mobile"},
            ))
            annotator = ServiceAnnotator(services=services, interaction_store=store)
            ctx = annotator._generate_context_annotations(services[0])
            # Should show interaction count from history
            self.assertEqual(ctx.interaction_count, 2)
            # Should have observed locations from history
            self.assertIn("Paris", ctx.observed_locations)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def test_no_history_still_works(self):
        services = _build_services()
        annotator = ServiceAnnotator(services=services)
        ctx = annotator._generate_context_annotations(services[0])
        self.assertEqual(ctx.interaction_count, 0)
        self.assertIsInstance(ctx, ContextAnnotation)


if __name__ == "__main__":
    unittest.main()
