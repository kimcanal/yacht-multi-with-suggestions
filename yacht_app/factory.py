"""Flask application factory."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from flask import Flask, request

from config import AI_WARMUP_ENABLED
from routes.ai import ai_bp
from routes.leaderboard import leaderboard_bp
from routes.lobby import lobby_bp
from routes.rooms import rooms_bp
from routes.single import single_bp
from utils.ai_utils import load_ai_policy_model, warm_ai_runtime
from yacht_app.container import AppServices, create_services
from yacht_app.infra.observability import assign_request_id, attach_request_id, configure_tracing
from yacht_app.web.pages import pages_bp

ROOT = Path(__file__).resolve().parents[1]


def create_app(
    config_overrides: dict | None = None,
    *,
    services: AppServices | None = None,
    initialize_runtime: bool = True,
) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(ROOT / "templates"),
        static_folder=str(ROOT / "static"),
    )
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
            load_ai_policy_model()
            if AI_WARMUP_ENABLED:
                threading.Thread(target=warm_ai_runtime, daemon=True).start()

    return app
