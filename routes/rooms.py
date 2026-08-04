import secrets
import time
from contextlib import nullcontext

from flask import Blueprint, Response, jsonify, request, stream_with_context

from app_state import get_services, rooms
from config import TURN_TIME_LIMIT
from utils.validation import (
    is_valid_player,
    issue_player_token,
    normalize_dice,
    normalize_kept,
    normalize_rolls_left,
    normalize_scores_by_players,
    normalize_username,
    safe_int,
)
from yacht_app.services.room_game import (
    finish_room_if_complete,
    rematch_payload,
    room_event_payload,
    sse_event,
    validate_sync_transition,
)
from yacht_app.services.room_lifecycle import (
    advance_expired_turn,
    build_fair_state,
    default_room_state,
    finalize_room_forfeit,
    generate_room_code,
    prune_room_activity,
    record_room_score,
    remove_observer,
    remove_player,
    roll_room_dice,
    room_phase,
    score_total,
    start_room_rematch,
    touch_observer,
    touch_player,
)

rooms_bp = Blueprint("rooms", __name__)

_INVALID_USERNAME = "닉네임은 2~12자(한글/영문/숫자/_)만 가능합니다"
_REACTION_HISTORY_LIMIT = 24
_REACTION_COOLDOWN_SECONDS = 2.0
_REACTIONS = {
    "nice": {"emoji": "👍", "label": "나이스", "asset": "/static/assets/openmoji/1F44D.svg"},
    "fire": {"emoji": "🔥", "label": "대박", "asset": "/static/assets/openmoji/1F525.svg"},
    "laugh": {"emoji": "😂", "label": "ㅋㅋ", "asset": "/static/assets/openmoji/1F602.svg"},
    "wow": {"emoji": "😱", "label": "헉", "asset": "/static/assets/openmoji/1F631.svg"},
    "dice": {"emoji": "🎲", "label": "가자", "asset": "/static/assets/openmoji/1F3B2.svg"},
    "gg": {"emoji": "👏", "label": "GG", "asset": "/static/assets/openmoji/1F44F.svg"},
}
def _recent_reactions(room):
    return list(room.get("reactions", []))[-_REACTION_HISTORY_LIMIT:]


def _reactions_after(reactions, last_reaction_id):
    if not last_reaction_id:
        return list(reactions)
    for index, reaction in enumerate(reactions):
        if reaction.get("id") == last_reaction_id:
            return list(reactions[index + 1:])
    return list(reactions[-1:])


def _save_room(code, room):
    if room:
        rooms.save(code, room) if hasattr(rooms, "save") else rooms.__setitem__(code, room)


def _save_room_if_absent(code, room):
    if hasattr(rooms, "save_if_absent"):
        return rooms.save_if_absent(code, room)
    if code in rooms:
        return False
    rooms[code] = room
    return True


def _delete_room(code):
    rooms.delete(code) if hasattr(rooms, "delete") else rooms.pop(code, None)


def _room_lock(code):
    return rooms.lock(code) if hasattr(rooms, "lock") else nullcontext()


def _advance_expired_turn_if_needed(code, room, now):
    event = advance_expired_turn(room, code, TURN_TIME_LIMIT, now)
    if event:
        if room.get("state", {}).get("game_over"):
            finish_room_if_complete(room, room["state"])
        _save_room(code, room)
    return event


def _prepare_room(code, room, now):
    """Prune, advance an expired turn, and persist one locked room mutation."""
    room = prune_room_activity(room, now)
    if not room:
        _delete_room(code)
        return None
    _advance_expired_turn_if_needed(code, room, now)
    _save_room(code, room)
    return room


def _room_summary(code, room):
    return {
        "code": code,
        "host": room["host"],
        "players": room["players"],
        "status": "full" if len(room["players"]) >= 2 else "waiting",
        "room_phase": room_phase(room),
        "observer_count": len(room.get("observers", [])),
    }


def active_room_summaries(now=None):
    now = now or time.time()
    summaries = []
    for code, info in list(rooms.items()):
        with _room_lock(code):
            room = _prepare_room(code, rooms.get(code, info), now)
            if room:
                summaries.append(_room_summary(code, room))
    return summaries


@rooms_bp.route("/api/rooms", methods=["GET"])
def list_rooms():
    return jsonify(active_room_summaries())


