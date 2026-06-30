import secrets
import time

from flask import Blueprint, jsonify, request

from app_state import single_sessions, single_sessions_lock
from utils.room_utils import score_total
from utils.validation import normalize_kept, normalize_username, safe_int
from yacht_engine import CATS, calc_score

single_bp = Blueprint("single", __name__)

SINGLE_SESSION_TTL_SECONDS = 60 * 60 * 4
_YACHT_IDX = CATS["Yacht"]


def _new_dice():
    return [secrets.randbelow(6) + 1 for _ in range(5)]


def _new_session(username):
    now = time.time()
    return {
        "id": secrets.token_urlsafe(18),
        "token": secrets.token_urlsafe(24),
        "username": username,
        "dice": [1, 1, 1, 1, 1],
        "kept": [0, 0, 0, 0, 0],
        "rolls_left": 3,
        "scorecard": [None] * 12,
        "created_at": now,
        "updated_at": now,
        "finished": False,
        "final_score": None,
        "saved": False,
    }


def _public_state(session):
    return {
        "dice": session["dice"],
        "kept": session["kept"],
        "rolls_left": session["rolls_left"],
        "scorecard": session["scorecard"],
        "finished": session["finished"],
        "final_score": session["final_score"],
    }


def _prune_sessions(now=None):
    now = now or time.time()
    stale = [
        session_id for session_id, session in single_sessions.items()
        if now - session.get("updated_at", session.get("created_at", 0)) > SINGLE_SESSION_TTL_SECONDS
    ]
    for session_id in stale:
        single_sessions.pop(session_id, None)


def _get_session(data):
    session_id = data.get("session_id")
    session_token = data.get("session_token")
    if not session_id or not session_token:
        return None
    session = single_sessions.get(session_id)
    if not session or not secrets.compare_digest(session.get("token", ""), session_token):
        return None
    return session


def verify_ranked_single_session(username, score, session_id, session_token):
    with single_sessions_lock:
        session = single_sessions.get(session_id)
        if not session or not secrets.compare_digest(session.get("token", ""), session_token or ""):
            return False, "랭킹 세션 인증 실패"
        if session.get("username") != username:
            return False, "랭킹 세션 사용자와 닉네임이 다릅니다"
        if not session.get("finished"):
            return False, "완료되지 않은 싱글 세션입니다"
        if session.get("saved"):
            return False, "이미 저장된 싱글 기록입니다"
        if session.get("final_score") != score:
            return False, "최종 점수가 서버 세션과 다릅니다"
        session["saved"] = True
        session["updated_at"] = time.time()
        return True, None


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

        rolled = _new_dice()
        next_dice = session["dice"][:]
        for idx in range(5):
            if not kept[idx]:
                next_dice[idx] = rolled[idx]

        session["dice"] = next_dice
        session["kept"] = kept
        session["rolls_left"] -= 1
        session["updated_at"] = time.time()
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

        score = calc_score(session["dice"], category_idx)
        bonus = 0
        if (
            calc_score(session["dice"], _YACHT_IDX) == 50
            and isinstance(session["scorecard"][_YACHT_IDX], int)
            and session["scorecard"][_YACHT_IDX] >= 50
            and category_idx != _YACHT_IDX
            and score > 0
        ):
            session["scorecard"][_YACHT_IDX] += 100
            bonus = 100
        session["scorecard"][category_idx] = score

        finished = all(value is not None for value in session["scorecard"])
        session["dice"] = [1, 1, 1, 1, 1]
        session["kept"] = [0, 0, 0, 0, 0]
        session["rolls_left"] = 3
        session["finished"] = finished
        session["final_score"] = score_total(session["scorecard"]) if finished else None
        session["updated_at"] = time.time()

        return jsonify({
            "score": score,
            "bonus": bonus,
            "total_gain": score + bonus,
            "state": _public_state(session),
        })
