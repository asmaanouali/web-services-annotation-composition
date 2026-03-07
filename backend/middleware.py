"""
Security and rate-limiting middleware for the Flask application.

- **API Key authentication** — When ``API_KEY`` is set in the environment,
  every request must include the header ``X-API-Key: <key>``.
  If ``API_KEY`` is ``None`` (the default for local development), all
  requests are allowed through without authentication.

- **Rate limiting** — A lightweight, in-process sliding-window rate limiter
  keyed by client IP address.  Configurable via ``RATE_LIMIT_PER_MINUTE``.
"""

import time
import threading
from collections import defaultdict
from functools import wraps

from flask import request, jsonify, g

import config


# ── Rate-limiter state ─────────────────────────────────────────────

_hits: dict[str, list[float]] = defaultdict(list)
_lock = threading.Lock()


def _cleanup_old_hits(ip: str, window: float = 60.0) -> None:
    """Remove timestamps older than *window* seconds."""
    cutoff = time.monotonic() - window
    _hits[ip] = [t for t in _hits[ip] if t > cutoff]


# ── Public helpers ─────────────────────────────────────────────────

def check_api_key():
    """Before-request hook: reject unauthenticated requests when ``API_KEY``
    is configured.  The ``/api/health`` endpoint is always public."""
    api_key = config.API_KEY
    if api_key is None:
        return  # dev mode — no auth
    if request.path == "/api/health":
        return  # health-check is always public
    key = request.headers.get("X-API-Key", "")
    if key != api_key:
        return jsonify({"error": "Unauthorized – provide a valid X-API-Key header"}), 401


def check_rate_limit():
    """Before-request hook: enforce per-IP rate limiting."""
    rate_limit = config.RATE_LIMIT_PER_MINUTE
    if rate_limit <= 0:
        return  # disabled
    # Exempt lightweight polling endpoints from rate limiting
    if request.path in ("/api/annotate/progress", "/api/health"):
        return
    ip = request.remote_addr or "unknown"
    now = time.monotonic()
    with _lock:
        _cleanup_old_hits(ip)
        if len(_hits[ip]) >= rate_limit:
            return jsonify({
                "error": "Rate limit exceeded",
                "retry_after_seconds": 60,
            }), 429
        _hits[ip].append(now)


def register_security(app):
    """Register all security middleware on *app*.

    Call this once in the application factory, **after** CORS but
    **before** blueprint registration.
    """
    app.before_request(check_api_key)
    app.before_request(check_rate_limit)
