"""
Tests for ClassicComposer — Dijkstra, A*, and Greedy algorithms.

Uses a small hand-crafted service graph where the expected optimal
composition path is known, allowing us to verify each algorithm's
correctness and trace output.
"""

import unittest
from models.service import WebService, QoS, CompositionRequest, CompositionResult
from services.classic_composer import ClassicComposer


def _make_service(sid, inputs, outputs, qos_data=None):
    """Helper: create a WebService with given I/O and QoS."""
    s = WebService(sid)
    s.inputs = list(inputs)
    s.outputs = list(outputs)
    if qos_data:
        s.qos = QoS(qos_data)
    else:
        s.qos = QoS({
            "ResponseTime": 50,
            "Availability": 90,
            "Throughput": 80,
            "Successability": 85,
            "Reliability": 90,
            "Compliance": 70,
            "BestPractices": 60,
            "Latency": 30,
            "Documentation": 50,
        })
    return s


def _make_request(rid, provided, resultant, constraints=None):
    """Helper: create a CompositionRequest."""
    req = CompositionRequest(rid)
    req.provided = list(provided)
    req.resultant = resultant
    if constraints:
        req.qos_constraints = QoS(constraints)
    return req


class TestClassicComposerSimpleChain(unittest.TestCase):
    """A → B → C linear chain: provided={a}, resultant=d.

    S1: a → b
    S2: b → c
    S3: c → d
    Only one valid path: S1 → S2 → S3.
    """

    @classmethod
    def setUpClass(cls):
        cls.services = [
            _make_service("S1", ["a"], ["b"]),
            _make_service("S2", ["b"], ["c"]),
            _make_service("S3", ["c"], ["d"]),
        ]
        cls.composer = ClassicComposer(cls.services)
        cls.request = _make_request("R1", ["a"], "d")

    def test_dijkstra_finds_solution(self):
        result = self.composer.compose(self.request, "dijkstra")
        self.assertTrue(result.success)
        ids = [s.id if hasattr(s, "id") else s for s in result.services]
        self.assertIn("S1", ids)
        self.assertIn("S2", ids)
        self.assertIn("S3", ids)

    def test_astar_finds_solution(self):
        result = self.composer.compose(self.request, "astar")
        self.assertTrue(result.success)
        ids = [s.id if hasattr(s, "id") else s for s in result.services]
        self.assertIn("S3", ids)

    def test_greedy_finds_solution(self):
        result = self.composer.compose(self.request, "greedy")
        self.assertTrue(result.success)

    def test_result_has_trace(self):
        result = self.composer.compose(self.request, "dijkstra")
        self.assertIsInstance(result.algorithm_trace, list)
        self.assertGreater(len(result.algorithm_trace), 0)

    def test_result_has_computation_time(self):
        result = self.composer.compose(self.request, "astar")
        self.assertGreaterEqual(result.computation_time, 0)

    def test_result_has_utility(self):
        result = self.composer.compose(self.request, "dijkstra")
        self.assertGreater(result.utility_value, 0)


class TestClassicComposerUnreachable(unittest.TestCase):
    """No path exists to produce the desired output."""

    @classmethod
    def setUpClass(cls):
        cls.services = [
            _make_service("S1", ["a"], ["b"]),
            _make_service("S2", ["x"], ["y"]),  # unrelated
        ]
        cls.composer = ClassicComposer(cls.services)
        cls.request = _make_request("R1", ["a"], "z")

    def test_dijkstra_reports_failure(self):
        result = self.composer.compose(self.request, "dijkstra")
        self.assertFalse(result.success)

    def test_astar_reports_failure(self):
        result = self.composer.compose(self.request, "astar")
        self.assertFalse(result.success)

    def test_greedy_reports_failure(self):
        result = self.composer.compose(self.request, "greedy")
        self.assertFalse(result.success)


