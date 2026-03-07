"""
Tests for validators module — decorators, validation functions, and safe_route.
"""

import unittest
from unittest.mock import patch
from flask import Flask


class TestValidators(unittest.TestCase):
    """Unit tests for the ``validators`` module."""

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True

    # ── require_json ──────────────────────────────────────────────

    def test_require_json_rejects_non_json(self):
        from validators import require_json

        @self.app.route("/test", methods=["POST"])
        @require_json
        def _handler():
            return "ok"

        with self.app.test_client() as c:
            resp = c.post("/test", data="hello")
            self.assertEqual(resp.status_code, 400)
            self.assertIn("application/json", resp.get_json()["error"])

    def test_require_json_accepts_json(self):
        from validators import require_json

        @self.app.route("/test2", methods=["POST"])
        @require_json
        def _handler():
            return "ok"

        with self.app.test_client() as c:
            resp = c.post("/test2", json={"key": "value"})
            self.assertEqual(resp.status_code, 200)

    # ── require_fields ────────────────────────────────────────────

    def test_require_fields_missing(self):
        from validators import require_fields

        @self.app.route("/test3", methods=["POST"])
        @require_fields("name", "age")
        def _handler():
            return "ok"

        with self.app.test_client() as c:
            resp = c.post("/test3", json={"name": "Alice"})
            self.assertEqual(resp.status_code, 400)
            self.assertIn("age", resp.get_json()["error"])

    def test_require_fields_present(self):
        from validators import require_fields

        @self.app.route("/test4", methods=["POST"])
        @require_fields("name")
        def _handler():
            return "ok"

        with self.app.test_client() as c:
            resp = c.post("/test4", json={"name": "Alice"})
            self.assertEqual(resp.status_code, 200)

    def test_require_fields_empty_body(self):
        from validators import require_fields

        @self.app.route("/test5", methods=["POST"])
        @require_fields("x")
        def _handler():
            return "ok"

        with self.app.test_client() as c:
            resp = c.post("/test5", content_type="application/json")
            self.assertEqual(resp.status_code, 400)

    # ── require_files ─────────────────────────────────────────────

    def test_require_files_missing(self):
        from validators import require_files

        @self.app.route("/test6", methods=["POST"])
        @require_files("file")
        def _handler():
            return "ok"

        with self.app.test_client() as c:
            resp = c.post("/test6")
            self.assertEqual(resp.status_code, 400)
            self.assertIn("file", resp.get_json()["error"])

    # ── safe_route ────────────────────────────────────────────────

    def test_safe_route_catches_exception(self):
        from validators import safe_route

        @self.app.route("/test7", methods=["GET"])
        @safe_route
        def _handler():
            raise RuntimeError("boom")

        with self.app.test_client() as c:
            resp = c.get("/test7")
            self.assertEqual(resp.status_code, 500)
            self.assertIn("boom", resp.get_json()["error"])

    def test_safe_route_passes_through_normally(self):
        from validators import safe_route

        @self.app.route("/test8", methods=["GET"])
        @safe_route
        def _handler():
            return "ok"

        with self.app.test_client() as c:
            resp = c.get("/test8")
            self.assertEqual(resp.status_code, 200)

    # ── validate_algorithm ────────────────────────────────────────

    def test_validate_algorithm_valid(self):
        from validators import validate_algorithm
        with self.app.app_context():
            self.assertIsNone(validate_algorithm("dijkstra"))
            self.assertIsNone(validate_algorithm("astar"))
            self.assertIsNone(validate_algorithm("greedy"))

    def test_validate_algorithm_invalid(self):
        from validators import validate_algorithm
        with self.app.app_context():
            result = validate_algorithm("invalid_algo")
            self.assertIsNotNone(result)

    # ── validate_annotation_types ─────────────────────────────────

    def test_validate_annotation_types_valid(self):
        from validators import validate_annotation_types
        with self.app.app_context():
            self.assertIsNone(validate_annotation_types(["interaction", "context"]))

    def test_validate_annotation_types_invalid(self):
        from validators import validate_annotation_types
        with self.app.app_context():
            result = validate_annotation_types(["interaction", "invalid_type"])
            self.assertIsNotNone(result)

    # ── validate_rl_algorithm ─────────────────────────────────────

    def test_validate_rl_algorithm_valid(self):
        from validators import validate_rl_algorithm
        with self.app.app_context():
            self.assertIsNone(validate_rl_algorithm("GRPO"))
            self.assertIsNone(validate_rl_algorithm("PPO"))

    def test_validate_rl_algorithm_invalid(self):
        from validators import validate_rl_algorithm
        with self.app.app_context():
            result = validate_rl_algorithm("DQN")
            self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
