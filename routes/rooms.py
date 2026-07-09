import json
import time
from contextlib import nullcontext

from flask import Blueprint, Response, jsonify, request, stream_with_context

from app_state import rooms
from config import TURN_TIME_LIMIT
from utils.room_utils import (
    build_fair_state, default_room_state, finalize_room_forfeit, generate_room_code,
    prune_room_activity, remove_observer, remove_player, roll_with_fairness, room_phase,
    score_total, start_room_rematch, touch_observer, touch_player,
)
from utils.validation import (
    is_valid_player, issue_player_token,
    normalize_dice, normalize_kept, normalize_rolls_left, normalize_scores_by_players,
    normalize_username, safe_int,
)
from yacht_engine import CATS, calc_score
import database

rooms_bp = Blueprint("rooms", __name__)

_INVALID_USERNAME = "닉네임은 2~12자(한글/영문/숫자/_)만 가능합니다"
_YACHT_IDX = CATS["Yacht"]


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


def _rematch_payload(room):
    players = room.get("players", [])
    requests = room.get("rematch_requests", {})
    pending_players = [player for player in players if player in requests]
    waiting_for = [player for player in players if player not in requests]
    return {
        "rematch_pending_players": pending_players,
        "rematch_waiting_for": waiting_for,
    }


def _room_event_payload(code, room):
    state = room.get("state", default_room_state())
    return {
        "code": code,
        "room_phase": room_phase(room),
        "players": room.get("players", []),
        "observer_count": len(room.get("observers", [])),
        "version": safe_int(state.get("version"), 0),
        "turn": state.get("turn"),
        "game_over": state.get("game_over", False),
    }


def _sse_event(event_name, payload, event_id=None):
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event_name}")
    lines.append(f"data: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}")
    return "\n".join(lines) + "\n\n"


def _cards_are_empty(scores):
    return all(all(value is None for value in scores.get(player, [])) for player in scores)


def _changed_indices(previous, current):
    return [idx for idx, (old, new) in enumerate(zip(previous, current)) if old != new]


def _is_yacht_roll(dice):
    return calc_score(dice, _YACHT_IDX) == 50


def _validate_player_score_delta(previous_card, current_card, scoring_dice, previous_rolls_left):
    changed = _changed_indices(previous_card, current_card)
    if not changed:
        return True, None, None
    if previous_rolls_left >= 3:
        return False, "점수 기록 전에는 최소 1회 굴려야 합니다", None

    if len(changed) == 1:
        category_idx = changed[0]
        if previous_card[category_idx] is not None:
            return False, "이미 기록된 점수칸은 변경할 수 없습니다", None
        expected_score = calc_score(scoring_dice, category_idx)
        if current_card[category_idx] != expected_score:
            return False, "점수가 서버 계산 결과와 다릅니다", None
        return True, None, {"category_idx": category_idx, "score": expected_score}

    if len(changed) == 2 and _YACHT_IDX in changed:
        category_idx = next(idx for idx in changed if idx != _YACHT_IDX)
        if previous_card[category_idx] is not None:
            return False, "이미 기록된 점수칸은 변경할 수 없습니다", None
        if not isinstance(previous_card[_YACHT_IDX], int) or previous_card[_YACHT_IDX] < 50:
            return False, "Yacht Bonus 조건이 충족되지 않았습니다", None
        expected_score = calc_score(scoring_dice, category_idx)
        if expected_score <= 0 or not _is_yacht_roll(scoring_dice):
            return False, "Yacht Bonus 조건이 충족되지 않았습니다", None
        if current_card[category_idx] != expected_score:
            return False, "점수가 서버 계산 결과와 다릅니다", None
        if current_card[_YACHT_IDX] != previous_card[_YACHT_IDX] + 100:
            return False, "Yacht Bonus 점수가 서버 계산 결과와 다릅니다", None
        return True, None, {"category_idx": category_idx, "score": expected_score, "yacht_bonus": 100}

    return False, "한 번의 턴에는 하나의 점수칸만 기록할 수 있습니다", None


