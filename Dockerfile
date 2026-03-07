# ============================================================
# Multi-stage Dockerfile for the Intelligent Web Service
# Composition System (QSRT).
#
# Stage 1 – Python backend (Flask/Gunicorn)
# Stage 2 – Lightweight Nginx for the static frontend
# ============================================================

# ── BACKEND ─────────────────────────────────────────────────
FROM python:3.11-slim AS backend

WORKDIR /app

# System deps needed for lxml (libxml2, libxslt)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential libxml2-dev libxslt1-dev && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY backend/ .

# Non-root user for security
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')"

CMD ["gunicorn", "-c", "gunicorn_config.py", "app:app"]

# ── FRONTEND ────────────────────────────────────────────────
FROM nginx:1.25-alpine AS frontend

COPY frontend/ /usr/share/nginx/html/

# Simple reverse-proxy config so /api/* goes to the backend
RUN printf 'server {\n\
    listen 80;\n\
    location / {\n\
        root /usr/share/nginx/html;\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
    location /api/ {\n\
        proxy_pass http://backend:5000;\n\
        proxy_set_header Host $host;\n\
        proxy_set_header X-Real-IP $remote_addr;\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s CMD wget -qO- http://localhost/ || exit 1
