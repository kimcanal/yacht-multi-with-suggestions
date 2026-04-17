import secrets
import time

from flask import Blueprint, jsonify, request

from app_state import rooms
from config import TURN_TIME_LIMIT
from utils.room_utils import (
    default_room_state, finalize_room_forfeit, generate_room_code,
    prune_room_activity, remove_observer, remove_player, room_phase,
    touch_observer, touch_player,
)
from utils.validation import (
    is_valid_player, issue_player_token,
    normalize_dice, normalize_kept, normalize_username, safe_int,
)

rooms_bp = Blueprint("rooms", __name__)

_INVALID_USERNAME = "닉네임은 2~12자(한글/영문/숫자/_)만 가능합니다"


@rooms_bp.route("/api/rooms", methods=["GET"])
def list_rooms():
    now = time.time()
    for code, info in list(rooms.items()):
        prune_room_activity(code, info, now)
    return jsonify([
        {
            "code": code,
            "host": info["host"],
            "players": info["players"],
            "status": "full" if len(info["players"]) >= 2 else "waiting",
            "room_phase": room_phase(info),
            "observer_count": len(info.get("observers", [])),
        }
        for code, info in rooms.items()
        if info.get("players")
    ])


@rooms_bp.route("/api/rooms", methods=["POST"])
def create_room():
    username = normalize_username((request.json or {}).get("username"))
    if not username:
        return jsonify({"error": _INVALID_USERNAME}), 400

    code = generate_room_code()
    while code in rooms:
        code = generate_room_code()
    now = time.time()

    state = default_room_state()
    state["scores"][username] = [None] * 12
    state["player_dice"][username] = [1] * 5
    state["player_kept"][username] = [0] * 5
    state["player_rolls_left"][username] = 3
    state["turn"] = username
    state["players"] = [username]

    player_token = issue_player_token()
    rooms[code] = {
        "host": username,
        "players": [username],
        "observers": [],
        "player_tokens": {username: player_token},
        "state": state,
        "created_at": now,
        "last_update": now,
        "started_full": False,
        "player_last_seen": {username: now},
        "observer_last_seen": {},
    }
    return jsonify({"code": code, "players": rooms[code]["players"], "player_token": player_token})


@rooms_bp.route("/api/rooms/<code>/join", methods=["POST"])
def join_room(code):
    username = normalize_username((request.json or {}).get("username"))
    if not username:
        return jsonify({"error": _INVALID_USERNAME}), 400
    if code not in rooms:
        return jsonify({"error": "방 없음"}), 404

    now = time.time()
    room = prune_room_activity(code, rooms[code], now)
    if not room:
        return jsonify({"error": "방 없음"}), 404
    if username in room["players"]:
        return jsonify({"error": "이미 사용 중인 닉네임입니다"}), 409
    if len(room["players"]) >= 2:
        return jsonify({"error": "방이 가득 찼습니다"}), 409

    room["players"].append(username)
    player_token = issue_player_token()
    room.setdefault("player_tokens", {})[username] = player_token

    host, guest = room["players"][0], username
    state = default_room_state()
    state["scores"] = {host: [None] * 12, guest: [None] * 12}
    state["player_dice"] = {host: [1] * 5, guest: [1] * 5}
    state["player_kept"] = {host: [0] * 5, guest: [0] * 5}
    state["player_rolls_left"] = {host: 3, guest: 3}
    state["players"] = room["players"]
    state["turn"] = host
    state["turn_start_time"] = time.time()
    state["version"] = (room.get("state", {}).get("version", 0)) + 1
    state["updated_by"] = "system"

    room["state"] = state
    room["last_update"] = now
    room["started_full"] = True
    touch_player(room, username, now)

    return jsonify({
        "code": code,
        "players": room["players"],
        "state": room["state"],
        "observers": room.get("observers", []),
        "player_token": player_token,
    })


