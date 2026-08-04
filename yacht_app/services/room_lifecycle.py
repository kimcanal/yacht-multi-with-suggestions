import secrets
import string
import time

from app_state import get_services
from config import OBSERVER_ROOM_TIMEOUT, PLAYER_ROOM_TIMEOUT
from yacht_app.services.room_types import Room, RoomState
from yacht_core import CATS, calc_score
from yacht_core.simulation import total_score as score_total


def default_room_state() -> RoomState:
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


def room_phase(room: Room) -> str:
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

    get_services().results.save_game_result(
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


def prune_room_activity(room, now=None):
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
        return None

    room["last_update"] = now
    return room


def generate_room_code(length=6):
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


def _new_fair_round():
    secret = secrets.token_hex(16)
    return {
        "secret": secret,
        "hash": secrets.token_hex(0),
        "nonce": 0,
        "last_reveal": None,
    }


def build_fair_state():
    fair = _new_fair_round()
    import hashlib
    fair["hash"] = hashlib.sha256(fair["secret"].encode("utf-8")).hexdigest()
    return fair


def roll_with_fairness(code, kept, fair):
    import hashlib
    nonce = fair.get("nonce", 0)
    secret = fair["secret"]
    generated = []
    for i in range(5):
        payload = f"{code}:{nonce}:{i}:{secret}".encode("utf-8")
        raw = hashlib.sha256(payload).digest()
        generated.append((raw[0] % 6) + 1)

    next_fair = build_fair_state()
    next_fair["last_reveal"] = {
        "secret": secret,
        "hash": fair.get("hash"),
        "nonce": nonce,
        "generated_dice": generated,
    }
    next_fair["nonce"] = nonce + 1

    out = []
    for i in range(5):
        out.append(generated[i] if not kept[i] else None)
    return out, next_fair


def roll_room_dice(room: Room, code: str, kept: list[int]) -> dict:
    """Apply the server-owned dice transition shared by manual and timeout rolls."""
    state = room.get("state") or {}
    player = state.get("turn")
    dice = state.get("dice")
    rolls_left = state.get("rolls_left", 3)
    if (
        player not in room.get("players", [])
        or not isinstance(dice, list)
        or len(dice) != 5
        or not isinstance(kept, list)
        or len(kept) != 5
        or not isinstance(rolls_left, int)
        or not 1 <= rolls_left <= 3
    ):
        raise ValueError("room roll state is invalid")

    effective_kept = [0] * 5 if rolls_left == 3 else kept[:]
    fair = room.get("fair") or build_fair_state()
    rolled_values, next_fair = roll_with_fairness(code, effective_kept, fair)
    next_dice = dice[:]
    for index, value in enumerate(rolled_values):
        if not effective_kept[index]:
            next_dice[index] = value

    next_rolls_left = rolls_left - 1
    state.setdefault("player_dice", {})[player] = next_dice[:]
    state.setdefault("player_kept", {})[player] = effective_kept[:]
    state.setdefault("player_rolls_left", {})[player] = next_rolls_left
    state["dice"] = next_dice
    state["kept"] = effective_kept
    state["rolls_left"] = next_rolls_left
    room["state"] = state
    room["fair"] = next_fair
    return {
        "dice": next_dice,
        "kept": effective_kept,
        "rolls_left": next_rolls_left,
        "fairness": {
            "revealed": next_fair.get("last_reveal"),
            "next_hash": next_fair.get("hash"),
            "next_nonce": next_fair.get("nonce", 0),
        },
    }


def record_room_score(
    room: Room,
    username: str,
    category_idx: int,
    *,
    now: float | None = None,
    updated_by: str | None = None,
    end_reason: str = "score",
) -> dict:
    """Record one server-calculated score and advance the game exactly once.

    This is deliberately a persistence-free transition: routes can save the
    room and trigger result storage after it returns, while timeout handling
    can use the same rules without reimplementing Yacht-bonus/game-end logic.
    """
    now = now or time.time()
    state = room.get("state") or {}
    players = room.get("players", [])
    dice = state.get("dice")
    rolls_left = state.get("rolls_left", 3)
    scorecard = state.get("scores", {}).get(username)

    if state.get("game_over"):
        raise ValueError("이미 종료된 게임입니다")
    if username not in players or state.get("turn") != username:
        raise ValueError("현재 턴 플레이어만 점수를 기록할 수 있습니다")
    if not isinstance(category_idx, int) or not 0 <= category_idx < 12:
        raise ValueError("점수칸 번호가 올바르지 않습니다")
    if not isinstance(dice, list) or len(dice) != 5 or any(value not in range(1, 7) for value in dice):
        raise ValueError("서버 주사위 상태가 올바르지 않습니다")
    if not isinstance(rolls_left, int) or not 0 <= rolls_left < 3:
        raise ValueError("점수 기록 전에는 최소 1회 굴려야 합니다")
    if not isinstance(scorecard, list) or len(scorecard) != 12:
        raise ValueError("점수판 상태가 올바르지 않습니다")
    if scorecard[category_idx] is not None:
        raise ValueError("이미 기록된 점수칸입니다")

    score = calc_score(dice, category_idx)
    yacht_idx = CATS["Yacht"]
    yacht_bonus = 0
    if (
        category_idx != yacht_idx
        and calc_score(dice, yacht_idx) == 50
        and isinstance(scorecard[yacht_idx], int)
        and scorecard[yacht_idx] >= 50
        and score > 0
    ):
        scorecard[yacht_idx] += 100
        yacht_bonus = 100
    scorecard[category_idx] = score
    state.setdefault("scores", {})[username] = scorecard

    all_done = all(
        isinstance(state.get("scores", {}).get(player), list)
        and all(value is not None for value in state["scores"][player])
        for player in players
    )
    if all_done:
        totals = {player: score_total(state["scores"].get(player)) for player in players}
        winner = loser = None
        if len(players) >= 2:
            first, second = players[:2]
            if totals[first] > totals[second]:
                winner, loser = first, second
            elif totals[second] > totals[first]:
                winner, loser = second, first
        state["game_over"] = True
        state["winner"] = winner
        state["loser"] = loser
        state["end_reason"] = end_reason
        state["turn_start_time"] = None
    else:
        next_player = next((player for player in players if player != username), username)
        state["turn"] = next_player
        state["dice"] = [1] * 5
        state["kept"] = [0] * 5
        state["rolls_left"] = 3
        state.setdefault("player_dice", {})[next_player] = [1] * 5
        state.setdefault("player_kept", {})[next_player] = [0] * 5
        state.setdefault("player_rolls_left", {})[next_player] = 3
        # 추천은 이전 플레이어의 주사위에 대한 결과이므로 턴을 넘길 때 공유
        # 상태에서 제거한다. 다음 플레이어는 자신의 첫 굴림 뒤 새로 계산한다.
        state["ai_rec"] = None
        state["winner"] = None
        state["loser"] = None
        state["end_reason"] = None
        state["turn_start_time"] = now

    state["version"] = state.get("version", 0) + 1
    state["updated_by"] = updated_by or username
    state.pop("timeout_event", None)
    room["state"] = state
    room["last_update"] = now
    return {
        "category_idx": category_idx,
        "score": score,
        "yacht_bonus": yacht_bonus,
        "game_over": bool(state.get("game_over")),
        "state": state,
    }


def advance_expired_turn(room, code, turn_limit, now=None):
    """Apply one server-authoritative timeout action when a turn has expired.

    A timeout follows the behaviour the game previously attempted in browser
    JavaScript: roll with the player's current keep selection while rolls
    remain, then bank the highest immediate open score.  Making this a state
    transition on the server prevents a paused or modified client from
    holding a room indefinitely.
    """
    now = now or time.time()
    state = room.get("state") or {}
    player = state.get("turn")
    started_at = state.get("turn_start_time")
    players = room.get("players", [])
    if (
        not room.get("started_full")
        or state.get("game_over")
        or player not in players
        or not isinstance(started_at, (int, float))
        or now - started_at < turn_limit
    ):
        return None

    kept = list(state.get("kept", [0] * 5))
    rolls_left = state.get("rolls_left", 3)
    if not isinstance(rolls_left, int) or rolls_left < 0 or rolls_left > 3:
        return None

    event = {"type": "timeout", "player": player}
    if rolls_left > 0:
        roll_room_dice(room, code, kept)
        event["action"] = "roll"
    else:
        scorecard = state.get("scores", {}).get(player)
        if not isinstance(scorecard, list):
            return None
        open_categories = [index for index, score in enumerate(scorecard) if score is None]
        if not open_categories:
            return None
        dice = state.get("dice", [1] * 5)
        category_idx = max(open_categories, key=lambda index: (calc_score(dice, index), -index))
        result = record_room_score(
            room, player, category_idx, now=now, updated_by="system_timeout", end_reason="timeout_score"
        )
        state = room["state"]
        event.update({"action": "score", **{key: result[key] for key in ("category_idx", "score", "yacht_bonus")}})

    if event.get("action") == "roll":
        state["turn_start_time"] = now
        state["version"] = state.get("version", 0) + 1
        state["updated_by"] = "system_timeout"
    state["timeout_event"] = event
    room["state"] = state
    room["last_update"] = now
    return event
