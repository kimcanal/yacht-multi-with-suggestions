import time

from flask import Blueprint, jsonify, request

from app_state import get_services, single_sessions, single_sessions_lock
from utils.validation import normalize_kept, normalize_username, safe_int
from yacht_app.services import vs_ai
from yacht_app.services.room_lifecycle import score_total
from yacht_app.services.single_sessions import (
    _get_session,
    _new_dice,
    _new_session,
    _prune_sessions,
    _public_state,
    new_bot_match,
)
from yacht_core.simulation import apply_score

single_bp = Blueprint("single", __name__)


@single_bp.route("/api/v1/vs-ai/sessions", methods=["POST"])
def create_vs_ai_session():
    data = request.json or {}
    username = normalize_username(data.get("username"))
    if not username:
        return jsonify({"error": "유효한 닉네임이 필요합니다"}), 400
    if data.get("policy_mode") not in (None, "exact_memo"):
        return jsonify({"error": "MLP 정책은 더 이상 지원하지 않습니다"}), 400
    with single_sessions_lock:
        _prune_sessions()
        session = vs_ai.new_session(username)
        single_sessions[session["id"]] = session
    payload = {
        "session_id": session["id"],
        "session_token": session["token"],
        "state": vs_ai.public_state(session),
    }
    return jsonify(payload), 201


def _vs_ai_session_from_request(session_id, data):
    username = normalize_username(data.get("username"))
    if not username:
        return None, None, "유효한 닉네임이 필요합니다"
    session = single_sessions.get(session_id)
    error = vs_ai.authenticate(session, username, data.get("session_token"))
    return session, username, error


@single_bp.route("/api/v1/vs-ai/sessions/<session_id>", methods=["GET"])
def get_vs_ai_session(session_id):
    data = {
        "username": request.args.get("username"),
        "session_token": request.headers.get("X-VS-AI-Token"),
    }
    with single_sessions_lock:
        session, _username, error = _vs_ai_session_from_request(session_id, data)
        if error:
            return jsonify({"error": error}), 403
        return jsonify({"state": vs_ai.public_state(session)})


@single_bp.route("/api/v1/vs-ai/sessions/<session_id>/roll", methods=["POST"])
def roll_vs_ai_session(session_id):
    data = request.json or {}
    kept = normalize_kept(data.get("kept"))
    if kept is None:
        return jsonify({"error": "잘못된 고정 주사위 데이터"}), 400
    with single_sessions_lock:
        session, _username, error = _vs_ai_session_from_request(session_id, data)
        if error:
            return jsonify({"error": error}), 403
        try:
            vs_ai.roll_player(session, kept)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 409
        single_sessions[session_id] = session
        return jsonify({"state": vs_ai.public_state(session)})


@single_bp.route("/api/v1/vs-ai/sessions/<session_id>/score", methods=["POST"])
def score_vs_ai_session(session_id):
    data = request.json or {}
    category_idx = safe_int(data.get("category_idx"))
    if category_idx is None:
        return jsonify({"error": "잘못된 점수칸입니다"}), 400
    with single_sessions_lock:
        session, username, error = _vs_ai_session_from_request(session_id, data)
        if error:
            return jsonify({"error": error}), 403
        try:
            score, bonus = vs_ai.score_player(session, category_idx)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 409
        if session["finished"] and not session["result_saved"]:
            get_services().results.save_bot_game_result(
                username,
                session["final_score"],
                session["bot_final_score"],
                session["policy_mode"],
                session_id,
                verified=True,
            )
            session["result_saved"] = True
        single_sessions[session_id] = session
        return jsonify({
            "score": score,
            "bonus": bonus,
            "total_gain": score + bonus,
            "state": vs_ai.public_state(session),
        })


