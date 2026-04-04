"""
Optimised Flask dev-server runner with generous upload and timeout settings.
"""

from app import app
from config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG
from werkzeug.serving import WSGIRequestHandler

# Use persistent HTTP/1.1 connections
WSGIRequestHandler.protocol_version = "HTTP/1.1"

if __name__ == "__main__":
    print("=" * 60)
    print("Starting Flask server (development mode)")
    print("=" * 60)
    print(f"  Host           : {FLASK_HOST}")
    print(f"  Port           : {FLASK_PORT}")
    print(f"  Debug          : {FLASK_DEBUG}")
    print(f"  Multi-threading: enabled")
    print("=" * 60)
    print()

    app.run(
        host=FLASK_HOST,
        port=FLASK_PORT,
        debug=FLASK_DEBUG,
        threaded=True,
        use_reloader=False,
        request_handler=WSGIRequestHandler,
    )