def _validate_sync_transition(room, username, state, normalized_scores, requested_turn, requested_game_over):
    players = room.get("players", [])
    previous_scores = state.get("scores", {})
    if set(normalized_scores.keys()) != set(players):
        return False, "scores 플레이어 목록이 방 참가자와 다릅니다", None

    for player in players:
        if player == username:
            continue
        if normalized_scores.get(player) != previous_scores.get(player):
            return False, "상대 점수판은 변경할 수 없습니다", None

    previous_card = previous_scores.get(username)
    current_card = normalized_scores.get(username)
    if previous_card is None or current_card is None:
        return False, "점수판 상태가 올바르지 않습니다", None

    scoring_dice = normalize_dice(state.get("dice", [1, 1, 1, 1, 1]))
    if scoring_dice is None:
        return False, "서버 주사위 상태가 올바르지 않습니다", None

    previous_rolls_left = normalize_rolls_left(state.get("rolls_left", 3), 0, 3)
    if previous_rolls_left is None:
        return False, "서버 굴림 상태가 올바르지 않습니다", None

    valid, message, score_action = _validate_player_score_delta(
        previous_card, current_card, scoring_dice, previous_rolls_left
    )
    if not valid:
        return False, message, None

    previous_turn = state.get("turn")
    if requested_turn not in players:
        return False, "turn은 방 참가자 중 한 명이어야 합니다", None

    if score_action:
        if previous_turn != username:
            return False, "현재 턴 플레이어만 점수를 기록할 수 있습니다", None
    elif requested_turn != previous_turn:
        pass_allowed = (
            previous_turn == username
            and previous_rolls_left == 3
            and _cards_are_empty(previous_scores)
            and _cards_are_empty(normalized_scores)
        )
        if not pass_allowed:
            return False, "점수 기록 없는 턴 변경은 시작 전 선공권 넘기기만 허용됩니다", None

    all_done = all(all(value is not None for value in normalized_scores.get(player, [])) for player in players)
    if requested_game_over and not all_done:
        return False, "모든 점수칸이 채워지기 전에는 게임을 종료할 수 없습니다", None

    return True, None, {"score_action": score_action, "all_done": all_done}


def _finish_room_if_complete(room, state):
    players = room.get("players", [])
    if len(players) < 2 or not state.get("game_over") or room.get("result_saved"):
        return

    player1, player2 = players[0], players[1]
    scores = state.get("scores", {})
    score1 = score_total(scores.get(player1))
    score2 = score_total(scores.get(player2))

    database.save_game_result(player1, score1, player2, score2)
    room["result_saved"] = True


