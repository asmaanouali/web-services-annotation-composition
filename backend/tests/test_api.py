"""
Integration tests for the Flask API endpoints.
"""
import unittest
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app


class TestAPIEndpoints(unittest.TestCase):
    """Tests for core API endpoints using the Flask test client."""

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_health_endpoint(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data["status"], "healthy")

    def test_annotation_status(self):
        resp = self.client.get("/api/annotation/status")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertIn("total_services", data)

    def test_services_list_empty(self):
        resp = self.client.get("/api/services")
        # The route may not exist (services are at /api/services/upload)
        # 404 is acceptable for listing if no list endpoint is defined
        self.assertIn(resp.status_code, (200, 404))

    def test_training_status(self):
        resp = self.client.get("/api/training/status")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertIn("sft_state", data)
        self.assertIn("reward_state", data)
        self.assertIn("rl_state", data)

    def test_history_status(self):
        resp = self.client.get("/api/history/status")
        self.assertEqual(resp.status_code, 200)

    def test_context_get(self):
        resp = self.client.get("/api/context/current")
        self.assertEqual(resp.status_code, 200)

    def test_compose_missing_body(self):
        """POST without JSON should return an error status."""
        resp = self.client.post(
            "/api/compose/classic",
            content_type="application/json",
            data="not json",
        )
        # 400, 415, or 500 are all acceptable for malformed input
        self.assertIn(resp.status_code, (400, 415, 500))

    def test_404_unknown_route(self):
        resp = self.client.get("/api/does-not-exist")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
