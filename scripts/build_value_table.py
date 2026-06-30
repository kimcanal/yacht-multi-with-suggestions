#!/usr/bin/env python3
"""Build an experimental full-game value table for Yacht score decisions.

The table uses a compressed state:
  (closed_category_mask, capped_upper_total, yacht_bonus_available)

It is intentionally an offline experiment.  Small --max-exact-open values are
useful for smoke tests and endgame validation; --max-exact-open 12 attempts the
full horizon and can be expensive.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from yacht_ai.constants import CATS, CATEGORY_NAMES, FRESH_TURN_CATEGORY_EV, UPPER_BONUS_VALUE
from yacht_ai.scoring import (
    DICE_STATES,
    calc_score,
    get_keep_options,
    get_outcomes_probs,
    get_transition_distribution,
)

YACHT_IDX = CATS["Yacht"]
ALL_CLOSED_MASK = (1 << len(CATEGORY_NAMES)) - 1


class StateLimitReached(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an experimental Yacht full-game value table.")
    parser.add_argument("--max-exact-open", type=int, default=4, help="exactly solve states with at most N open categories")
    parser.add_argument("--max-states", type=int, default=250000, help="abort after this many value states")
    parser.add_argument(
        "--open",
        default="",
        help="comma-separated category names to leave open; default starts from a fully open game",
    )
    parser.add_argument("--upper-total", type=int, default=0, help="starting capped upper total")
    parser.add_argument("--yacht-bonus", action="store_true", help="start with Yacht bonus available")
    parser.add_argument("--output", default="", help="optional JSON artifact path")
    parser.add_argument("--sample-states", type=int, default=20, help="number of computed states to store in JSON")
    return parser.parse_args()


def open_categories(mask: int) -> list[int]:
    return [idx for idx in range(len(CATEGORY_NAMES)) if not (mask & (1 << idx))]


def open_upper_faces(mask: int) -> tuple[int, ...]:
    return tuple(idx + 1 for idx in range(6) if not (mask & (1 << idx)))


@lru_cache(maxsize=None)
def upper_bonus_probability(current_upper: int, open_faces: tuple[int, ...]) -> float:
    capped_upper = max(0, min(int(current_upper), 63))
    if capped_upper >= 63:
        return 1.0
    if not open_faces:
        return 0.0

    # Same fresh-turn upper count distribution as yacht_ai.constants, inlined
    # to keep this script independent of private advice.py helpers.
    count_probs = {
        0: 0.06490547,
        1: 0.23625592,
        2: 0.34398861,
        3: 0.25042371,
        4: 0.09115423,
        5: 0.01327206,
    }
    dist = {capped_upper: 1.0}
    for face in open_faces:
        next_dist: dict[int, float] = {}
        for subtotal, subtotal_prob in dist.items():
            for count, count_prob in count_probs.items():
                next_total = min(63, subtotal + face * count)
                next_dist[next_total] = next_dist.get(next_total, 0.0) + subtotal_prob * count_prob
        dist = next_dist
    return sum(prob for total, prob in dist.items() if total >= 63)


def heuristic_tail_value(mask: int, upper_total: int, yacht_bonus_available: bool) -> float:
    value = 0.0
    for category_idx in open_categories(mask):
        value += FRESH_TURN_CATEGORY_EV.get(CATEGORY_NAMES[category_idx], 0.0)
    if upper_total < 63:
        value += UPPER_BONUS_VALUE * upper_bonus_probability(upper_total, open_upper_faces(mask))
    # Repeated Yacht Bonus is real but rare.  The exact endgame horizon handles
    # it; the tail heuristic leaves it out rather than inventing a large prior.
    return value


def score_transition(
    mask: int,
    upper_total: int,
    yacht_bonus_available: bool,
    dice: tuple[int, ...],
    category_idx: int,
) -> tuple[float, tuple[int, int, bool]]:
    score = calc_score(dice, category_idx)
    gain = float(score)

    next_upper = upper_total
    if category_idx < 6:
        next_upper = min(63, upper_total + score)
        if upper_total < 63 <= upper_total + score:
            gain += UPPER_BONUS_VALUE

    if (
        yacht_bonus_available
        and category_idx != YACHT_IDX
        and calc_score(dice, YACHT_IDX) == 50
        and score > 0
    ):
        gain += 100.0

    next_yacht_bonus = yacht_bonus_available or (category_idx == YACHT_IDX and score >= 50)
    next_mask = mask | (1 << category_idx)
    return gain, (next_mask, next_upper, next_yacht_bonus)


def mask_from_open_arg(open_arg: str) -> int:
    if not open_arg.strip():
        return 0
    open_names = {name.strip() for name in open_arg.split(",") if name.strip()}
    unknown = sorted(name for name in open_names if name not in CATS)
    if unknown:
        raise SystemExit(f"unknown category in --open: {', '.join(unknown)}")

    mask = ALL_CLOSED_MASK
    for name in open_names:
        mask &= ~(1 << CATS[name])
    return mask


def build_value_table_from_state(
    start_mask: int,
    start_upper_total: int,
    start_yacht_bonus: bool,
    max_exact_open: int,
    max_states: int,
) -> tuple[dict[tuple[int, int, bool], float], float]:
    value_cache: dict[tuple[int, int, bool], float] = {}

    def value(mask: int, upper_total: int, yacht_bonus_available: bool) -> float:
        state = (mask, upper_total, yacht_bonus_available)
        cached = value_cache.get(state)
        if cached is not None:
            return cached
        if len(value_cache) >= max_states:
            raise StateLimitReached(f"state limit reached: {max_states}")
        if mask == ALL_CLOSED_MASK:
            value_cache[state] = 0.0
            return 0.0

        open_count = len(open_categories(mask))
        if open_count > max_exact_open:
            fallback = heuristic_tail_value(mask, upper_total, yacht_bonus_available)
            value_cache[state] = fallback
            return fallback

        cats = open_categories(mask)

        @lru_cache(maxsize=None)
        def roll_value(dice: tuple[int, ...], rolls_left: int) -> float:
            stop_candidates = []
            for category_idx in cats:
                gain, next_state = score_transition(
                    mask, upper_total, yacht_bonus_available, dice, category_idx
                )
                stop_candidates.append(gain + value(*next_state))
            stop_value = max(stop_candidates)
            if rolls_left <= 0:
                return stop_value

            best = stop_value
            for kept_tuple in get_keep_options(dice):
                candidate = 0.0
                for next_dice, prob in get_transition_distribution(kept_tuple):
                    candidate += prob * roll_value(next_dice, rolls_left - 1)
                if candidate > best:
                    best = candidate
            return best

        turn_ev = 0.0
        for initial_roll, prob in get_outcomes_probs(5):
            turn_ev += prob * roll_value(initial_roll, 2)
        value_cache[state] = turn_ev
        return turn_ev

    start_value = value(start_mask, max(0, min(63, start_upper_total)), start_yacht_bonus)
    return value_cache, start_value


def encode_state(state: tuple[int, int, bool]) -> str:
    mask, upper_total, yacht_bonus_available = state
    return f"{mask}:{upper_total}:{1 if yacht_bonus_available else 0}"


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    status = "ok"
    error = None
    start_mask = mask_from_open_arg(args.open)
    start_upper_total = max(0, min(63, args.upper_total))
    try:
        values, initial_value = build_value_table_from_state(
            start_mask,
            start_upper_total,
            bool(args.yacht_bonus),
            args.max_exact_open,
            args.max_states,
        )
    except StateLimitReached as exc:
        status = "state_limit_reached"
        error = str(exc)
        values = {}
        initial_value = math.nan

    elapsed_s = time.perf_counter() - started
    sample = {
        encode_state(state): round(value, 6)
        for state, value in list(values.items())[: max(0, args.sample_states)]
    }
    payload = {
        "status": status,
        "error": error,
        "max_exact_open": args.max_exact_open,
        "max_states": args.max_states,
        "start_state": {
            "mask": start_mask,
            "upper_total": start_upper_total,
            "yacht_bonus_available": bool(args.yacht_bonus),
            "open_categories": [CATEGORY_NAMES[idx] for idx in open_categories(start_mask)],
        },
        "computed_states": len(values),
        "initial_value": None if math.isnan(initial_value) else round(initial_value, 6),
        "elapsed_seconds": round(elapsed_s, 3),
        "state_encoding": "closed_mask:upper_total:yacht_bonus_available",
        "sample_values": sample,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if status != "ok":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
