"""
Unit tests for the formal evaluation metrics (precision, recall, F1, etc.)
defined in helpers.py.
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from helpers import (
    _extract_service_ids,
    _single_request_metrics,
    calculate_formal_metrics,
)


class TestExtractServiceIds(unittest.TestCase):
    """Tests for _extract_service_ids helper."""

    def test_empty_result(self):
        self.assertEqual(_extract_service_ids(None), set())
        self.assertEqual(_extract_service_ids({}), set())

    def test_from_services_key(self):
        result = {"services": ["s1", "s2", "s3"]}
        self.assertEqual(_extract_service_ids(result), {"s1", "s2", "s3"})

    def test_from_workflow_key(self):
        """Falls back to workflow when services is empty."""
        result = {"workflow": ["s4", "s5"]}
        self.assertEqual(_extract_service_ids(result), {"s4", "s5"})

    def test_services_takes_priority(self):
        result = {"services": ["s1"], "workflow": ["s2"]}
        self.assertEqual(_extract_service_ids(result), {"s1"})


class TestSingleRequestMetrics(unittest.TestCase):
    """Tests for _single_request_metrics helper."""

    def test_both_empty(self):
        m = _single_request_metrics(set(), set(), 0.0, 0.0)
        self.assertEqual(m["precision"], 1.0)
        self.assertEqual(m["recall"], 1.0)
        self.assertEqual(m["f1"], 1.0)
        self.assertEqual(m["exact_match"], 1.0)

    def test_composed_empty_best_not(self):
        m = _single_request_metrics(set(), {"s1", "s2"}, 0.0, 1.0)
        self.assertEqual(m["precision"], 0.0)
        self.assertEqual(m["recall"], 0.0)
        self.assertEqual(m["f1"], 0.0)
        self.assertEqual(m["exact_match"], 0.0)

    def test_no_best_ids_returns_none(self):
        m = _single_request_metrics({"s1"}, set(), 1.0, 0.0)
        self.assertIsNone(m)

    def test_perfect_match(self):
        ids = {"s1", "s2", "s3"}
        m = _single_request_metrics(ids, ids, 0.8, 0.8)
        self.assertAlmostEqual(m["precision"], 1.0)
        self.assertAlmostEqual(m["recall"], 1.0)
        self.assertAlmostEqual(m["f1"], 1.0)
        self.assertEqual(m["exact_match"], 1.0)
        self.assertAlmostEqual(m["utility_ratio"], 1.0)
        self.assertAlmostEqual(m["jaccard"], 1.0)

    def test_partial_overlap(self):
        composed = {"s1", "s2", "s3"}
        best = {"s2", "s3", "s4"}
        m = _single_request_metrics(composed, best, 0.6, 0.8)

        # tp = 2, composed_size = 3, best_size = 3
        self.assertAlmostEqual(m["precision"], 2 / 3, places=4)
        self.assertAlmostEqual(m["recall"], 2 / 3, places=4)
        expected_f1 = 2 * (2 / 3) * (2 / 3) / (2 / 3 + 2 / 3)
        self.assertAlmostEqual(m["f1"], expected_f1, places=4)
        self.assertEqual(m["exact_match"], 0.0)
        # jaccard = 2 / 4 = 0.5
        self.assertAlmostEqual(m["jaccard"], 0.5, places=4)
        # utility_ratio = 0.6 / 0.8 = 0.75
        self.assertAlmostEqual(m["utility_ratio"], 0.75, places=4)

    def test_no_overlap(self):
        composed = {"s1", "s2"}
        best = {"s3", "s4"}
        m = _single_request_metrics(composed, best, 0.3, 0.9)
        self.assertAlmostEqual(m["precision"], 0.0)
        self.assertAlmostEqual(m["recall"], 0.0)
        self.assertAlmostEqual(m["f1"], 0.0)
        self.assertAlmostEqual(m["jaccard"], 0.0)

    def test_superset(self):
        """Composed includes all best services plus extras."""
        composed = {"s1", "s2", "s3", "s4"}
        best = {"s2", "s3"}
        m = _single_request_metrics(composed, best, 0.7, 0.8)
        # precision = 2/4 = 0.5, recall = 2/2 = 1.0
        self.assertAlmostEqual(m["precision"], 0.5, places=4)
        self.assertAlmostEqual(m["recall"], 1.0, places=4)
        self.assertEqual(m["exact_match"], 0.0)


class TestCalculateFormalMetrics(unittest.TestCase):
    """Tests for the aggregate calculate_formal_metrics function."""

    def test_no_best_known_returns_none(self):
        comparisons = [
            {
                "request_id": "r1",
                "best_known": None,
                "classic": {"success": True, "services": ["s1"]},
                "llm": {"success": True, "services": ["s1"]},
            }
        ]
        self.assertIsNone(calculate_formal_metrics(comparisons))

    def test_single_perfect_comparison(self):
        comparisons = [
            {
                "request_id": "r1",
                "best_known": {"service_ids": ["s1", "s2"], "utility": 0.9},
                "classic": {
                    "success": True,
                    "services": ["s1", "s2"],
                    "utility_value": 0.9,
                },
                "llm": {
                    "success": True,
                    "services": ["s1", "s2"],
                    "utility_value": 0.9,
                },
            }
        ]
        result = calculate_formal_metrics(comparisons)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["classic"]["macro_precision"], 1.0)
        self.assertAlmostEqual(result["classic"]["macro_recall"], 1.0)
        self.assertAlmostEqual(result["classic"]["macro_f1"], 1.0)
        self.assertAlmostEqual(result["llm"]["macro_precision"], 1.0)
        self.assertEqual(result["classic"]["evaluated_requests"], 1)

    def test_multiple_requests_average(self):
        comparisons = [
            {
                "request_id": "r1",
                "best_known": {"service_ids": ["s1", "s2"], "utility": 1.0},
                "classic": {
                    "success": True,
                    "services": ["s1", "s2"],
                    "utility_value": 1.0,
                },
                "llm": {
                    "success": True,
                    "services": ["s1"],
                    "utility_value": 0.5,
                },
            },
            {
                "request_id": "r2",
                "best_known": {"service_ids": ["s3", "s4"], "utility": 1.0},
                "classic": {
                    "success": True,
                    "services": ["s3"],
                    "utility_value": 0.6,
                },
                "llm": {
                    "success": True,
                    "services": ["s3", "s4"],
                    "utility_value": 1.0,
                },
            },
        ]
        result = calculate_formal_metrics(comparisons)
        self.assertIsNotNone(result)
        # Classic: r1 perfect (1.0), r2 partial (p=1.0, r=0.5)
        # → macro_precision = (1.0+1.0)/2 = 1.0 since s3 is in best
        self.assertEqual(result["classic"]["evaluated_requests"], 2)
        self.assertEqual(result["llm"]["evaluated_requests"], 2)
        # Per-request detail
        self.assertEqual(len(result["per_request"]), 2)

    def test_failed_methods_handled(self):
        comparisons = [
            {
                "request_id": "r1",
                "best_known": {"service_ids": ["s1"], "utility": 0.9},
                "classic": {"success": False},
                "llm": None,
            }
        ]
        result = calculate_formal_metrics(comparisons)
        self.assertIsNotNone(result)
        # Both methods failed → 0 evaluated
        self.assertEqual(result["classic"]["evaluated_requests"], 0)
        self.assertEqual(result["llm"]["evaluated_requests"], 0)
        self.assertAlmostEqual(result["classic"]["macro_precision"], 0.0)

    def test_empty_comparisons(self):
        self.assertIsNone(calculate_formal_metrics([]))


if __name__ == "__main__":
    unittest.main()