@rooms_bp.route("/api/rooms", methods=["POST"])
def create_room():
    username = normalize_username((request.json or {}).get("username"))
    if not username:
        return jsonify({"error": _INVALID_USERNAME}), 400

    now = time.time()

    state = default_room_state()
    state["scores"][username] = [None] * 12
    state["player_dice"][username] = [1] * 5
    state["player_kept"][username] = [0] * 5
    state["player_rolls_left"][username] = 3
    state["turn"] = username
    state["players"] = [username]

    player_token = issue_player_token()
    room = {
        "host": username,
        "players": [username],
        "observers": [],
        "player_tokens": {username: player_token},
        "state": state,
        "created_at": now,
        "last_update": now,
        "started_full": False,
        "result_saved": False,
        "player_last_seen": {username: now},
        "observer_last_seen": {},
        "rematch_requests": {},
        "reactions": [],
        "reaction_last_sent": {},
        "fair": build_fair_state(),
    }
    for _ in range(25):
        code = generate_room_code()
        if _save_room_if_absent(code, room):
            return jsonify({"code": code, "players": room["players"], "player_token": player_token})
    return jsonify({"error": "방 코드 생성 실패"}), 503


@rooms_bp.route("/api/rooms/<code>/join", methods=["POST"])
def join_room(code):
    username = normalize_username((request.json or {}).get("username"))
    if not username:
        return jsonify({"error": _INVALID_USERNAME}), 400
    with _room_lock(code):
        if code not in rooms:
            return jsonify({"error": "방 없음"}), 404

        now = time.time()
        room = _prepare_room(code, rooms[code], now)
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
        room["result_saved"] = False
        room["rematch_requests"] = {}
        room["fair"] = build_fair_state()
        touch_player(room, username, now)
        _save_room(code, room)

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
    with _room_lock(code):
        if code not in rooms:
            return jsonify({"error": "방 없음"}), 404

        now = time.time()
        room = _prepare_room(code, rooms[code], now)
        if not room:
            return jsonify({"error": "방 없음"}), 404
        if username in room["players"]:
            return jsonify({"error": "이미 플레이어입니다"}), 409

        if username not in room.get("observers", []):
            room.setdefault("observers", []).append(username)
        touch_observer(room, username, now)
        _save_room(code, room)

        return jsonify({
            "code": code,
            "observers": room["observers"],
            "players": room["players"],
            "state": room["state"],
        })


@rooms_bp.route("/api/rooms/<code>", methods=["GET"])
def get_room(code):
    with _room_lock(code):
        room = rooms.get(code)
        if not room:
            return jsonify({"error": "방 없음"}), 404

        now = time.time()
        u = normalize_username(request.args.get("u"))
        player_token = request.headers.get("X-Player-Token", "")
        if u and u in room.get("players", []):
            if not is_valid_player(room, u, player_token):
                return jsonify({"error": "참가자 인증 실패"}), 403
            touch_player(room, u, now)
        elif u and u in room.get("observers", []):
            touch_observer(room, u, now)

        room = _prepare_room(code, room, now)
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
            "reactions": _recent_reactions(room),
        }
        payload.update(rematch_payload(room))

        if since_version is not None and since_version == current_version:
            payload["unchanged"] = True
            payload["state"] = {
                "version": current_version,
                "turn_left_seconds": turn_left,
                "turn": state.get("turn"),
                "game_over": state.get("game_over", False),
            }
        return jsonify(payload)


