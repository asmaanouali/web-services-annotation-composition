"""
Unit tests for the QoS utility calculator.
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.service import QoS
from utils.qos_calculator import (
    calculate_utility,
    calculate_utility_detailed,
    normalize,
    normalize_inverse,
    aggregate_qos,
    compare_qos,
)


class TestNormalize(unittest.TestCase):
    """Tests for the normalize / normalize_inverse helpers."""

    def test_normalize_min(self):
        self.assertAlmostEqual(normalize(0, 0, 100, 0, 10), 0.0)

    def test_normalize_max(self):
        self.assertAlmostEqual(normalize(100, 0, 100, 0, 10), 10.0)

    def test_normalize_mid(self):
        self.assertAlmostEqual(normalize(50, 0, 100, 0, 10), 5.0)

    def test_normalize_clamps_above(self):
        self.assertAlmostEqual(normalize(200, 0, 100, 0, 10), 10.0)

    def test_normalize_clamps_below(self):
        self.assertAlmostEqual(normalize(-50, 0, 100, 0, 10), 0.0)

    def test_normalize_equal_range(self):
        """When min == max, return target_min."""
        self.assertAlmostEqual(normalize(50, 50, 50, 0, 10), 0.0)

    def test_normalize_inverse_min(self):
        """Lowest value → highest target."""
        self.assertAlmostEqual(normalize_inverse(0, 0, 100, 0, 10), 10.0)

    def test_normalize_inverse_max(self):
        """Highest value → lowest target."""
        self.assertAlmostEqual(normalize_inverse(100, 0, 100, 0, 10), 0.0)

    def test_normalize_inverse_equal_range(self):
        self.assertAlmostEqual(normalize_inverse(50, 50, 50, 0, 10), 10.0)


class TestCalculateUtility(unittest.TestCase):
    """Tests for the main utility calculator."""

    def _make_qos(self, **kw):
        return QoS(**kw)

    def test_perfect_service(self):
        """A service meeting all constraints with high QoS should score high."""
        achieved = self._make_qos(
            response_time=50, availability=99, throughput=800,
            successability=98, reliability=99, compliance=95,
            best_practices=90, latency=10, documentation=85,
        )
        constraints = self._make_qos(
            response_time=200, availability=80, throughput=500,
            successability=80, reliability=80, compliance=70,
            best_practices=60, latency=50, documentation=50,
        )
        checks = achieved.meets_constraints(constraints)
        utility = calculate_utility(achieved, constraints, checks)
        self.assertGreater(utility, 100)

    def test_zero_qos_service(self):
        """A service with all-zero QoS should score low."""
        achieved = QoS()
        constraints = self._make_qos(
            response_time=100, availability=90, throughput=500,
            successability=80, reliability=80, compliance=70,
            best_practices=60, latency=50, documentation=50,
        )
        checks = achieved.meets_constraints(constraints)
        utility = calculate_utility(achieved, constraints, checks)
        self.assertGreaterEqual(utility, 0)

    def test_utility_non_negative(self):
        """Utility must never be negative."""
        achieved = QoS()
        constraints = QoS()
        checks = achieved.meets_constraints(constraints)
        utility = calculate_utility(achieved, constraints, checks)
        self.assertGreaterEqual(utility, 0)

    def test_detailed_returns_breakdown(self):
        """Detailed version should return a dict with expected keys."""
        achieved = self._make_qos(
            response_time=100, availability=95, throughput=600,
            successability=90, reliability=92, compliance=80,
            best_practices=70, latency=20, documentation=60,
        )
        constraints = self._make_qos(
            response_time=200, availability=80, throughput=400,
            successability=80, reliability=80, compliance=70,
            best_practices=60, latency=50, documentation=50,
        )
        checks = achieved.meets_constraints(constraints)
        detail = calculate_utility_detailed(achieved, constraints, checks)
        self.assertIn("utility", detail)
        self.assertIn("quality_score", detail)
        self.assertIn("conformity_score", detail)
        self.assertIn("penalty_factor", detail)
        self.assertAlmostEqual(
            detail["utility"],
            calculate_utility(achieved, constraints, checks),
            places=5,
        )


class TestAggregateQoS(unittest.TestCase):
    """Tests for sequential composition QoS aggregation."""

    def _ws(self, **qos_kw):
        from models.service import WebService
        ws = WebService("test")
        ws.qos = QoS(**qos_kw)
        return ws

    def test_empty(self):
        agg = aggregate_qos([])
        self.assertIsInstance(agg, QoS)

    def test_single_service(self):
        ws = self._ws(response_time=100, availability=95)
        agg = aggregate_qos([ws])
        self.assertEqual(agg.response_time, 100)
        self.assertEqual(agg.availability, 95)

    def test_times_are_summed(self):
        ws1 = self._ws(response_time=100, latency=10)
        ws2 = self._ws(response_time=200, latency=20)
        agg = aggregate_qos([ws1, ws2])
        self.assertAlmostEqual(agg.response_time, 300)
        self.assertAlmostEqual(agg.latency, 30)

    def test_probabilities_are_multiplied(self):
        ws1 = self._ws(availability=90, reliability=80, successability=70)
        ws2 = self._ws(availability=80, reliability=90, successability=60)
        agg = aggregate_qos([ws1, ws2])
        self.assertAlmostEqual(agg.availability, 0.9 * 0.8 * 100, places=2)
        self.assertAlmostEqual(agg.reliability, 0.8 * 0.9 * 100, places=2)

    def test_minimums_are_taken(self):
        ws1 = self._ws(throughput=500, compliance=80, best_practices=70, documentation=60)
        ws2 = self._ws(throughput=300, compliance=90, best_practices=65, documentation=80)
        agg = aggregate_qos([ws1, ws2])
        self.assertAlmostEqual(agg.throughput, 300)
        self.assertAlmostEqual(agg.compliance, 80)
        self.assertAlmostEqual(agg.best_practices, 65)
        self.assertAlmostEqual(agg.documentation, 60)


class TestCompareQoS(unittest.TestCase):
    """Tests for QoS comparison."""

    def test_basic_comparison(self):
        q1 = QoS(response_time=100, availability=95)
        q2 = QoS(response_time=200, availability=90)
        result = compare_qos(q1, q2)
        # Lower response time is better → q1 wins
        self.assertEqual(result["response_time"]["winner"], "qos1")
        # Higher availability is better → q1 wins
        self.assertEqual(result["availability"]["winner"], "qos1")

    def test_tie(self):
        q1 = QoS(availability=95)
        q2 = QoS(availability=95)
        result = compare_qos(q1, q2)
        self.assertEqual(result["availability"]["winner"], "tie")


if __name__ == "__main__":
    unittest.main()
