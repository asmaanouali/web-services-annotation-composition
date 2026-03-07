"""
Flask API for the Intelligent Web Service Composition System.

Thin application factory — all route handlers live in the ``routes`` package,
shared state in ``state``, configuration in ``config``, and reusable helpers in
``helpers`` / ``validators``.
"""

from flask import Flask
from flask_cors import CORS

from config import MAX_CONTENT_LENGTH, FLASK_HOST, FLASK_PORT, FLASK_DEBUG, CORS_ORIGINS
from middleware import register_security
from routes import all_blueprints

# ── Application factory ───────────────────────────────────────────

app = Flask(__name__)
CORS(app, origins=CORS_ORIGINS.split(","))

# Security: cap upload size (was previously unlimited)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# Security middleware (API key + rate limiting)
register_security(app)

# Register every Blueprint defined in the routes package
for bp in all_blueprints:
    app.register_blueprint(bp)


if __name__ == "__main__":
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG, use_reloader=False)