@rooms_bp.route("/api/rooms/<code>/events", methods=["GET"])
def room_events(code):
    with _room_lock(code):
        if code not in rooms:
            return jsonify({"error": "방 없음"}), 404

    once = request.args.get("once") == "1"
    slot_acquired = once or get_services().sse_slots.acquire(blocking=False)
    if not slot_acquired:
        response = jsonify({"error": "실시간 연결이 혼잡합니다. 잠시 후 다시 시도해 주세요."})
        response.headers["Retry-After"] = "2"
        return response, 503
    last_version = safe_int(request.args.get("sv"), -1)
    last_reaction_id = (request.args.get("reaction_id") or "").strip() or None
    reaction_cursor_initialized = last_reaction_id is not None
    interval_ms = safe_int(request.args.get("interval_ms"), 1200)
    interval_s = max(0.5, min((interval_ms or 1200) / 1000, 5.0))

    @stream_with_context
    def generate():
        nonlocal last_version, last_reaction_id, reaction_cursor_initialized
        try:
            deadline = time.time() + 25
            last_heartbeat = 0
            while True:
                with _room_lock(code):
                    room = _prepare_room(code, rooms.get(code), time.time())
                    if room:
                        state = room.get("state", default_room_state())
                        current_version = safe_int(state.get("version"), 0)
                        room_notice = room_event_payload(code, room)
                        reactions = _recent_reactions(room)
                    else:
                        current_version = None
                        room_notice = None
                        reactions = []

                if room_notice is None:
                    yield sse_event("room_closed", {"code": code})
                    return

                if not reaction_cursor_initialized:
                    last_reaction_id = reactions[-1].get("id") if reactions else None
                    reaction_cursor_initialized = True
                else:
                    new_reactions = _reactions_after(reactions, last_reaction_id)
                    for reaction in new_reactions:
                        yield sse_event("reaction", reaction)
                    if new_reactions:
                        last_reaction_id = new_reactions[-1].get("id")

                if once or current_version != last_version:
                    last_version = current_version
                    yield sse_event(
                        "room_state",
                        room_notice,
                        event_id=current_version,
                    )
                    if once:
                        return
                elif time.time() - last_heartbeat >= 10:
                    last_heartbeat = time.time()
                    yield sse_event("heartbeat", {"code": code, "ts": int(last_heartbeat)})

                if time.time() >= deadline:
                    return
                time.sleep(interval_s)
        finally:
            if not once:
                get_services().sse_slots.release()

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@rooms_bp.route("/api/rooms/<code>/heartbeat", methods=["POST"])
def heartbeat_room(code):
    data = request.json or {}
    username = normalize_username(data.get("username"))
    player_token = data.get("player_token")
    with _room_lock(code):
        room = rooms.get(code)
        if not room:
            return jsonify({"error": "방 없음"}), 404

        now = time.time()

        if username in room.get("players", []):
            if not is_valid_player(room, username, player_token):
                return jsonify({"error": "참가자 인증 실패"}), 403
            touch_player(room, username, now)
        elif username in room.get("observers", []):
            touch_observer(room, username, now)
        else:
            return jsonify({"error": "참가자 없음"}), 404

        room = _prepare_room(code, room, now)
        if not room:
            return jsonify({"error": "방 없음"}), 404

        return jsonify({
            "status": "ok",
            "room_phase": room_phase(room),
            "observer_count": len(room.get("observers", [])),
        })