@rooms_bp.route("/api/rooms/<code>/observe", methods=["POST"])
def observe_room(code):
    username = normalize_username((request.json or {}).get("username"))
    if not username:
        return jsonify({"error": _INVALID_USERNAME}), 400
    if code not in rooms:
        return jsonify({"error": "방 없음"}), 404

    now = time.time()
    room = prune_room_activity(code, rooms[code], now)
    if not room:
        return jsonify({"error": "방 없음"}), 404
    if username in room["players"]:
        return jsonify({"error": "이미 플레이어입니다"}), 409

    if username not in room.get("observers", []):
        room.setdefault("observers", []).append(username)
    touch_observer(room, username, now)

    return jsonify({
        "code": code,
        "observers": room["observers"],
        "players": room["players"],
        "state": room["state"],
    })


@rooms_bp.route("/api/rooms/<code>", methods=["GET"])
def get_room(code):
    room = rooms.get(code)
    if not room:
        return jsonify({"error": "방 없음"}), 404

    now = time.time()
    u = request.args.get("u")
    pt = request.args.get("pt")
    if u and u in room.get("players", []) and is_valid_player(room, u, pt):
        touch_player(room, u, now)
    elif u and u in room.get("observers", []):
        touch_observer(room, u, now)

    room = prune_room_activity(code, room, now)
    if not room:
        return jsonify({"error": "방 없음"}), 404

    state = room.get("state", default_room_state())
    turn_left = None
    if state.get("turn_start_time"):
        turn_left = max(0, TURN_TIME_LIMIT - int(now - state["turn_start_time"]))

    state_payload = dict(state)
    state_payload["turn_left_seconds"] = turn_left

    since_version = safe_int(request.args.get("sv"))
    current_version = safe_int(state.get("version"), 0)
    p1 = room["host"]
    p2 = next((p for p in room["players"] if p != p1), None)

    payload = {
        "code": code,
        "host": room["host"],
        "players": room["players"],
        "observers": room.get("observers", []),
        "observer_count": len(room.get("observers", [])),
        "room_phase": room_phase(room),
        "state": state_payload,
        "player1": p1,
        "player2": p2,
    }

    if since_version is not None and since_version == current_version:
        payload["unchanged"] = True
        payload["state"] = {
            "version": current_version,
            "turn_left_seconds": turn_left,
            "turn": state.get("turn"),
            "game_over": state.get("game_over", False),
        }
    return jsonify(payload)


@rooms_bp.route("/api/rooms/<code>/heartbeat", methods=["POST"])
def heartbeat_room(code):
    room = rooms.get(code)
    if not room:
        return jsonify({"error": "방 없음"}), 404

    data = request.json or {}
    username = normalize_username(data.get("username"))
    player_token = data.get("player_token")
    now = time.time()

    if username in room.get("players", []):
        if not is_valid_player(room, username, player_token):
            return jsonify({"error": "참가자 인증 실패"}), 403
        touch_player(room, username, now)
    elif username in room.get("observers", []):
        touch_observer(room, username, now)
    else:
        return jsonify({"error": "참가자 없음"}), 404

    room = prune_room_activity(code, room, now)
    if not room:
        return jsonify({"error": "방 없음"}), 404

    return jsonify({
        "status": "ok",
        "room_phase": room_phase(room),
        "observer_count": len(room.get("observers", [])),
    })


