import multiprocessing
import os


bind = f"{os.getenv('YACHT_HOST', '0.0.0.0')}:{os.getenv('YACHT_PORT', '8080')}"
worker_class = "gthread"
workers = int(os.getenv("GUNICORN_WORKERS", max(2, multiprocessing.cpu_count() // 2)))
threads = int(os.getenv("GUNICORN_THREADS", "4"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "30"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))
accesslog = "-"
errorlog = "-"
capture_output = True