@rooms_bp.route("/api/rooms/<code>/sync", methods=["POST"])
def sync_room(code):
    data = request.json or {}
    username = normalize_username(data.get("username"))
    player_token = data.get("player_token")
    with _room_lock(code):
        room = rooms.get(code)
        if not room:
            return jsonify({"error": "방 없음"}), 404

        if username not in room["players"] or not is_valid_player(room, username, player_token):
            return jsonify({"error": "참가자 인증 실패"}), 403

        now = time.time()
        touch_player(room, username, now)
        room = _prepare_room(code, room, now)
        if not room or username not in room.get("players", []):
            return jsonify({"error": "방 없음"}), 404

        state = room.get("state", default_room_state())
        if state.get("turn") and state["turn"] != username and not data.get("game_over"):
            return jsonify({"error": "상대 턴"}), 403

        # 주사위와 남은 굴림은 서버 소유다. Keep은 다음 굴림에서 어떤 주사위를
        # 보존할지 정하는 의도라서, 현재 턴 플레이어의 선택만 저장한다.
        if "dice" in data and normalize_dice(data["dice"]) is None:
            return jsonify({"error": "잘못된 주사위 데이터"}), 400
        requested_kept = normalize_kept(data.get("kept", state.get("kept", [0, 0, 0, 0, 0])))
        if requested_kept is None:
            return jsonify({"error": "잘못된 keep 데이터"}), 400
        if "rolls_left" in data and normalize_rolls_left(data["rolls_left"], 0, 3) is None:
            return jsonify({"error": "rolls_left는 0~3 정수여야 합니다"}), 400

        dice = normalize_dice(state.get("dice", [1, 1, 1, 1, 1]))
        rolls_left = normalize_rolls_left(state.get("rolls_left", 3), 0, 3)
        if dice is None or rolls_left is None:
            return jsonify({"error": "서버 주사위 상태가 올바르지 않습니다"}), 500
        if rolls_left == 3:
            requested_kept = [0, 0, 0, 0, 0]

        scores_payload = data.get("scores", state["scores"])
        normalized_scores = normalize_scores_by_players(scores_payload, room["players"])
        if normalized_scores is None:
            return jsonify({"error": "scores는 플레이어별 길이 12 점수/None 배열이어야 합니다"}), 400

        requested_turn = data.get("turn", state.get("turn"))
        is_game_over_requested = bool(data.get("game_over", state["game_over"]))
        valid_transition, validation_error, transition = validate_sync_transition(
            room, username, state, normalized_scores, requested_turn, is_game_over_requested
        )
        if not valid_transition:
            return jsonify({"error": validation_error}), 400

        player_dice = state.setdefault("player_dice", {})
        player_kept = state.setdefault("player_kept", {})
        player_rolls_left = state.setdefault("player_rolls_left", {})
        player_dice[username] = dice
        player_kept[username] = requested_kept
        player_rolls_left[username] = rolls_left

        prev_turn = state.get("turn")
        new_turn = requested_turn
        turn_start_time = state.get("turn_start_time")
        if prev_turn != new_turn or (rolls_left == 3 and state.get("rolls_left") != 3):
            turn_start_time = time.time()

        is_game_over = bool(transition["all_done"])
        score_action = transition.get("score_action")
        next_dice = dice
        next_kept = requested_kept
        next_rolls_left = rolls_left
        if score_action and not is_game_over and new_turn in room["players"]:
            next_dice = [1, 1, 1, 1, 1]
            next_kept = [0, 0, 0, 0, 0]
            next_rolls_left = 3
            player_dice[new_turn] = next_dice[:]
            player_kept[new_turn] = next_kept[:]
            player_rolls_left[new_turn] = next_rolls_left

        winner = None
        loser = None
        end_reason = None
        if is_game_over:
            totals = {
                player: score_total(normalized_scores.get(player))
                for player in room.get("players", [])
            }
            ordered_players = room.get("players", [])
            if len(ordered_players) >= 2:
                p1, p2 = ordered_players[0], ordered_players[1]
                if totals[p1] > totals[p2]:
                    winner, loser = p1, p2
                elif totals[p2] > totals[p1]:
                    winner, loser = p2, p1
            end_reason = "score"

        new_state = {
            "dice": next_dice,
            "kept": next_kept,
            "rolls_left": next_rolls_left,
            "scores": normalized_scores,
            "player_dice": player_dice,
            "player_kept": player_kept,
            "player_rolls_left": player_rolls_left,
            "turn": new_turn,
            "turn_start_time": turn_start_time,
            "game_over": is_game_over,
            # AI 추천은 각 클라이언트가 현재 주사위로 계산하는 개인 UI 상태다.
            # 방 상태에 남기면 상대의 추천(특히 희생 칸)이 다음 턴 플레이어에게
            # 전달되어 새 주사위에 잘못 적용될 수 있다.
            "ai_rec": None,
            "players": state.get("players", room["players"]),
            "version": state.get("version", 0) + 1,
            "updated_by": username,
            "winner": winner,
            "loser": loser,
            "end_reason": end_reason,
        }
        if not is_game_over:
            new_state["winner"] = None
            new_state["loser"] = None
            new_state["end_reason"] = None

        room["state"] = new_state
        room["last_update"] = now
        if not is_game_over:
            room["rematch_requests"] = {}
        else:
            finish_room_if_complete(room, new_state)
        _save_room(code, room)
        return jsonify({"state": new_state})


