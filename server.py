import os
import logging
import threading

from flask import Flask, jsonify, render_template, request

from app_state import lobby_clients, presence_store, room_store, rooms
from config import AI_WARMUP_ENABLED
from routes.ai import ai_bp
from routes.leaderboard import leaderboard_bp
from routes.lobby import lobby_bp
from routes.rooms import rooms_bp
from routes.single import single_bp
from utils.ai_utils import load_ai_policy_model, warm_ai_runtime
from utils.observability import assign_request_id, attach_request_id, configure_tracing

app = Flask(__name__)
logging.basicConfig(
    level=os.getenv("YACHT_LOG_LEVEL", "INFO"),
    format="%(message)s",
)
configure_tracing(app)

# --- Blueprint 등록 ---
app.register_blueprint(lobby_bp)
app.register_blueprint(ai_bp)
app.register_blueprint(leaderboard_bp)
app.register_blueprint(rooms_bp)
app.register_blueprint(single_bp)


@app.before_request
def set_request_context():
    assign_request_id()


# --- 캐시 미들웨어 ---
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


# --- 페이지 라우트 ---
@app.route("/")
def index():
    return render_template("lobby.html")


@app.route("/intro")
def intro():
    return render_template("intro.html")


@app.route("/game/single")
def game_single():
    return render_template("single-game.html")


@app.route("/game/multi")
def game_multi():
    return render_template("multi-game.html")


@app.route("/health", methods=["GET"])
def healthcheck():
    return jsonify({
        "status": "ok",
        "rooms": len(rooms),
        "room_backend": room_store.backend_name,
        "lobby_clients": len(lobby_clients),
        "presence_backend": presence_store.backend_name,
    })


# --- 시작 시 초기화 ---
load_ai_policy_model()
if AI_WARMUP_ENABLED:
    threading.Thread(target=warm_ai_runtime, daemon=True).start()


if __name__ == "__main__":
    host = os.getenv("YACHT_HOST", "0.0.0.0")
    port = int(os.getenv("YACHT_PORT", "8080"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    print(f"Yacht Game Server Running on Port {port}...")
    app.run(host=host, port=port, debug=debug)
