import string
import secrets
import time

import database
from app_state import rooms
from config import PLAYER_ROOM_TIMEOUT, OBSERVER_ROOM_TIMEOUT


def default_room_state():
    return {
        "dice": [1, 1, 1, 1, 1],
        "kept": [0, 0, 0, 0, 0],
        "rolls_left": 3,
        "scores": {},
        "player_dice": {},
        "player_kept": {},
        "player_rolls_left": {},
        "turn": None,
        "turn_start_time": None,
        "game_over": False,
        "ai_msg": "AI: 새 게임을 시작하세요",
        "ai_rec": None,
        "version": 0,
        "updated_by": None,
        "winner": None,
        "loser": None,
        "end_reason": None,
    }


def score_total(card):
    card = card or []
    card = (card + [None] * 12)[:12]
    upper = sum((v or 0) for v in card[:6])
    bonus = 35 if upper >= 63 else 0
    lower = sum((v or 0) for v in card[6:])
    return upper + bonus + lower


def room_phase(room):
    state = room.get("state", {})
    if state.get("game_over"):
        return "finished"
    if len(room.get("players", [])) >= 2:
        return "playing"
    return "waiting"


def touch_player(room, username, now=None):
    now = now or time.time()
    room.setdefault("player_last_seen", {})[username] = now
    room["last_update"] = now


def touch_observer(room, username, now=None):
    now = now or time.time()
    room.setdefault("observer_last_seen", {})[username] = now
    room["last_update"] = now


def remove_player(room, username, now=None):
    now = now or time.time()
    if username in room.get("players", []):
        room["players"].remove(username)
    room.get("player_tokens", {}).pop(username, None)
    room.setdefault("rematch_requests", {}).pop(username, None)
    room.setdefault("player_last_seen", {}).pop(username, None)
    if room.get("host") == username:
        room["host"] = room["players"][0] if room.get("players") else username
    room["last_update"] = now


def remove_observer(room, username, now=None):
    now = now or time.time()
    if username in room.get("observers", []):
        room["observers"].remove(username)
    room.setdefault("observer_last_seen", {}).pop(username, None)
    room["last_update"] = now


def finalize_room_forfeit(room, winner, loser, updated_by="system", now=None):
    if not winner or not loser or winner == loser or not room.get("started_full"):
        return
    state = room.get("state")
    if not isinstance(state, dict) or state.get("game_over"):
        return

    scores = state.get("scores", {})
    state["players"] = room.get("players", [])
    state["turn"] = winner
    state["turn_start_time"] = None
    state["game_over"] = True
    state["version"] = state.get("version", 0) + 1
    state["updated_by"] = updated_by
    state["winner"] = winner
    state["loser"] = loser
    state["end_reason"] = {
        "system_timeout": "timeout",
        "system_leave": "leave",
    }.get(updated_by, "system")

    room["state"] = state
    room["last_update"] = now or time.time()

    database.save_game_result(
        winner,
        score_total(scores.get(winner)),
        loser,
        score_total(scores.get(loser)),
        result_override="player1_win",
    )


def start_room_rematch(room, updated_by="system_rematch", now=None):
    now = now or time.time()
    players = list(room.get("players", []))
    if len(players) < 2:
        return None

    prev_state = room.get("state") or {}
    previous_winner = prev_state.get("winner")
    previous_turn = prev_state.get("turn")

    if previous_winner in players:
        starter = next((player for player in players if player != previous_winner), players[0])
    elif previous_turn in players:
        starter = next((player for player in players if player != previous_turn), players[0])
    else:
        starter = players[0]

    new_state = default_room_state()
    new_state["scores"] = {player: [None] * 12 for player in players}
    new_state["player_dice"] = {player: [1] * 5 for player in players}
    new_state["player_kept"] = {player: [0] * 5 for player in players}
    new_state["player_rolls_left"] = {player: 3 for player in players}
    new_state["players"] = players
    new_state["turn"] = starter
    new_state["turn_start_time"] = now
    new_state["version"] = prev_state.get("version", 0) + 1
    new_state["updated_by"] = updated_by

    room["state"] = new_state
    room["last_update"] = now
    room["started_full"] = True
    room["rematch_requests"] = {}
    return new_state


def prune_room_activity(code, room, now=None):
    now = now or time.time()

    player_last_seen = room.setdefault("player_last_seen", {})
    current_players = list(room.get("players", []))
    stale_players = [
        p for p in current_players
        if player_last_seen.get(p, 0) < now - PLAYER_ROOM_TIMEOUT
    ]
    surviving_players = [p for p in current_players if p not in stale_players]
    for player in stale_players:
        remove_player(room, player, now)

    if len(current_players) >= 2 and len(stale_players) == 1 and len(surviving_players) == 1:
        finalize_room_forfeit(
            room,
            surviving_players[0],
            stale_players[0],
            updated_by="system_timeout",
            now=now,
        )

    observer_last_seen = room.setdefault("observer_last_seen", {})
    stale_observers = [
        obs for obs in list(room.get("observers", []))
        if observer_last_seen.get(obs, 0) < now - OBSERVER_ROOM_TIMEOUT
    ]
    for observer in stale_observers:
        remove_observer(room, observer, now)

    state = room.get("state")
    if isinstance(state, dict):
        state["players"] = room.get("players", [])

    if not room.get("players"):
        rooms.pop(code, None)
        return None

    room["last_update"] = now
    return room


def generate_room_code(length=6):
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))
