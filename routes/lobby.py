import time

import psutil
from flask import Blueprint, jsonify, request

from app_state import lobby_clients, rooms
from config import CLIENT_TIMEOUT
from utils.ai_utils import CPU_MODEL, ai_metrics_snapshot
from utils.validation import normalize_username

lobby_bp = Blueprint("lobby", __name__)


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
    now = time.time()

    # 로비 대기중 유저
    lobby = {
        info["username"]: {"status": "대기중"}
        for cid, info in lobby_clients.items()
        if isinstance(info, dict)
        and now - info["last_seen"] <= CLIENT_TIMEOUT
        and info.get("username")
    }

    # 게임중 유저
    playing = {
        p: {"status": "게임중", "room": code}
        for code, room in rooms.items()
        for p in room.get("players", [])
        if p
    }

    # 게임중 상태가 대기중보다 우선
    merged = {**lobby, **playing}
    result = [
        {"username": uname, "status": meta["status"],
         **({} if "room" not in meta else {"room": meta["room"]})}
        for uname, meta in merged.items()
    ]
    return jsonify(result)


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
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()

        now = time.time()
        stale = []
        active_count = 0
        for cid, info in lobby_clients.items():
            try:
                last_seen = info["last_seen"] if isinstance(info, dict) else info
                if now - last_seen <= CLIENT_TIMEOUT:
                    active_count += 1
                else:
                    stale.append(cid)
            except Exception:
                stale.append(cid)
        for cid in stale:
            lobby_clients.pop(cid, None)

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
        return jsonify(payload)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
