"""
Centralized configuration for the service composition system.

All configurable values are loaded from environment variables with sensible
defaults.  This avoids hardcoding URLs, model names, and limits in
multiple modules.
"""

import os

# ── Flask ──────────────────────────────────────────────────────────
FLASK_HOST = os.environ.get("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.environ.get("FLASK_PORT", "5000"))
FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "true").lower() in ("1", "true", "yes")

# ── Upload limits ──────────────────────────────────────────────────
MAX_UPLOAD_SIZE_MB = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "500"))
MAX_CONTENT_LENGTH = MAX_UPLOAD_SIZE_MB * 1024 * 1024  # bytes

# ── Ollama / LLM ──────────────────────────────────────────────────
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

# ── Interaction history persistence ───────────────────────────────
INTERACTION_HISTORY_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "interaction_history.json"
)

# ── Algorithm ─────────────────────────────────────────────────────
ALGORITHM_TIMEOUT = int(os.environ.get("ALGORITHM_TIMEOUT", "60"))

# ── SFT / Training defaults ──────────────────────────────────────
SFT_DEFAULT_MODEL = os.environ.get(
    "SFT_DEFAULT_MODEL", "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
)
SFT_OUTPUT_DIR = os.environ.get("SFT_OUTPUT_DIR", None)

# ── Security ───────────────────────────────────────────────────────
API_KEY = os.environ.get("API_KEY", None)  # None = no auth required (dev mode)
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "120"))

# ── CORS ──────────────────────────────────────────────────────────
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")

# ── Gunicorn / Production ─────────────────────────────────────────
GUNICORN_WORKERS = os.environ.get("GUNICORN_WORKERS", None)
GUNICORN_TIMEOUT = int(os.environ.get("GUNICORN_TIMEOUT", "300"))