@rooms_bp.route("/api/rooms/<code>/roll", methods=["POST"])
def roll_dice(code):
    data = request.json or {}
    username = normalize_username(data.get("username"))
    player_token = data.get("player_token")
    with _room_lock(code):
        room = rooms.get(code)
        if not room:
            return jsonify({"error": "방 없음"}), 404

        if username not in room["players"] or not is_valid_player(room, username, player_token):
            return jsonify({"error": "참가자 인증 실패"}), 403

        now = time.time()
        touch_player(room, username, now)
        room = _prepare_room(code, room, now)
        if not room or username not in room.get("players", []):
            return jsonify({"error": "방 없음"}), 404

        if len(room.get("players", [])) < 2:
            return jsonify({"error": "상대방 입장 대기 중"}), 409

        state = room.get("state", default_room_state())
        if state.get("turn") and state["turn"] != username:
            return jsonify({"error": "상대 턴"}), 403

        expected_version = safe_int(data.get("expected_version"))
        if "expected_version" in data and expected_version is None:
            return jsonify({"error": "expected_version은 정수여야 합니다"}), 400
        current_version = safe_int(state.get("version"), 0)
        if expected_version is not None and expected_version != current_version:
            return jsonify({
                "error": "방 상태가 최신이 아닙니다. 다시 동기화해 주세요.",
                "state": state,
            }), 409

        rolls_left = state.get("rolls_left", 3)
        if rolls_left <= 0:
            return jsonify({"error": "남은 굴림 없음"}), 400

        kept = normalize_kept(data.get("kept", state["kept"]))
        if kept is None:
            return jsonify({"error": "잘못된 고정 주사위 데이터"}), 400
        roll_result = roll_room_dice(room, code, kept)
        state.pop("timeout_event", None)
        state["version"] = state.get("version", 0) + 1
        state["turn_start_time"] = now

        room["state"] = state
        room["last_update"] = now
        _save_room(code, room)
        return jsonify({
            "dice": roll_result["dice"],
            "rolls_left": roll_result["rolls_left"],
            "state": state,
            "fairness": roll_result["fairness"],
        })


@rooms_bp.route("/api/rooms/<code>/score", methods=["POST"])
def score_room(code):
    """Record a category through one server-authoritative game command."""
    data = request.json or {}
    username = normalize_username(data.get("username"))
    player_token = data.get("player_token")
    category_idx = safe_int(data.get("category_idx"))
    if category_idx is None:
        return jsonify({"error": "category_idx는 정수여야 합니다"}), 400

    with _room_lock(code):
        room = rooms.get(code)
        if not room:
            return jsonify({"error": "방 없음"}), 404
        if username not in room.get("players", []) or not is_valid_player(room, username, player_token):
            return jsonify({"error": "참가자 인증 실패"}), 403

        now = time.time()
        touch_player(room, username, now)
        room = _prepare_room(code, room, now)
        if not room or username not in room.get("players", []):
            return jsonify({"error": "방 없음"}), 404

        if len(room.get("players", [])) < 2:
            return jsonify({"error": "상대방 입장 대기 중"}), 409
        state = room.get("state", default_room_state())
        expected_version = safe_int(data.get("expected_version"))
        if "expected_version" in data and expected_version is None:
            return jsonify({"error": "expected_version은 정수여야 합니다"}), 400
        current_version = safe_int(state.get("version"), 0)
        if expected_version is not None and expected_version != current_version:
            return jsonify({
                "error": "방 상태가 최신이 아닙니다. 다시 동기화해 주세요.",
                "state": state,
            }), 409

        try:
            result = record_room_score(room, username, category_idx, now=now)
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

        state = result["state"]
        if state.get("game_over"):
            finish_room_if_complete(room, state)
        else:
            room["rematch_requests"] = {}
        _save_room(code, room)
        return jsonify(result)


@rooms_bp.route("/api/rooms/<code>/reaction", methods=["POST"])
def react_to_room(code):
    data = request.json or {}
    username = normalize_username(data.get("username"))
    player_token = data.get("player_token")
    reaction_code = str(data.get("reaction") or "").strip().lower()
    if not username:
        return jsonify({"error": _INVALID_USERNAME}), 400
    if reaction_code not in _REACTIONS:
        return jsonify({"error": "지원하지 않는 감정표현입니다"}), 400

    with _room_lock(code):
        room = rooms.get(code)
        if not room:
            return jsonify({"error": "방 없음"}), 404

        now = time.time()
        if username not in room.get("players", []):
            return jsonify({"error": "참가자 없음"}), 404
        if not is_valid_player(room, username, player_token):
            return jsonify({"error": "참가자 인증 실패"}), 403

        touch_player(room, username, now)
        room = _prepare_room(code, room, now)
        if not room or username not in room.get("players", []):
            return jsonify({"error": "방 없음"}), 404

        last_sent = room.setdefault("reaction_last_sent", {}).get(username, 0)
        retry_after = _REACTION_COOLDOWN_SECONDS - (now - last_sent)
        if retry_after > 0:
            return jsonify({
                "error": "감정표현은 잠시 후 다시 보낼 수 있습니다",
                "retry_after_ms": int(retry_after * 1000) + 1,
            }), 429

        reaction = {
            "id": secrets.token_urlsafe(9),
            "user": username,
            "code": reaction_code,
            **_REACTIONS[reaction_code],
            "ts": now,
        }
        history = room.setdefault("reactions", [])
        history.append(reaction)
        if len(history) > _REACTION_HISTORY_LIMIT:
            del history[:-_REACTION_HISTORY_LIMIT]
        room["reaction_last_sent"][username] = now
        _save_room(code, room)
        return jsonify({"status": "ok", "reaction": reaction})


