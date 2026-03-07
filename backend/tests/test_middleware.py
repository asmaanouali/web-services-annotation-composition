"""
Tests for security middleware — API key authentication, rate limiting.
"""

import unittest
from flask import Flask
from middleware import register_security, _hits, _lock


def _make_app(api_key=None, rate_limit=120):
    """Create a minimal Flask app with security middleware."""
    import config
    # Temporarily override config values
    original_key = config.API_KEY
    original_rate = config.RATE_LIMIT_PER_MINUTE
    config.API_KEY = api_key
    config.RATE_LIMIT_PER_MINUTE = rate_limit

    app = Flask(__name__)
    app.config["TESTING"] = True

    # Re-import to use updated config
    from middleware import check_api_key, check_rate_limit
    app.before_request(check_api_key)
    app.before_request(check_rate_limit)

    @app.route("/api/health")
    def health():
        return "ok"

    @app.route("/api/test")
    def test_endpoint():
        return "ok"

    # Restore config
    yield app
    config.API_KEY = original_key
    config.RATE_LIMIT_PER_MINUTE = original_rate


class TestAPIKeyAuth(unittest.TestCase):
    """API key authentication tests."""

    def test_no_key_configured_allows_all(self):
        """When API_KEY is None, all requests pass."""
        import config
        original = config.API_KEY
        config.API_KEY = None
        try:
            app = Flask(__name__)
            app.config["TESTING"] = True
            register_security(app)

            @app.route("/api/test")
            def handler():
                return "ok"

            with app.test_client() as c:
                resp = c.get("/api/test")
                self.assertEqual(resp.status_code, 200)
        finally:
            config.API_KEY = original

    def test_health_always_public(self):
        """Health endpoint is always accessible even with API key."""
        import config
        original = config.API_KEY
        config.API_KEY = "secret123"
        try:
            app = Flask(__name__)
            app.config["TESTING"] = True
            register_security(app)

            @app.route("/api/health")
            def health():
                return "ok"

            with app.test_client() as c:
                resp = c.get("/api/health")
                self.assertEqual(resp.status_code, 200)
        finally:
            config.API_KEY = original

    def test_missing_key_returns_401(self):
        """Requests without API key get 401 when key is configured."""
        import config
        original = config.API_KEY
        config.API_KEY = "mysecretkey"
        try:
            app = Flask(__name__)
            app.config["TESTING"] = True
            register_security(app)

            @app.route("/api/test")
            def handler():
                return "ok"

            with app.test_client() as c:
                resp = c.get("/api/test")
                self.assertEqual(resp.status_code, 401)
        finally:
            config.API_KEY = original

    def test_valid_key_passes(self):
        """Requests with correct API key pass."""
        import config
        original = config.API_KEY
        config.API_KEY = "mysecretkey"
        try:
            app = Flask(__name__)
            app.config["TESTING"] = True
            register_security(app)

            @app.route("/api/test")
            def handler():
                return "ok"

            with app.test_client() as c:
                resp = c.get("/api/test", headers={"X-API-Key": "mysecretkey"})
                self.assertEqual(resp.status_code, 200)
        finally:
            config.API_KEY = original

    def test_wrong_key_returns_401(self):
        """Requests with wrong API key get 401."""
        import config
        original = config.API_KEY
        config.API_KEY = "correct"
        try:
            app = Flask(__name__)
            app.config["TESTING"] = True
            register_security(app)

            @app.route("/api/test")
            def handler():
                return "ok"

            with app.test_client() as c:
                resp = c.get("/api/test", headers={"X-API-Key": "wrong"})
                self.assertEqual(resp.status_code, 401)
        finally:
            config.API_KEY = original


class TestRateLimiting(unittest.TestCase):
    """Rate limiting tests."""

    def setUp(self):
        # Clear rate limit state between tests
        with _lock:
            _hits.clear()

    def test_under_limit_passes(self):
        import config
        original_key = config.API_KEY
        original_rate = config.RATE_LIMIT_PER_MINUTE
        config.API_KEY = None
        config.RATE_LIMIT_PER_MINUTE = 10
        try:
            app = Flask(__name__)
            app.config["TESTING"] = True
            register_security(app)

            @app.route("/api/test")
            def handler():
                return "ok"

            with app.test_client() as c:
                for _ in range(5):
                    resp = c.get("/api/test")
                    self.assertEqual(resp.status_code, 200)
        finally:
            config.API_KEY = original_key
            config.RATE_LIMIT_PER_MINUTE = original_rate

    def test_over_limit_returns_429(self):
        import config
        original_key = config.API_KEY
        original_rate = config.RATE_LIMIT_PER_MINUTE
        config.API_KEY = None
        config.RATE_LIMIT_PER_MINUTE = 3
        try:
            app = Flask(__name__)
            app.config["TESTING"] = True
            register_security(app)

            @app.route("/api/test")
            def handler():
                return "ok"

            with app.test_client() as c:
                for _ in range(3):
                    c.get("/api/test")
                resp = c.get("/api/test")
                self.assertEqual(resp.status_code, 429)
        finally:
            config.API_KEY = original_key
            config.RATE_LIMIT_PER_MINUTE = original_rate

    def test_disabled_rate_limit(self):
        import config
        original_key = config.API_KEY
        original_rate = config.RATE_LIMIT_PER_MINUTE
        config.API_KEY = None
        config.RATE_LIMIT_PER_MINUTE = 0  # disabled
        try:
            app = Flask(__name__)
            app.config["TESTING"] = True
            register_security(app)

            @app.route("/api/test")
            def handler():
                return "ok"

            with app.test_client() as c:
                for _ in range(100):
                    resp = c.get("/api/test")
                    self.assertEqual(resp.status_code, 200)
        finally:
            config.API_KEY = original_key
            config.RATE_LIMIT_PER_MINUTE = original_rate


if __name__ == "__main__":
    unittest.main()
