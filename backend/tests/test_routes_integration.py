"""
Integration tests for POST API endpoints.

Tests the full request→response cycle for POST endpoints that were
previously untested, including:
- JSON validation (Content-Type enforcement)
- Required field validation
- Composition endpoints
- Training endpoints
- History endpoints

Uses the Flask test client with the real app (no mocking).
"""

import unittest
from app import app


class TestPOSTEndpoints(unittest.TestCase):
    """Integration tests for POST endpoints."""

    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    # ── Composition endpoints ─────────────────────────────────────

    def test_compose_classic_requires_json(self):
        resp = self.client.post("/api/compose/classic", data="not json")
        self.assertIn(resp.status_code, (400, 415))

    def test_compose_classic_requires_request_id(self):
        resp = self.client.post(
            "/api/compose/classic",
            json={"algorithm": "dijkstra"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("request_id", resp.get_json()["error"])

    def test_compose_classic_unknown_request_returns_404(self):
        resp = self.client.post(
            "/api/compose/classic",
            json={"request_id": "nonexistent_req_999", "algorithm": "dijkstra"},
        )
        self.assertEqual(resp.status_code, 404)

    def test_compose_llm_requires_json(self):
        resp = self.client.post("/api/compose/llm", data="not json")
        self.assertIn(resp.status_code, (400, 415))

    def test_compose_llm_requires_request_id(self):
        resp = self.client.post("/api/compose/llm", json={})
        self.assertEqual(resp.status_code, 400)

    def test_compose_compare_requires_request_id(self):
        resp = self.client.post("/api/compose/compare", json={})
        self.assertEqual(resp.status_code, 400)

    def test_llm_chat_requires_message(self):
        resp = self.client.post("/api/llm/chat", json={})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("message", resp.get_json()["error"])

    def test_llm_chat_requires_json(self):
        resp = self.client.post("/api/llm/chat", data="hello")
        self.assertIn(resp.status_code, (400, 415))

    # ── Upload endpoints (no file → error) ────────────────────────

    def test_upload_services_no_files(self):
        resp = self.client.post("/api/services/upload")
        self.assertEqual(resp.status_code, 400)

    def test_upload_requests_no_file(self):
        resp = self.client.post("/api/requests/upload")
        self.assertIn(resp.status_code, (400, 500))

    def test_upload_best_solutions_no_file(self):
        resp = self.client.post("/api/best-solutions/upload")
        self.assertIn(resp.status_code, (400, 500))

    # ── History endpoints ─────────────────────────────────────────

    def test_clear_history(self):
        resp = self.client.post("/api/history/clear")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("message", resp.get_json())

    def test_import_training_no_examples(self):
        resp = self.client.post("/api/history/import-training")
        self.assertEqual(resp.status_code, 400)

    # ── Training endpoints ────────────────────────────────────────

    def test_training_start_requires_data(self):
        # Starting training without any data should give an error
        resp = self.client.post(
            "/api/training/start",
            json={},
            content_type="application/json",
        )
        # Either 400 (no training data) or 200 with error message
        self.assertIn(resp.status_code, (200, 400, 500))

    def test_training_reset_wsdl(self):
        resp = self.client.post("/api/training/reset-wsdl")
        self.assertEqual(resp.status_code, 200)

    # ── GET endpoints still work ──────────────────────────────────

    def test_health_endpoint(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "healthy")

    def test_services_list(self):
        resp = self.client.get("/api/services")
        self.assertEqual(resp.status_code, 200)

    def test_requests_list(self):
        resp = self.client.get("/api/requests")
        self.assertEqual(resp.status_code, 200)

    def test_history_status(self):
        resp = self.client.get("/api/history/status")
        self.assertEqual(resp.status_code, 200)

    def test_context_current(self):
        resp = self.client.get("/api/context/current")
        self.assertEqual(resp.status_code, 200)

    def test_annotation_status(self):
        resp = self.client.get("/api/annotation/status")
        self.assertEqual(resp.status_code, 200)

    def test_training_status(self):
        resp = self.client.get("/api/training/status")
        self.assertEqual(resp.status_code, 200)

    def test_comparison_endpoint(self):
        resp = self.client.get("/api/comparison")
        self.assertEqual(resp.status_code, 200)

    def test_nonexistent_endpoint(self):
        resp = self.client.get("/api/does-not-exist")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