@rooms_bp.route("/api/rooms/<code>/fairness", methods=["GET"])
def room_fairness(code):
    with _room_lock(code):
        room = rooms.get(code)
        if not room:
            return jsonify({"error": "방 없음"}), 404
        room = _prepare_room(code, room, time.time())
        if not room:
            return jsonify({"error": "방 없음"}), 404
        fair = room.get("fair") or build_fair_state()
        room["fair"] = fair
        _save_room(code, room)
        payload = {"current_hash": fair.get("hash"), "current_nonce": fair.get("nonce", 0)}
        if fair.get("last_reveal"):
            payload["last_reveal"] = fair.get("last_reveal")
        return jsonify(payload)


@rooms_bp.route("/api/rooms/<code>/rematch", methods=["POST"])
def rematch_room(code):
    data = request.json or {}
    username = normalize_username(data.get("username"))
    player_token = data.get("player_token")
    with _room_lock(code):
        room = rooms.get(code)
        if not room:
            return jsonify({"error": "방 없음"}), 404

        if username not in room.get("players", []) or not is_valid_player(room, username, player_token):
            return jsonify({"error": "참가자 인증 실패"}), 403

        now = time.time()
        touch_player(room, username, now)
        room = _prepare_room(code, room, now)
        if not room or username not in room.get("players", []):
            return jsonify({"error": "방 없음"}), 404

        state = room.get("state", default_room_state())
        if not state.get("game_over"):
            return jsonify({"error": "게임이 아직 끝나지 않았습니다"}), 409
        if len(room.get("players", [])) < 2:
            return jsonify({"error": "재대결 가능한 상대가 없습니다"}), 409

        requests = room.setdefault("rematch_requests", {})
        requests[username] = now
        pending_payload = rematch_payload(room)

        if len(pending_payload["rematch_pending_players"]) >= 2:
            new_state = start_room_rematch(room, now=now)
            room["result_saved"] = False
            _save_room(code, room)
            payload = {
                "status": "started",
                "players": room.get("players", []),
                "state": new_state,
            }
            payload.update(rematch_payload(room))
            return jsonify(payload)

        payload = {"status": "waiting"}
        payload.update(pending_payload)
        _save_room(code, room)
        return jsonify(payload)


@rooms_bp.route("/api/rooms/<code>/leave", methods=["POST"])
def leave_room(code):
    data = request.get_json(silent=True) or {}
    username = normalize_username(data.get("username"))
    player_token = data.get("player_token")
    with _room_lock(code):
        room = rooms.get(code)
        if not room:
            return jsonify({"error": "방 없음"}), 404

        if username in room.get("players", []) and not is_valid_player(room, username, player_token):
            return jsonify({"error": "참가자 인증 실패"}), 403

        now = time.time()

        if username in room["players"]:
            remove_player(room, username, now)
            if room["players"]:
                winner = room["players"][0]
                finalize_room_forfeit(room, winner, username, updated_by="system_leave", now=now)
                _save_room(code, room)
                return jsonify({"status": "left", "players": room["players"]})

        if username in room.get("observers", []):
            remove_observer(room, username, now)
            _save_room(code, room)
            return jsonify({
                "status": "left",
                "players": room.get("players", []),
                "observers": room.get("observers", []),
            })

        if not room.get("players"):
            _delete_room(code)

        return jsonify({"status": "left", "players": []})