@single_bp.route("/api/single/vs-ai/start", methods=["POST"])
def start_bot_match():
    """Issue a one-time token for a VS-AI practice-board submission."""
    data = request.json or {}
    username = normalize_username(data.get("username"))
    if not username:
        return jsonify({"error": "유효한 닉네임이 필요합니다"}), 400
    if data.get("policy_mode") not in (None, "exact_memo"):
        return jsonify({"error": "MLP 정책은 더 이상 지원하지 않습니다"}), 400

    with single_sessions_lock:
        _prune_sessions()
        match = new_bot_match(username)
        single_sessions[match["id"]] = match
    payload = {
        "match_id": match["id"],
        "match_token": match["token"],
        "verified": False,
    }
    return jsonify(payload)

@single_bp.route("/api/single/start", methods=["POST"])
def start_single_session():
    data = request.json or {}
    username = normalize_username(data.get("username"))
    mode = data.get("mode")
    coach_enabled = data.get("coach_enabled")
    if not username:
        return jsonify({"error": "유효한 닉네임이 필요합니다"}), 400
    if mode != "solo" or coach_enabled is not False:
        return jsonify({"error": "랭킹 세션은 솔로/AI 코치 OFF에서만 생성됩니다"}), 400

    with single_sessions_lock:
        _prune_sessions()
        session = _new_session(username)
        single_sessions[session["id"]] = session
        return jsonify({
            "session_id": session["id"],
            "session_token": session["token"],
            "state": _public_state(session),
        })


@single_bp.route("/api/single/roll", methods=["POST"])
def roll_single_session():
    data = request.json or {}
    with single_sessions_lock:
        session = _get_session(data)
        if not session:
            return jsonify({"error": "랭킹 세션 인증 실패"}), 403
        if session.get("finished"):
            return jsonify({"error": "이미 종료된 싱글 세션입니다"}), 409
        if session["rolls_left"] <= 0:
            return jsonify({"error": "남은 굴림 없음"}), 400

        kept = normalize_kept(data.get("kept", session["kept"]))
        if kept is None:
            return jsonify({"error": "잘못된 고정 주사위 데이터"}), 400
        # 첫 굴림 전의 [1, 1, 1, 1, 1]은 표시용 초기값일 뿐이다. 클라이언트가
        # 임의 KEEP으로 이를 보존해 첫 손패를 조작하지 못하게 항상 전부 굴린다.
        if session["rolls_left"] == 3:
            kept = [0, 0, 0, 0, 0]

        rolled = _new_dice()
        next_dice = session["dice"][:]
        for idx in range(5):
            if not kept[idx]:
                next_dice[idx] = rolled[idx]

        session["dice"] = next_dice
        session["kept"] = kept
        session["rolls_left"] -= 1
        session["updated_at"] = time.time()
        single_sessions[session["id"]] = session
        return jsonify({"state": _public_state(session)})


@single_bp.route("/api/single/score", methods=["POST"])
def score_single_session():
    data = request.json or {}
    with single_sessions_lock:
        session = _get_session(data)
        if not session:
            return jsonify({"error": "랭킹 세션 인증 실패"}), 403
        if session.get("finished"):
            return jsonify({"error": "이미 종료된 싱글 세션입니다"}), 409
        if session["rolls_left"] >= 3:
            return jsonify({"error": "점수 기록 전에는 최소 1회 굴려야 합니다"}), 400

        category_idx = safe_int(data.get("category_idx"))
        if category_idx is None or category_idx < 0 or category_idx >= 12:
            return jsonify({"error": "잘못된 점수칸입니다"}), 400
        if session["scorecard"][category_idx] is not None:
            return jsonify({"error": "이미 기록된 점수칸입니다"}), 409

        score, bonus = apply_score(session["dice"], session["scorecard"], category_idx)

        finished = all(value is not None for value in session["scorecard"])
        session["dice"] = [1, 1, 1, 1, 1]
        session["kept"] = [0, 0, 0, 0, 0]
        session["rolls_left"] = 3
        session["finished"] = finished
        session["final_score"] = score_total(session["scorecard"]) if finished else None
        session["updated_at"] = time.time()
        single_sessions[session["id"]] = session

        return jsonify({
            "score": score,
            "bonus": bonus,
            "total_gain": score + bonus,
            "state": _public_state(session),
        })
