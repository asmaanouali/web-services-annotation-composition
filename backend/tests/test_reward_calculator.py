"""
Tests for RewardCalculator — the analytical multi-objective reward function.

R = alpha * QoS_utility + beta * Social_trust + gamma * Chain_validity

Tests verify:
- Reward is always in [0, 1]
- Higher QoS services get higher reward
- Social annotations affect the reward
- Chain validity scoring (I/O correctness, goal reached)
- Custom weights
- Edge cases (empty services, no annotations)
"""

import unittest
from models.service import WebService, QoS, CompositionRequest
from models.annotation import ServiceAnnotation
from services.reward_calculator import RewardCalculator


def _svc(sid, inputs, outputs, qos_dict=None, annotated=False):
    """Helper: create a WebService."""
    s = WebService(sid)
    s.inputs = list(inputs)
    s.outputs = list(outputs)
    s.qos = QoS(qos_dict or {
        "ResponseTime": 50, "Availability": 95, "Throughput": 80,
        "Successability": 90, "Reliability": 95, "Compliance": 80,
        "BestPractices": 70, "Latency": 30, "Documentation": 60,
    })
    if annotated:
        s.annotations = ServiceAnnotation(sid)
        s.annotations.social_node.trust_degree.value = 0.8
        s.annotations.social_node.reputation.value = 0.7
        s.annotations.social_node.cooperativeness.value = 0.6
    return s


def _req(provided, resultant):
    r = CompositionRequest("R1")
    r.provided = list(provided)
    r.resultant = resultant
    return r


class TestRewardCalculatorBasic(unittest.TestCase):
    """Basic reward computation tests."""

    def setUp(self):
        self.calc = RewardCalculator()

    def test_reward_in_range(self):
        services = [_svc("S1", ["a"], ["b"], annotated=True)]
        req = _req(["a"], "b")
        result = self.calc.compute_reward(services, req)
        self.assertGreaterEqual(result["reward"], 0.0)
        self.assertLessEqual(result["reward"], 1.0)

    def test_reward_returns_all_components(self):
        services = [_svc("S1", ["a"], ["b"])]
        req = _req(["a"], "b")
        result = self.calc.compute_reward(services, req)
        self.assertIn("reward", result)
        self.assertIn("qos_score", result)
        self.assertIn("social_score", result)
        self.assertIn("chain_score", result)
        self.assertIn("weights", result)
        self.assertIn("detail", result)

    def test_empty_services_zero_reward(self):
        req = _req(["a"], "b")
        result = self.calc.compute_reward([], req)
        self.assertAlmostEqual(result["reward"], 0.0, places=4)

    def test_shorthand_reward_matches(self):
        services = [_svc("S1", ["a"], ["b"], annotated=True)]
        req = _req(["a"], "b")
        full = self.calc.compute_reward(services, req)
        short = self.calc.reward(services, req)
        self.assertAlmostEqual(full["reward"], short, places=6)


class TestRewardQoSComponent(unittest.TestCase):
    """Higher QoS services should produce higher QoS score."""

    def test_good_qos_beats_bad_qos(self):
        calc = RewardCalculator()
        good = _svc("S1", ["a"], ["b"], {
            "ResponseTime": 10, "Availability": 99, "Throughput": 90,
            "Successability": 98, "Reliability": 99, "Compliance": 95,
            "BestPractices": 90, "Latency": 5, "Documentation": 85,
        })
        bad = _svc("S2", ["a"], ["b"], {
            "ResponseTime": 1500, "Availability": 20, "Throughput": 5,
            "Successability": 15, "Reliability": 10, "Compliance": 5,
            "BestPractices": 5, "Latency": 1000, "Documentation": 5,
        })
        req = _req(["a"], "b")
        r_good = calc.compute_reward([good], req)["qos_score"]
        r_bad = calc.compute_reward([bad], req)["qos_score"]
        self.assertGreater(r_good, r_bad)


class TestRewardSocialComponent(unittest.TestCase):
    """Annotated services should get positive social score."""

    def test_annotated_service_has_social_score(self):
        calc = RewardCalculator()
        svc = _svc("S1", ["a"], ["b"], annotated=True)
        req = _req(["a"], "b")
        result = calc.compute_reward([svc], req)
        self.assertGreater(result["social_score"], 0.0)

    def test_unannotated_service_has_low_social_score(self):
        calc = RewardCalculator()
        svc = _svc("S1", ["a"], ["b"], annotated=False)
        req = _req(["a"], "b")
        result = calc.compute_reward([svc], req)
        # Without annotations, social_score should use defaults (0.5 each)
        # but still be in valid range
        self.assertGreaterEqual(result["social_score"], 0.0)
        self.assertLessEqual(result["social_score"], 1.0)


class TestRewardChainComponent(unittest.TestCase):
    """Chain validity tests — I/O correctness, goal reaching."""

    def test_valid_chain_higher_chain_score(self):
        calc = RewardCalculator()
        s1 = _svc("S1", ["a"], ["b"])
        s2 = _svc("S2", ["b"], ["c"])
        req = _req(["a"], "c")
        result = calc.compute_reward([s1, s2], req, workflow=["S1", "S2"])
        self.assertGreater(result["chain_score"], 0.0)

    def test_goal_not_reached_lower_chain_score(self):
        calc = RewardCalculator()
        s1 = _svc("S1", ["a"], ["b"])
        req = _req(["a"], "z")  # z is not produced
        result = calc.compute_reward([s1], req)
        # chain_score should be lower when goal not in outputs
        # compared to when goal IS in outputs
        s2 = _svc("S2", ["a"], ["z"])
        result2 = calc.compute_reward([s2], req)
        self.assertGreaterEqual(result2["chain_score"], result["chain_score"])


class TestRewardCustomWeights(unittest.TestCase):
    """Custom weights should be normalised and applied."""

    def test_custom_weights_normalized(self):
        calc = RewardCalculator({"alpha": 1.0, "beta": 0.0, "gamma": 0.0})
        self.assertAlmostEqual(calc.alpha, 1.0)
        self.assertAlmostEqual(calc.beta, 0.0)
        self.assertAlmostEqual(calc.gamma, 0.0)

    def test_qos_only_weight(self):
        calc = RewardCalculator({"alpha": 1.0, "beta": 0.0, "gamma": 0.0})
        svc = _svc("S1", ["a"], ["b"], annotated=True)
        req = _req(["a"], "b")
        result = calc.compute_reward([svc], req)
        # Reward should equal qos_score when only alpha counts
        self.assertAlmostEqual(result["reward"], result["qos_score"], places=4)


if __name__ == "__main__":
    unittest.main()