@rooms_bp.route("/api/rooms", methods=["GET"])
def list_rooms():
    now = time.time()
    for code, info in list(rooms.items()):
        with _room_lock(code):
            current = rooms.get(code, info)
            pruned = prune_room_activity(code, current, now)
            if pruned:
                _save_room(code, pruned)
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
        room = prune_room_activity(code, rooms[code], now)
        if not room:
            return jsonify({"error": "방 없음"}), 404
        _save_room(code, room)
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
        room = prune_room_activity(code, rooms[code], now)
        if not room:
            return jsonify({"error": "방 없음"}), 404
        _save_room(code, room)
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
        u = request.args.get("u")
        pt = request.args.get("pt")
        if u and u in room.get("players", []) and is_valid_player(room, u, pt):
            touch_player(room, u, now)
        elif u and u in room.get("observers", []):
            touch_observer(room, u, now)

        room = prune_room_activity(code, room, now)
        if not room:
            return jsonify({"error": "방 없음"}), 404
        _save_room(code, room)

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
        payload.update(_rematch_payload(room))

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
    if code not in rooms:
        return jsonify({"error": "방 없음"}), 404

    once = request.args.get("once") == "1"
    last_version = safe_int(request.args.get("sv"), -1)
    interval_ms = safe_int(request.args.get("interval_ms"), 1200)
    interval_s = max(0.5, min((interval_ms or 1200) / 1000, 5.0))

    @stream_with_context
    def generate():
        nonlocal last_version
        deadline = time.time() + 25
        last_heartbeat = 0
        while True:
            room = rooms.get(code)
            if not room:
                yield _sse_event("room_closed", {"code": code})
                return

            state = room.get("state", default_room_state())
            current_version = safe_int(state.get("version"), 0)
            if once or current_version != last_version:
                last_version = current_version
                yield _sse_event(
                    "room_state",
                    _room_event_payload(code, room),
                    event_id=current_version,
                )
                if once:
                    return
            elif time.time() - last_heartbeat >= 10:
                last_heartbeat = time.time()
                yield _sse_event("heartbeat", {"code": code, "ts": int(last_heartbeat)})

            if time.time() >= deadline:
                return
            time.sleep(interval_s)

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

        room = prune_room_activity(code, room, now)
        if not room:
            return jsonify({"error": "방 없음"}), 404
        _save_room(code, room)

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
        room = prune_room_activity(code, room, now)
        if not room or username not in room.get("players", []):
            return jsonify({"error": "방 없음"}), 404
        _save_room(code, room)

        state = room.get("state", default_room_state())
        if state.get("turn") and state["turn"] != username and not data.get("game_over"):
            return jsonify({"error": "상대 턴"}), 403

        requested_dice = normalize_dice(data.get("dice", state["dice"]))
        requested_kept = normalize_kept(data.get("kept", state["kept"]))
        if requested_dice is None or requested_kept is None:
            return jsonify({"error": "잘못된 주사위 데이터"}), 400

        requested_rolls_left = normalize_rolls_left(data.get("rolls_left", state["rolls_left"]), 0, 3)
        if requested_rolls_left is None:
            return jsonify({"error": "rolls_left는 0~3 정수여야 합니다"}), 400

        dice = normalize_dice(state.get("dice", [1, 1, 1, 1, 1]))
        kept = normalize_kept(state.get("kept", [0, 0, 0, 0, 0]))
        rolls_left = normalize_rolls_left(state.get("rolls_left", 3), 0, 3)
        if dice is None or kept is None or rolls_left is None:
            return jsonify({"error": "서버 주사위 상태가 올바르지 않습니다"}), 500

        scores_payload = data.get("scores", state["scores"])
        normalized_scores = normalize_scores_by_players(scores_payload, room["players"])
        if normalized_scores is None:
            return jsonify({"error": "scores는 플레이어별 길이 12 점수/None 배열이어야 합니다"}), 400

        requested_turn = data.get("turn", state.get("turn"))
        is_game_over_requested = bool(data.get("game_over", state["game_over"]))
        valid_transition, validation_error, transition = _validate_sync_transition(
            room, username, state, normalized_scores, requested_turn, is_game_over_requested
        )
        if not valid_transition:
            return jsonify({"error": validation_error}), 400

        player_dice = state.setdefault("player_dice", {})
        player_kept = state.setdefault("player_kept", {})
        player_rolls_left = state.setdefault("player_rolls_left", {})
        player_dice[username] = dice
        player_kept[username] = kept
        player_rolls_left[username] = rolls_left

        prev_turn = state.get("turn")
        new_turn = requested_turn
        turn_start_time = state.get("turn_start_time")
        if prev_turn != new_turn or (rolls_left == 3 and state.get("rolls_left") != 3):
            turn_start_time = time.time()

        is_game_over = bool(transition["all_done"])
        score_action = transition.get("score_action")
        next_dice = dice
        next_kept = kept
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
            "ai_rec": data.get("ai_rec", state.get("ai_rec")),
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
            _finish_room_if_complete(room, new_state)
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
        room = prune_room_activity(code, room, now)
        if not room or username not in room.get("players", []):
            return jsonify({"error": "방 없음"}), 404
        _save_room(code, room)

        state = room.get("state", default_room_state())
        if state.get("turn") and state["turn"] != username:
            return jsonify({"error": "상대 턴"}), 403

        rolls_left = state.get("rolls_left", 3)
        if rolls_left <= 0:
            return jsonify({"error": "남은 굴림 없음"}), 400

        kept = normalize_kept(data.get("kept", state["kept"]))
        if kept is None:
            return jsonify({"error": "잘못된 고정 주사위 데이터"}), 400

        fair = room.get("fair") or build_fair_state()
        rolled_values, next_fair = roll_with_fairness(code, kept, fair)

        new_dice = state["dice"][:]
        for i in range(5):
            if not kept[i]:
                new_dice[i] = rolled_values[i]

        state.setdefault("player_dice", {})[username] = new_dice
        state.setdefault("player_kept", {})[username] = kept
        state.setdefault("player_rolls_left", {})[username] = rolls_left - 1
        state["dice"] = new_dice
        state["kept"] = kept
        state["rolls_left"] = rolls_left - 1
        state["version"] = state.get("version", 0) + 1
        state["turn_start_time"] = now

        room["state"] = state
        room["fair"] = next_fair
        room["last_update"] = now
        _save_room(code, room)
        return jsonify({
            "dice": new_dice,
            "rolls_left": state["rolls_left"],
            "state": state,
            "fairness": {
                "revealed": next_fair.get("last_reveal"),
                "next_hash": next_fair.get("hash"),
                "next_nonce": next_fair.get("nonce", 0),
            },
        })


@rooms_bp.route("/api/rooms/<code>/fairness", methods=["GET"])
def room_fairness(code):
    with _room_lock(code):
        room = rooms.get(code)
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
        room = prune_room_activity(code, room, now)
        if not room or username not in room.get("players", []):
            return jsonify({"error": "방 없음"}), 404
        _save_room(code, room)

        state = room.get("state", default_room_state())
        if not state.get("game_over"):
            return jsonify({"error": "게임이 아직 끝나지 않았습니다"}), 409
        if len(room.get("players", [])) < 2:
            return jsonify({"error": "재대결 가능한 상대가 없습니다"}), 409

        requests = room.setdefault("rematch_requests", {})
        requests[username] = now
        pending_payload = _rematch_payload(room)

        if len(pending_payload["rematch_pending_players"]) >= 2:
            new_state = start_room_rematch(room, now=now)
            room["result_saved"] = False
            _save_room(code, room)
            payload = {
                "status": "started",
                "players": room.get("players", []),
                "state": new_state,
            }
            payload.update(_rematch_payload(room))
            return jsonify(payload)

        payload = {"status": "waiting"}
        payload.update(pending_payload)
        _save_room(code, room)
        return jsonify(payload)


@rooms_bp.route("/api/rooms/<code>/leave", methods=["POST", "GET"])
def leave_room(code):
    data = request.get_json(silent=True) or {}
    username = normalize_username(data.get("username") or request.args.get("username"))
    player_token = data.get("player_token") or request.args.get("pt")
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
