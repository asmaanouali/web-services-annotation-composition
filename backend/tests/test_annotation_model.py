"""
Tests for annotation models — SNProperty, SNNode, SNAssociation,
InteractionAnnotation, ContextAnnotation, PolicyAnnotation, ServiceAnnotation.
"""

import unittest

from models.annotation import (
    SNProperty,
    SNAssociationType,
    SNAssociationWeight,
    SNAssociation,
    SNNode,
    InteractionAnnotation,
    ContextAnnotation,
    PolicyAnnotation,
    ServiceAnnotation,
)


class TestSNProperty(unittest.TestCase):
    def test_defaults(self):
        p = SNProperty()
        self.assertEqual(p.prop_name, "")
        self.assertEqual(p.value, 0.0)

    def test_custom_values(self):
        p = SNProperty("trust", 0.9)
        self.assertEqual(p.prop_name, "trust")
        self.assertAlmostEqual(p.value, 0.9)

    def test_to_dict(self):
        p = SNProperty("x", 1.5)
        d = p.to_dict()
        self.assertEqual(d["prop_name"], "x")
        self.assertAlmostEqual(d["value"], 1.5)


class TestSNAssociationType(unittest.TestCase):
    def test_defaults(self):
        t = SNAssociationType()
        self.assertEqual(t.type_name, "")
        self.assertFalse(t.is_symmetric)
        self.assertEqual(t.temporal_aspect, "permanent")

    def test_to_dict(self):
        t = SNAssociationType()
        t.type_name = "collaboration"
        d = t.to_dict()
        self.assertEqual(d["type_name"], "collaboration")


class TestSNAssociationWeight(unittest.TestCase):
    def test_inheritance(self):
        w = SNAssociationWeight("collab_weight", 0.7)
        self.assertIsInstance(w, SNProperty)
        self.assertEqual(w.prop_name, "collab_weight")
        self.assertAlmostEqual(w.value, 0.7)

    def test_calculation_method_default(self):
        w = SNAssociationWeight()
        self.assertEqual(w.calculation_method, "interaction_count")

    def test_to_dict_includes_method(self):
        w = SNAssociationWeight("w", 0.5)
        d = w.to_dict()
        self.assertIn("calculation_method", d)


class TestSNAssociation(unittest.TestCase):
    def test_defaults(self):
        a = SNAssociation()
        self.assertEqual(a.source_node, "")
        self.assertEqual(a.target_node, "")
        self.assertIsInstance(a.association_type, SNAssociationType)

    def test_to_dict(self):
        a = SNAssociation()
        a.source_node = "s1"
        a.target_node = "s2"
        d = a.to_dict()
        self.assertEqual(d["source_node"], "s1")
        self.assertEqual(d["target_node"], "s2")


class TestSNNode(unittest.TestCase):
    def test_defaults(self):
        n = SNNode("service_1")
        self.assertEqual(n.node_id, "service_1")
        self.assertEqual(n.node_type, "WebService")
        self.assertEqual(n.state, "active")
        self.assertAlmostEqual(n.trust_degree.value, 0.5)
        self.assertAlmostEqual(n.reputation.value, 0.5)

    def test_add_property(self):
        n = SNNode("s1")
        n.add_property("custom_prop", 0.8)
        self.assertEqual(len(n.properties), 1)
        self.assertEqual(n.properties[0].prop_name, "custom_prop")

    def test_add_association(self):
        n = SNNode("s1")
        n.add_association("s2", "collaboration", 0.6)
        self.assertEqual(len(n.associations), 1)
        self.assertEqual(n.associations[0].target_node, "s2")
        self.assertAlmostEqual(n.associations[0].association_weight.value, 0.6)

    def test_to_dict(self):
        n = SNNode("s1")
        n.add_association("s2", "substitution", 0.3)
        d = n.to_dict()
        self.assertEqual(d["node_id"], "s1")
        self.assertEqual(len(d["associations"]), 1)
        self.assertIn("trust_degree", d)


class TestInteractionAnnotation(unittest.TestCase):
    def test_defaults(self):
        ia = InteractionAnnotation()
        self.assertEqual(ia.can_call, [])
        self.assertEqual(ia.role, "worker")
        self.assertEqual(ia.substitutes, [])

    def test_to_dict(self):
        ia = InteractionAnnotation()
        ia.can_call = ["s2", "s3"]
        ia.role = "orchestrator"
        d = ia.to_dict()
        self.assertEqual(d["can_call"], ["s2", "s3"])
        self.assertEqual(d["role"], "orchestrator")


class TestContextAnnotation(unittest.TestCase):
    def test_defaults(self):
        ca = ContextAnnotation()
        self.assertFalse(ca.context_aware)
        self.assertEqual(ca.time_critical, "low")
        self.assertEqual(ca.interaction_count, 0)
        self.assertAlmostEqual(ca.context_adaptation_score, 0.0)

    def test_to_dict(self):
        ca = ContextAnnotation()
        ca.observed_locations = {"Paris": 10}
        d = ca.to_dict()
        self.assertEqual(d["observed_locations"], {"Paris": 10})


class TestPolicyAnnotation(unittest.TestCase):
    def test_defaults(self):
        pa = PolicyAnnotation()
        self.assertTrue(pa.gdpr_compliant)
        self.assertEqual(pa.security_level, "medium")
        self.assertEqual(pa.data_classification, "internal")

    def test_to_dict(self):
        pa = PolicyAnnotation()
        pa.compliance_standards = ["ISO27001", "HIPAA"]
        d = pa.to_dict()
        self.assertEqual(d["compliance_standards"], ["ISO27001", "HIPAA"])


class TestServiceAnnotation(unittest.TestCase):
    def test_creation(self):
        sa = ServiceAnnotation("svc_1")
        self.assertEqual(sa.social_node.node_id, "svc_1")
        self.assertIsInstance(sa.interaction, InteractionAnnotation)
        self.assertIsInstance(sa.context, ContextAnnotation)
        self.assertIsInstance(sa.policy, PolicyAnnotation)

    def test_to_dict(self):
        sa = ServiceAnnotation("svc_1")
        d = sa.to_dict()
        self.assertIn("social_node", d)
        self.assertIn("interaction", d)
        self.assertIn("context", d)
        self.assertIn("policy", d)

    def test_from_dict_roundtrip(self):
        sa = ServiceAnnotation("svc_1")
        sa.social_node.trust_degree.value = 0.85
        sa.social_node.reputation.value = 0.72
        d = sa.to_dict()
        restored = ServiceAnnotation.from_dict(d)
        self.assertEqual(restored.social_node.node_id, "svc_1")
        self.assertAlmostEqual(restored.social_node.trust_degree.value, 0.85)
        self.assertAlmostEqual(restored.social_node.reputation.value, 0.72)

    def test_from_dict_empty(self):
        restored = ServiceAnnotation.from_dict({})
        self.assertEqual(restored.social_node.node_id, "")


if __name__ == "__main__":
    unittest.main()
