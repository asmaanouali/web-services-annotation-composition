"""
Unit tests for data models (QoS, WebService, CompositionRequest, CompositionResult).
"""
import unittest
import sys
import os

# Ensure backend is on the import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.service import QoS, WebService, CompositionRequest, CompositionResult


class TestQoS(unittest.TestCase):
    """Tests for the QoS model."""

    def test_default_init(self):
        qos = QoS()
        self.assertEqual(qos.response_time, 0.0)
        self.assertEqual(qos.availability, 0.0)
        self.assertEqual(qos.throughput, 0.0)

    def test_dict_init(self):
        data = {
            "ResponseTime": 150,
            "Availability": 99.5,
            "Throughput": 500,
            "Successability": 95,
            "Reliability": 98,
            "Compliance": 80,
            "BestPractices": 75,
            "Latency": 30,
            "Documentation": 60,
        }
        qos = QoS(data)
        self.assertEqual(qos.response_time, 150.0)
        self.assertEqual(qos.availability, 99.5)
        self.assertEqual(qos.documentation, 60.0)

    def test_kwargs_init(self):
        qos = QoS(response_time=200, availability=90)
        self.assertEqual(qos.response_time, 200.0)
        self.assertEqual(qos.availability, 90.0)
        # Unset values should default to 0
        self.assertEqual(qos.throughput, 0.0)

    def test_kwargs_override_dict(self):
        """kwargs should take priority over a dict if both provided."""
        data = {"ResponseTime": 100}
        qos = QoS(data, response_time=999)
        self.assertEqual(qos.response_time, 999.0)

    def test_to_dict(self):
        qos = QoS(response_time=10, availability=99)
        d = qos.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["ResponseTime"], 10.0)
        self.assertEqual(d["Availability"], 99.0)
        self.assertEqual(len(d), 9)

    def test_meets_constraints_all_pass(self):
        achieved = QoS(
            response_time=100, availability=95, throughput=500,
            successability=90, reliability=92, compliance=80,
            best_practices=70, latency=20, documentation=60,
        )
        constraints = QoS(
            response_time=200, availability=90, throughput=400,
            successability=80, reliability=85, compliance=70,
            best_practices=60, latency=50, documentation=50,
        )
        checks = achieved.meets_constraints(constraints)
        self.assertTrue(all(checks.values()))

    def test_meets_constraints_lower_is_better(self):
        achieved = QoS(response_time=300, latency=100)
        constraints = QoS(response_time=200, latency=50)
        checks = achieved.meets_constraints(constraints)
        self.assertFalse(checks["ResponseTime"])
        self.assertFalse(checks["Latency"])

    def test_zero_constraint_means_unconstrained(self):
        achieved = QoS(response_time=9999, latency=9999)
        constraints = QoS()  # all zeros
        checks = achieved.meets_constraints(constraints)
        self.assertTrue(checks["ResponseTime"])
        self.assertTrue(checks["Latency"])


class TestWebService(unittest.TestCase):
    """Tests for the WebService model."""

    def test_defaults(self):
        ws = WebService("svc1")
        self.assertEqual(ws.id, "svc1")
        self.assertEqual(ws.name, "svc1")
        self.assertEqual(ws.inputs, [])
        self.assertEqual(ws.outputs, [])

    def test_custom_name(self):
        ws = WebService("svc2", name="My Service")
        self.assertEqual(ws.name, "My Service")

    def test_can_produce(self):
        ws = WebService("svc3")
        ws.outputs = ["paramA", "paramB"]
        self.assertTrue(ws.can_produce("paramA"))
        self.assertFalse(ws.can_produce("paramC"))

    def test_has_required_inputs(self):
        ws = WebService("svc4")
        ws.inputs = ["x", "y"]
        self.assertTrue(ws.has_required_inputs({"x", "y", "z"}))
        self.assertFalse(ws.has_required_inputs({"x"}))

    def test_to_dict(self):
        ws = WebService("svc5")
        ws.inputs = ["a"]
        ws.outputs = ["b"]
        d = ws.to_dict()
        self.assertEqual(d["id"], "svc5")
        self.assertEqual(d["inputs"], ["a"])
        self.assertEqual(d["outputs"], ["b"])
        self.assertIsNone(d["annotations"])


class TestCompositionRequest(unittest.TestCase):
    """Tests for the CompositionRequest model."""

    def test_init(self):
        cr = CompositionRequest("req1")
        self.assertEqual(cr.id, "req1")
        self.assertEqual(cr.provided, [])
        self.assertIsNone(cr.resultant)

    def test_to_dict(self):
        cr = CompositionRequest("req2")
        cr.provided = ["p1", "p2"]
        cr.resultant = "out1"
        d = cr.to_dict()
        self.assertEqual(d["provided"], ["p1", "p2"])
        self.assertEqual(d["resultant"], "out1")


class TestCompositionResult(unittest.TestCase):
    """Tests for the CompositionResult model."""

    def test_defaults(self):
        result = CompositionResult()
        self.assertEqual(result.services, [])
        self.assertEqual(result.utility_value, 0.0)
        self.assertFalse(result.success)

    def test_to_dict(self):
        result = CompositionResult()
        result.success = True
        result.algorithm_used = "dijkstra"
        result.utility_value = 85.5
        d = result.to_dict()
        self.assertTrue(d["success"])
        self.assertEqual(d["algorithm_used"], "dijkstra")
        self.assertAlmostEqual(d["utility_value"], 85.5)

    def test_to_dict_with_service_objects(self):
        result = CompositionResult()
        ws = WebService("svc1")
        result.services = [ws]
        d = result.to_dict()
        self.assertEqual(d["services"], ["svc1"])


if __name__ == "__main__":
    unittest.main()