class TestClassicComposerBranching(unittest.TestCase):
    """Graph with two alternative paths — algorithm should pick one.

    S1: a → b         (high QoS)
    S2: a → b         (low QoS)
    S3: b → c

    Path 1: S1 → S3 (better)
    Path 2: S2 → S3 (worse)
    """

    @classmethod
    def setUpClass(cls):
        good_qos = {
            "ResponseTime": 10, "Availability": 99, "Throughput": 95,
            "Successability": 98, "Reliability": 99, "Compliance": 90,
            "BestPractices": 85, "Latency": 5, "Documentation": 80,
        }
        bad_qos = {
            "ResponseTime": 200, "Availability": 50, "Throughput": 20,
            "Successability": 40, "Reliability": 30, "Compliance": 10,
            "BestPractices": 10, "Latency": 150, "Documentation": 10,
        }
        cls.services = [
            _make_service("S1_good", ["a"], ["b"], good_qos),
            _make_service("S2_bad", ["a"], ["b"], bad_qos),
            _make_service("S3", ["b"], ["c"]),
        ]
        cls.composer = ClassicComposer(cls.services)
        cls.request = _make_request("R1", ["a"], "c")

    def test_dijkstra_prefers_better_path(self):
        result = self.composer.compose(self.request, "dijkstra")
        self.assertTrue(result.success)
        ids = [s.id if hasattr(s, "id") else s for s in result.services]
        # Dijkstra should find the optimal path with S1_good
        self.assertIn("S1_good", ids)

    def test_astar_prefers_better_path(self):
        result = self.composer.compose(self.request, "astar")
        self.assertTrue(result.success)
        ids = [s.id if hasattr(s, "id") else s for s in result.services]
        self.assertIn("S1_good", ids)


class TestClassicComposerDirectService(unittest.TestCase):
    """Single service directly satisfies the request."""

    @classmethod
    def setUpClass(cls):
        cls.services = [_make_service("S_direct", ["a"], ["b"])]
        cls.composer = ClassicComposer(cls.services)
        cls.request = _make_request("R1", ["a"], "b")

    def test_dijkstra_single_service(self):
        result = self.composer.compose(self.request, "dijkstra")
        self.assertTrue(result.success)
        ids = [s.id if hasattr(s, "id") else s for s in result.services]
        self.assertEqual(ids, ["S_direct"])

    def test_all_algorithms_return_same(self):
        for algo in ["dijkstra", "astar", "greedy"]:
            result = self.composer.compose(self.request, algo)
            self.assertTrue(result.success, f"{algo} should find a solution")
            ids = [s.id if hasattr(s, "id") else s for s in result.services]
            self.assertEqual(len(ids), 1, f"{algo} should use exactly 1 service")


class TestClassicComposerEmptyServices(unittest.TestCase):
    """Edge case: no services at all."""

    def test_empty_services(self):
        composer = ClassicComposer([])
        req = _make_request("R1", ["a"], "b")
        for algo in ["dijkstra", "astar", "greedy"]:
            result = composer.compose(req, algo)
            self.assertFalse(result.success)


class TestClassicComposerComposeAllAlgorithms(unittest.TestCase):
    """Test compose_all_algorithms returns results for all three."""

    @classmethod
    def setUpClass(cls):
        cls.services = [
            _make_service("S1", ["a"], ["b"]),
            _make_service("S2", ["b"], ["c"]),
        ]
        cls.composer = ClassicComposer(cls.services)
        cls.request = _make_request("R", ["a"], "c")

    def test_compose_all_returns_three(self):
        results = self.composer.compose_all_algorithms(self.request)
        self.assertIn("dijkstra", results)
        self.assertIn("astar", results)
        self.assertIn("greedy", results)

    def test_compose_all_all_succeed(self):
        results = self.composer.compose_all_algorithms(self.request)
        for algo, result in results.items():
            self.assertTrue(result["success"], f"{algo} should succeed")


class TestClassicComposerGraphData(unittest.TestCase):
    """Verify that graph_data is populated for visualization."""

    @classmethod
    def setUpClass(cls):
        cls.services = [
            _make_service("S1", ["a"], ["b"]),
            _make_service("S2", ["b"], ["c"]),
        ]
        cls.composer = ClassicComposer(cls.services)
        cls.request = _make_request("R", ["a"], "c")

    def test_graph_data_present(self):
        result = self.composer.compose(self.request, "dijkstra")
        self.assertTrue(result.success)
        self.assertIsNotNone(result.graph_data)
        self.assertIn("nodes", result.graph_data)
        self.assertIn("edges", result.graph_data)


if __name__ == "__main__":
    unittest.main()
