import hmac

import database
from flask import Blueprint, jsonify, request

from config import RESET_ADMIN_TOKEN
from utils.validation import normalize_username

leaderboard_bp = Blueprint("leaderboard", __name__)


@leaderboard_bp.route("/api/leaderboard", methods=["GET"])
def leaderboard():
    return jsonify(database.get_leaderboard())


@leaderboard_bp.route("/api/leaderboard/single", methods=["GET"])
def leaderboard_single_get():
    return jsonify(database.get_single_leaderboard())


@leaderboard_bp.route("/api/leaderboard/single", methods=["POST"])
def leaderboard_single_post():
    data = request.json or {}
    username = normalize_username(data.get("username"))
    try:
        score = int(data.get("score"))
    except (TypeError, ValueError):
        score = None
    if not username or score is None or score < 0 or score > 1000:
        return jsonify({"success": False, "error": "Invalid data"}), 400
    database.save_single_leaderboard(username, score)
    return jsonify({"success": True})


@leaderboard_bp.route("/api/leaderboard/multi", methods=["GET"])
def leaderboard_multi():
    return jsonify(database.get_leaderboard())


@leaderboard_bp.route("/api/leaderboard/recent", methods=["GET"])
def leaderboard_recent():
    raw_username = request.args.get("username")
    username = normalize_username(raw_username) if raw_username else None
    if raw_username and not username:
        return jsonify({"error": "Invalid username"}), 400

    limit = request.args.get("limit", 8)
    return jsonify(database.get_recent_games(limit=limit, username=username))


@leaderboard_bp.route("/api/leaderboard/users/<username>", methods=["GET"])
def leaderboard_user_profile(username):
    normalized_username = normalize_username(username)
    if not normalized_username:
        return jsonify({"error": "Invalid username"}), 400

    profile = database.get_user_profile(
        normalized_username,
        recent_limit=request.args.get("recent_limit", 5),
    )
    if not profile:
        return jsonify({"error": "사용자 없음"}), 404
    return jsonify(profile)


@leaderboard_bp.route("/api/leaderboard/reset", methods=["POST"])
def reset_leaderboard():
    admin_token = request.headers.get("X-Admin-Token", "")
    if not RESET_ADMIN_TOKEN:
        return jsonify({"error": "관리자 토큰이 설정되지 않았습니다"}), 503
    if not hmac.compare_digest(admin_token, RESET_ADMIN_TOKEN):
        return jsonify({"error": "권한 없음"}), 403
    database.reset_leaderboard()
    return jsonify({"status": "reset"})


@leaderboard_bp.route("/api/save-game", methods=["POST"])
def save_game():
    try:
        data = request.json or {}
        player1 = normalize_username(data.get("player1"))
        player2 = normalize_username(data.get("player2")) if data.get("player2") else None
        score1 = int(data.get("score1", 0))
        score2 = int(data.get("score2", 0))
        if not player1:
            return jsonify({"error": "player1 required"}), 400
        database.save_game_result(player1, score1, player2, score2)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
