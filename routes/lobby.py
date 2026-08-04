import time

import psutil
from flask import Blueprint, jsonify, request

from app_state import get_services, lobby_clients, rooms
from config import CLIENT_TIMEOUT, SYSTEM_STATUS_CACHE_SECONDS
from utils.ai_utils import CPU_MODEL, ai_metrics_snapshot
from utils.validation import normalize_username

lobby_bp = Blueprint("lobby", __name__)
def _online_users_payload(now=None):
    now = now or time.time()
    lobby = {
        info["username"]: {"status": "대기중"}
        for _, info in lobby_clients.items()
        if isinstance(info, dict)
        and now - info["last_seen"] <= CLIENT_TIMEOUT
        and info.get("username")
    }
    playing = {
        player: {"status": "게임중", "room": code}
        for code, room in rooms.items()
        for player in room.get("players", [])
        if player
    }
    return [
        {"username": username, "status": meta["status"], **({} if "room" not in meta else {"room": meta["room"]})}
        for username, meta in {**lobby, **playing}.items()
    ]


def _room_list_payload():
    # Import lazily to avoid a blueprint import cycle while reusing the exact
    # same pruning, expiry, locking, and payload rules as GET /api/rooms.
    from routes.rooms import active_room_summaries

    return active_room_summaries()


def _system_status_payload():
    now = time.time()
    services = get_services()
    with services.system_status_lock:
        cached = services.system_status_cache.get("current")
        if cached and now - cached["created_at"] < SYSTEM_STATUS_CACHE_SECONDS:
            return cached["payload"]

    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    stale = []
    active_count = 0
    for client_id, info in lobby_clients.items():
        try:
            last_seen = info["last_seen"] if isinstance(info, dict) else info
            if now - last_seen <= CLIENT_TIMEOUT:
                active_count += 1
            else:
                stale.append(client_id)
        except Exception:
            stale.append(client_id)
    for client_id in stale:
        lobby_clients.pop(client_id, None)

    payload = {
        "cpu_model": CPU_MODEL,
        "cpu_percent": round(cpu_percent, 1),
        "memory_percent": round(memory.percent, 1),
        "memory_used_gb": round(memory.used / (1024 ** 3), 2),
        "memory_total_gb": round(memory.total / (1024 ** 3), 2),
        "online_count": active_count,
        "active_rooms": len(rooms),
    }
    payload.update(ai_metrics_snapshot())
    with services.system_status_lock:
        services.system_status_cache["current"] = {"created_at": now, "payload": payload}
    return payload


@lobby_bp.route("/api/lobby-heartbeat", methods=["POST"])
def lobby_heartbeat():
    try:
        data = request.json or {}
        client_id = (data.get("client_id") or "")[:64]
        username = normalize_username(data.get("username")) or "익명"

        if not client_id:
            return jsonify({"error": "client_id required"}), 400

        now = time.time()
        lobby_clients[client_id] = {"last_seen": now, "username": username}

        # 만료된 클라이언트 정리
        stale = [
            cid for cid, info in lobby_clients.items()
            if now - (info["last_seen"] if isinstance(info, dict) else info) > CLIENT_TIMEOUT
        ]
        for cid in stale:
            del lobby_clients[cid]

        return jsonify({"status": "ok", "active_clients": len(lobby_clients)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@lobby_bp.route("/api/online-users", methods=["GET"])
def online_users():
    return jsonify(_online_users_payload())


@lobby_bp.route("/api/lobby-users", methods=["GET"])
def lobby_users():
    """구버전 호환성 유지용."""
    now = time.time()
    users = [
        {"client_id": cid, "username": info.get("username", "익명")}
        for cid, info in lobby_clients.items()
        if isinstance(info, dict) and now - info["last_seen"] <= CLIENT_TIMEOUT
    ]
    return jsonify(users)


@lobby_bp.route("/api/system-status")
def system_status():
    try:
        return jsonify(_system_status_payload())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@lobby_bp.route("/api/lobby-snapshot")
def lobby_snapshot():
    """One response for the lobby's recurring read-only dashboard refresh."""
    try:
        rank_mode = request.args.get("rank_mode", "multi")
        profile_username = normalize_username(request.args.get("profile"))
        results = get_services().results
        if rank_mode == "single":
            leaderboard = results.get_single_leaderboard()
            recent_games = results.get_recent_games(limit=6)
        elif rank_mode == "bot":
            leaderboard = results.get_bot_leaderboard()
            recent_games = results.get_recent_bot_games(limit=6)
        else:
            leaderboard = results.get_leaderboard()
            recent_games = results.get_recent_games(limit=6)
        room_summaries = _room_list_payload()
        online_users = _online_users_payload()
        return jsonify({
            "online_users": online_users,
            "rooms": room_summaries,
            "leaderboard": leaderboard,
            "recent_games": recent_games,
            "system": _system_status_payload(),
            "profile": results.get_user_profile(profile_username, recent_limit=5) if profile_username else None,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
