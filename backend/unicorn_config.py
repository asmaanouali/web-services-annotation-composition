"""
Configuration Gunicorn pour uploads massifs
"""

import multiprocessing

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 0  # Timeout infini pour uploads volumineux
keepalive = 5

# Limits (AUCUNE LIMITE)
limit_request_line = 0  # Illimité
limit_request_fields = 32768
limit_request_field_size = 0  # Illimité

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = "service_composer"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (si nécessaire)
keyfile = None
certfile = None