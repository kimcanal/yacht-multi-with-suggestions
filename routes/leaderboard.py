import hmac

from flask import Blueprint, jsonify, request

from app_state import get_services
from config import RESET_ADMIN_TOKEN
from utils.validation import normalize_username, safe_int
from yacht_app.services.single_sessions import verify_ranked_single_session

leaderboard_bp = Blueprint("leaderboard", __name__)


@leaderboard_bp.route("/api/leaderboard", methods=["GET"])
def leaderboard():
    return jsonify(get_services().results.get_leaderboard())


@leaderboard_bp.route("/api/leaderboard/single", methods=["GET"])
def leaderboard_single_get():
    return jsonify(get_services().results.get_single_leaderboard())


@leaderboard_bp.route("/api/leaderboard/single", methods=["POST"])
def leaderboard_single_post():
    data = request.json or {}
    username = normalize_username(data.get("username"))
    score = safe_int(data.get("score"))
    mode = data.get("mode")
    coach_enabled = data.get("coach_enabled")
    if not username or score is None or score < 0 or score > 1000:
        return jsonify({"success": False, "error": "Invalid data"}), 400
    if mode != "solo" or coach_enabled is not False:
        return jsonify({
            "success": False,
            "error": "싱글 랭킹은 솔로/AI 코치 OFF 기록만 저장됩니다",
        }), 403
    verified, error = verify_ranked_single_session(
        username,
        score,
        data.get("session_id"),
        data.get("session_token"),
    )
    if not verified:
        return jsonify({"success": False, "error": error}), 403
    get_services().results.save_single_leaderboard(username, score)
    return jsonify({"success": True})


@leaderboard_bp.route("/api/leaderboard/multi", methods=["GET"])
def leaderboard_multi():
    return jsonify(get_services().results.get_leaderboard())


@leaderboard_bp.route("/api/leaderboard/recent", methods=["GET"])
def leaderboard_recent():
    raw_username = request.args.get("username")
    username = normalize_username(raw_username) if raw_username else None
    if raw_username and not username:
        return jsonify({"error": "Invalid username"}), 400

    limit = request.args.get("limit", 8)
    return jsonify(get_services().results.get_recent_games(limit=limit, username=username))


@leaderboard_bp.route("/api/leaderboard/users/<username>", methods=["GET"])
def leaderboard_user_profile(username):
    normalized_username = normalize_username(username)
    if not normalized_username:
        return jsonify({"error": "Invalid username"}), 400

    profile = get_services().results.get_user_profile(
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
    get_services().results.reset_leaderboard()
    return jsonify({"status": "reset"})


@leaderboard_bp.route("/api/save-game", methods=["POST"])
def save_game():
    return jsonify({
        "error": "deprecated",
        "message": "멀티 결과는 방 상태 검증 후 서버에서 자동 저장됩니다.",
    }), 410
