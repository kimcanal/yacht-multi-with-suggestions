"""Server-authoritative ranked single-session operations."""

import secrets
import time

from app_state import single_sessions, single_sessions_lock

SINGLE_SESSION_TTL_SECONDS = 60 * 60 * 4


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
        single_sessions[session_id] = session
        return True, None
