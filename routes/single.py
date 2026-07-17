import time

from flask import Blueprint, jsonify, request

from app_state import single_sessions, single_sessions_lock
from utils.validation import normalize_kept, normalize_username, safe_int
from yacht_app.services.room_lifecycle import score_total
from yacht_app.services.single_sessions import (
    _get_session,
    _new_dice,
    _new_session,
    _prune_sessions,
    _public_state,
)
from yacht_engine import CATS, calc_score

single_bp = Blueprint("single", __name__)

_YACHT_IDX = CATS["Yacht"]


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
        single_sessions[session["id"]] = session

        return jsonify({
            "score": score,
            "bonus": bonus,
            "total_gain": score + bonus,
            "state": _public_state(session),
        })
