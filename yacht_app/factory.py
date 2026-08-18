"""Flask application factory."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from flask import Flask, request
from werkzeug.middleware.proxy_fix import ProxyFix

from config import AI_WARMUP_ENABLED, TRUSTED_PROXY_HOPS
from routes.ai import ai_bp
from routes.leaderboard import leaderboard_bp
from routes.lobby import lobby_bp
from routes.rooms import rooms_bp
from routes.single import single_bp
from utils.ai_utils import warm_ai_runtime
from yacht_app.container import AppServices, create_services
from yacht_app.infra.observability import assign_request_id, attach_request_id, configure_tracing
from yacht_app.web.pages import pages_bp

ROOT = Path(__file__).resolve().parents[1]


def _validate_runtime_configuration():
    """Fail fast when a multi-worker deployment would split mutable state."""
    workers = int(os.getenv("GUNICORN_WORKERS", "1"))
    room_backend = os.getenv("YACHT_ROOM_BACKEND", "memory").strip().lower()
    result_backend = os.getenv("YACHT_RESULT_BACKEND", "json").strip().lower()
    if workers <= 1:
        return
    if room_backend != "redis":
        raise RuntimeError("GUNICORN_WORKERS > 1 requires YACHT_ROOM_BACKEND=redis")
    if result_backend != "sqlite":
        raise RuntimeError("GUNICORN_WORKERS > 1 requires YACHT_RESULT_BACKEND=sqlite")


def create_app(
    config_overrides: dict | None = None,
    *,
    services: AppServices | None = None,
    initialize_runtime: bool = True,
) -> Flask:
    _validate_runtime_configuration()
    app = Flask(
        __name__,
        template_folder=str(ROOT / "templates"),
        static_folder=str(ROOT / "static"),
    )
    if TRUSTED_PROXY_HOPS:
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=TRUSTED_PROXY_HOPS,
            x_proto=TRUSTED_PROXY_HOPS,
            x_host=TRUSTED_PROXY_HOPS,
        )
    app.config.setdefault("MAX_CONTENT_LENGTH", int(os.getenv("YACHT_MAX_REQUEST_BYTES", "32768")))
    if config_overrides:
        app.config.update(config_overrides)

    # Each factory call owns its mutable state unless the caller explicitly
    # injects a shared container. This keeps tests and multiple app instances
    # isolated while still allowing the process entrypoint to opt into the
    # backward-compatible global services.
    app.extensions["yacht_services"] = services if services is not None else create_services()
    logging.basicConfig(
        level=os.getenv("YACHT_LOG_LEVEL", "INFO"),
        format="%(message)s",
    )
    configure_tracing(app)

    for blueprint in (pages_bp, lobby_bp, ai_bp, leaderboard_bp, rooms_bp, single_bp):
        app.register_blueprint(blueprint)

    @app.before_request
    def set_request_context():
        assign_request_id()

    @app.after_request
    def add_cache_headers(response):
        attach_request_id(response)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'self'; object-src 'none'; "
            "frame-ancestors 'none'; form-action 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com; "
            "script-src 'self' 'unsafe-inline'; connect-src 'self'",
        )
        if request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=86400, immutable"
            response.headers.pop("Pragma", None)
            response.headers.pop("Expires", None)
        elif request.path.startswith("/api/"):
            if response.mimetype == "text/event-stream":
                response.headers["Cache-Control"] = "no-cache"
                response.headers.pop("Pragma", None)
                response.headers.pop("Expires", None)
            else:
                response.headers["Cache-Control"] = "no-store, private"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
        else:
            response.headers["Cache-Control"] = "no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    if initialize_runtime:
        with app.app_context():
            if AI_WARMUP_ENABLED:
                threading.Thread(target=warm_ai_runtime, daemon=True).start()

    return app
