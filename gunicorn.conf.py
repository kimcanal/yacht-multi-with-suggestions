import os

bind = f"{os.getenv('YACHT_HOST', '0.0.0.0')}:{os.getenv('YACHT_PORT', '8080')}"
worker_class = "gthread"
# A single worker is safe for the in-memory development backend.  The app
# refuses multi-worker startup unless Redis rooms and SQLite results are set.
workers = int(os.getenv("GUNICORN_WORKERS", "1"))
threads = int(os.getenv("GUNICORN_THREADS", "4"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "30"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))
accesslog = "-"
errorlog = "-"
capture_output = True
