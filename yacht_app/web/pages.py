"""HTML pages and lightweight operational endpoints."""

from flask import Blueprint, jsonify, render_template

from app_state import get_services

pages_bp = Blueprint("pages", __name__)


@pages_bp.get("/")
def index():
    return render_template("lobby.html")


@pages_bp.get("/intro")
def intro():
    return render_template("intro.html")


@pages_bp.get("/game/single")
def game_single():
    return render_template("single-game.html")


@pages_bp.get("/game/multi")
def game_multi():
    return render_template("multi-game.html")


@pages_bp.get("/health")
def healthcheck():
    services = get_services()
    return jsonify({
        "status": "ok",
        "rooms": len(services.rooms),
        "room_backend": services.room_store.backend_name,
        "lobby_clients": len(services.presence),
        "presence_backend": services.presence_store.backend_name,
        "session_backend": services.single_sessions.backend_name,
        "result_backend": services.results.backend_name,
    })
