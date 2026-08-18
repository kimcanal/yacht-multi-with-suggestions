"""Server-authoritative VS-AI game operations."""

from __future__ import annotations

import secrets
import time

import yacht_engine
from yacht_core import CATS
from yacht_core.simulation import apply_score, total_score

POLICY_MODE = "exact_memo"


def new_session(username):
    now = time.time()
    return {
        "id": secrets.token_urlsafe(18),
        "token": secrets.token_urlsafe(24),
        "kind": "vs_ai",
        "username": username,
        "policy_mode": POLICY_MODE,
        "dice": [1] * 5,
        "kept": [0] * 5,
        "rolls_left": 3,
        "scorecard": [None] * 12,
        "bot_scorecard": [None] * 12,
        "turn": "player",
        "finished": False,
        "final_score": None,
        "bot_final_score": None,
        "result_saved": False,
        "last_bot_action": None,
        "created_at": now,
        "updated_at": now,
    }


def public_state(session):
    return {
        "dice": list(session["dice"]),
        "kept": list(session["kept"]),
        "rolls_left": session["rolls_left"],
        "scorecard": list(session["scorecard"]),
        "opp_scorecard": list(session["bot_scorecard"]),
        "turn": session["turn"],
        "finished": session["finished"],
        "final_score": session["final_score"],
        "bot_final_score": session["bot_final_score"],
        "last_bot_action": session["last_bot_action"],
        "verified": True,
    }


def authenticate(session, username, token):
    if not session or session.get("kind") != "vs_ai":
        return "VS-AI 세션 인증 실패"
    if not isinstance(token, str) or not secrets.compare_digest(session.get("token", ""), token):
        return "VS-AI 세션 인증 실패"
    if session.get("username") != username:
        return "VS-AI 세션 사용자와 닉네임이 다릅니다"
    return None


def _roll(dice, kept):
    rolled = [secrets.randbelow(6) + 1 for _ in range(5)]
    return [dice[idx] if kept[idx] else rolled[idx] for idx in range(5)]


def roll_player(session, kept):
    if session["finished"]:
        raise ValueError("이미 종료된 VS-AI 세션입니다")
    if session["turn"] != "player":
        raise ValueError("현재 플레이어 턴이 아닙니다")
    if session["rolls_left"] <= 0:
        raise ValueError("남은 굴림 없음")
    if session["rolls_left"] == 3:
        kept = [0] * 5
    session["dice"] = _roll(session["dice"], kept)
    session["kept"] = list(kept)
    session["rolls_left"] -= 1
    session["updated_at"] = time.time()


def _exact_choice(dice, rolls_left, scorecard):
    open_categories = [idx for idx, score in enumerate(scorecard) if score is None]
    return yacht_engine.solve_best_move(
        dice,
        rolls_left,
        open_categories,
        "focused",
        scorecard,
        score_value_mode="value_score_only",
    )


def _bot_choice(dice, rolls_left, scorecard):
    return _exact_choice(dice, rolls_left, scorecard)


def _score_bot(session, dice, category_idx):
    score, bonus = apply_score(dice, session["bot_scorecard"], category_idx)
    session["last_bot_action"] = {
        "category_idx": category_idx,
        "category": next(name for name, idx in CATS.items() if idx == category_idx),
        "score": score,
        "bonus": bonus,
        "total_gain": score + bonus,
    }


def _best_score_category(dice, scorecard):
    choice = _exact_choice(dice, 0, scorecard)
    target = choice.get("primary_target")
    if target in CATS:
        return CATS[target]
    return max(
        (idx for idx, score in enumerate(scorecard) if score is None),
        key=lambda idx: yacht_engine.calc_score(dice, idx),
    )


def run_bot_turn(session):
    """Play the bot's complete turn using server dice and scorecard state."""
    if session["finished"] or session["turn"] != "bot":
        return
    dice = [1] * 5
    kept = [0] * 5
    rolls_left = 3
    while True:
        dice = _roll(dice, kept)
        rolls_left -= 1
        choice = _bot_choice(dice, rolls_left, session["bot_scorecard"])
        keep_indices = set(choice.get("keep_indices", []))
        all_kept = len(keep_indices) == 5
        if choice.get("stage") == "score" or rolls_left <= 0 or all_kept:
            _score_bot(session, dice, _best_score_category(dice, session["bot_scorecard"]))
            break
        kept = [1 if idx in keep_indices else 0 for idx in range(5)]

    session["dice"] = [1] * 5
    session["kept"] = [0] * 5
    session["rolls_left"] = 3
    session["turn"] = "player"
    if all(value is not None for value in session["scorecard"]) and all(
        value is not None for value in session["bot_scorecard"]
    ):
        session["finished"] = True
        session["final_score"] = total_score(session["scorecard"])
        session["bot_final_score"] = total_score(session["bot_scorecard"])
    session["updated_at"] = time.time()


def score_player(session, category_idx):
    if session["finished"]:
        raise ValueError("이미 종료된 VS-AI 세션입니다")
    if session["turn"] != "player":
        raise ValueError("현재 플레이어 턴이 아닙니다")
    if session["rolls_left"] >= 3:
        raise ValueError("점수 기록 전에는 최소 1회 굴려야 합니다")
    if category_idx < 0 or category_idx >= 12 or session["scorecard"][category_idx] is not None:
        raise ValueError("잘못된 점수칸입니다")

    score, bonus = apply_score(session["dice"], session["scorecard"], category_idx)
    session["last_bot_action"] = None
    session["turn"] = "bot"
    run_bot_turn(session)
    return score, bonus