@rooms_bp.route("/api/rooms/<code>/sync", methods=["POST"])
def sync_room(code):
    room = rooms.get(code)
    if not room:
        return jsonify({"error": "방 없음"}), 404

    data = request.json or {}
    username = normalize_username(data.get("username"))
    player_token = data.get("player_token")
    if username not in room["players"] or not is_valid_player(room, username, player_token):
        return jsonify({"error": "참가자 인증 실패"}), 403

    now = time.time()
    touch_player(room, username, now)
    room = prune_room_activity(code, room, now)
    if not room or username not in room.get("players", []):
        return jsonify({"error": "방 없음"}), 404

    state = room.get("state", default_room_state())
    if state.get("turn") and state["turn"] != username and not data.get("game_over"):
        return jsonify({"error": "상대 턴"}), 403

    dice = normalize_dice(data.get("dice", state["dice"]))
    kept = normalize_kept(data.get("kept", state["kept"]))
    if dice is None or kept is None:
        return jsonify({"error": "잘못된 주사위 데이터"}), 400

    rolls_left = data.get("rolls_left", state["rolls_left"])
    state.setdefault("player_dice", {})[username] = dice
    state.setdefault("player_kept", {})[username] = kept
    state.setdefault("player_rolls_left", {})[username] = rolls_left

    prev_turn = state.get("turn")
    new_turn = data.get("turn", state.get("turn"))
    turn_start_time = state.get("turn_start_time")
    if prev_turn != new_turn or (rolls_left == 3 and state.get("rolls_left") != 3):
        turn_start_time = time.time()

    is_game_over = data.get("game_over", state["game_over"])
    new_state = {
        "dice": dice,
        "kept": kept,
        "rolls_left": rolls_left,
        "scores": data.get("scores", state["scores"]),
        "player_dice": state.get("player_dice", {}),
        "player_kept": state.get("player_kept", {}),
        "player_rolls_left": state.get("player_rolls_left", {}),
        "turn": new_turn,
        "turn_start_time": turn_start_time,
        "game_over": is_game_over,
        "ai_rec": data.get("ai_rec", state.get("ai_rec")),
        "players": state.get("players", room["players"]),
        "version": state.get("version", 0) + 1,
        "updated_by": username,
        "winner": data.get("winner", state.get("winner")),
        "loser": data.get("loser", state.get("loser")),
        "end_reason": data.get("end_reason", state.get("end_reason")),
    }
    if not is_game_over:
        new_state["winner"] = None
        new_state["loser"] = None
        new_state["end_reason"] = None

    room["state"] = new_state
    room["last_update"] = now
    return jsonify({"state": new_state})


@rooms_bp.route("/api/rooms/<code>/roll", methods=["POST"])
def roll_dice(code):
    room = rooms.get(code)
    if not room:
        return jsonify({"error": "방 없음"}), 404

    data = request.json or {}
    username = normalize_username(data.get("username"))
    player_token = data.get("player_token")
    if username not in room["players"] or not is_valid_player(room, username, player_token):
        return jsonify({"error": "참가자 인증 실패"}), 403

    now = time.time()
    touch_player(room, username, now)
    room = prune_room_activity(code, room, now)
    if not room or username not in room.get("players", []):
        return jsonify({"error": "방 없음"}), 404

    state = room.get("state", default_room_state())
    if state.get("turn") and state["turn"] != username:
        return jsonify({"error": "상대 턴"}), 403

    rolls_left = state.get("rolls_left", 3)
    if rolls_left <= 0:
        return jsonify({"error": "남은 굴림 없음"}), 400

    kept = normalize_kept(data.get("kept", state["kept"]))
    if kept is None:
        return jsonify({"error": "잘못된 고정 주사위 데이터"}), 400

    new_dice = state["dice"][:]
    for i in range(5):
        if not kept[i]:
            new_dice[i] = secrets.randbelow(6) + 1

    state.setdefault("player_dice", {})[username] = new_dice
    state.setdefault("player_kept", {})[username] = kept
    state["dice"] = new_dice
    state["kept"] = kept
    state["rolls_left"] = rolls_left - 1
    state["version"] = state.get("version", 0) + 1
    state["turn_start_time"] = now

    room["state"] = state
    room["last_update"] = now
    return jsonify({"dice": new_dice, "rolls_left": state["rolls_left"], "state": state})


@rooms_bp.route("/api/rooms/<code>/leave", methods=["POST", "GET"])
def leave_room(code):
    room = rooms.get(code)
    if not room:
        return jsonify({"error": "방 없음"}), 404

    data = request.get_json(silent=True) or {}
    username = normalize_username(data.get("username") or request.args.get("username"))
    player_token = data.get("player_token") or request.args.get("pt")

    if username in room.get("players", []) and not is_valid_player(room, username, player_token):
        return jsonify({"error": "참가자 인증 실패"}), 403

    now = time.time()

    if username in room["players"]:
        remove_player(room, username, now)
        if room["players"]:
            winner = room["players"][0]
            finalize_room_forfeit(room, winner, username, updated_by="system_leave", now=now)
            return jsonify({"status": "left", "players": room["players"]})

    if username in room.get("observers", []):
        remove_observer(room, username, now)
        return jsonify({
            "status": "left",
            "players": room.get("players", []),
            "observers": room.get("observers", []),
        })

    if not room.get("players"):
        rooms.pop(code, None)

    return jsonify({"status": "left", "players": []})
