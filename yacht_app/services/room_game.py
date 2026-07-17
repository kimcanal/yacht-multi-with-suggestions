"""Pure multiplayer payload and state-transition services."""

import json

from app_state import get_services
from utils.validation import normalize_dice, normalize_rolls_left, safe_int
from yacht_app.services.room_lifecycle import default_room_state, room_phase, score_total
from yacht_core import CATS, calc_score

_YACHT_IDX = CATS["Yacht"]


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

    get_services().results.save_game_result(player1, score1, player2, score2)
    room["result_saved"] = True


rematch_payload = _rematch_payload
room_event_payload = _room_event_payload
sse_event = _sse_event
validate_sync_transition = _validate_sync_transition
finish_room_if_complete = _finish_room_if_complete
