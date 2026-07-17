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
import itertools
import json
import math
import sys
import time
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from yacht_ai.constants import CATEGORY_NAMES, CATS, FRESH_TURN_CATEGORY_EV, UPPER_BONUS_VALUE
from yacht_ai.scoring import (
    DICE_STATES,
    calc_score,
    get_keep_options,
    get_outcomes_probs,
    get_transition_distribution,
)

YACHT_IDX = CATS["Yacht"]
ALL_CLOSED_MASK = (1 << len(CATEGORY_NAMES)) - 1
DICE_INDEX = {dice: idx for idx, dice in enumerate(DICE_STATES)}


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
    parser.add_argument(
        "--output-format",
        choices=("auto", "json", "npz"),
        default="auto",
        help="batch output format; auto uses .npz suffix for dense numpy artifacts",
    )
    parser.add_argument("--sample-states", type=int, default=20, help="number of computed states to store in JSON")
    parser.add_argument(
        "--batch-open-count",
        type=int,
        default=None,
        help="compute every state with at most this many open categories and write a full value table",
    )
    parser.add_argument("--progress-every", type=int, default=0, help="print batch progress every N start states")
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


def iter_endgame_states(max_open_count: int):
    bounded_open = max(0, min(len(CATEGORY_NAMES), int(max_open_count)))
    category_indices = tuple(range(len(CATEGORY_NAMES)))
    for open_count in range(bounded_open + 1):
        for open_idxs in itertools.combinations(category_indices, open_count):
            mask = ALL_CLOSED_MASK
            for idx in open_idxs:
                mask &= ~(1 << idx)
            for upper_total in range(64):
                yield (mask, upper_total, False)
                yield (mask, upper_total, True)


def summarize_open_counts(values: dict[tuple[int, int, bool], float]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for mask, _upper_total, _yacht_bonus_available in values:
        open_count = len(open_categories(mask))
        key = str(open_count)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: int(item[0])))


def build_batch_roll_context():
    keep_tuples = tuple(
        itertools.combinations_with_replacement(range(1, 7), keep_size)
        for keep_size in range(6)
    )
    keep_tuples = tuple(itertools.chain.from_iterable(keep_tuples))
    keep_index = {kept_tuple: idx for idx, kept_tuple in enumerate(keep_tuples)}
    transition_matrix = np.zeros((len(keep_tuples), len(DICE_STATES)), dtype=np.float64)
    for kept_tuple, keep_idx in keep_index.items():
        for next_dice, prob in get_transition_distribution(kept_tuple):
            transition_matrix[keep_idx, DICE_INDEX[next_dice]] += prob

    allowed_keep_indices = [
        np.asarray([keep_index[kept_tuple] for kept_tuple in get_keep_options(dice)], dtype=np.int32)
        for dice in DICE_STATES
    ]
    initial_probs = np.zeros(len(DICE_STATES), dtype=np.float64)
    for dice, prob in get_outcomes_probs(5):
        initial_probs[DICE_INDEX[dice]] = prob
    return {
        "transition_matrix": transition_matrix,
        "allowed_keep_indices": allowed_keep_indices,
        "initial_probs": initial_probs,
    }


def exact_fresh_turn_ev_from_terminal(terminal_values, roll_context) -> float:
    terminal = np.asarray(terminal_values, dtype=np.float64)
    current = terminal
    transition_matrix = roll_context["transition_matrix"]
    allowed_keep_indices = roll_context["allowed_keep_indices"]
    for _roll in range(2):
        expected_by_keep = transition_matrix @ current
        next_values = np.empty_like(current)
        for dice_idx, keep_indices in enumerate(allowed_keep_indices):
            next_values[dice_idx] = max(terminal[dice_idx], float(np.max(expected_by_keep[keep_indices])))
        current = next_values
    return float(roll_context["initial_probs"] @ current)


def build_exact_endgame_batch_table(
    max_open_count: int,
    max_states: int,
    progress_every: int = 0,
) -> dict[tuple[int, int, bool], float]:
    bounded_open = max(0, min(len(CATEGORY_NAMES), int(max_open_count)))
    value_cache: dict[tuple[int, int, bool], float] = {}
    roll_context = build_batch_roll_context()
    total_start_states = sum(1 for _state in iter_endgame_states(bounded_open))
    processed = 0

    for open_count in range(bounded_open + 1):
        masks = []
        for open_idxs in itertools.combinations(range(len(CATEGORY_NAMES)), open_count):
            mask = ALL_CLOSED_MASK
            for idx in open_idxs:
                mask &= ~(1 << idx)
            masks.append(mask)

        for mask in masks:
            cats = open_categories(mask)
            for upper_total in range(64):
                for yacht_bonus_available in (False, True):
                    state = (mask, upper_total, yacht_bonus_available)
                    if state in value_cache:
                        processed += 1
                        continue
                    if len(value_cache) >= max_states:
                        raise StateLimitReached(f"state limit reached: {max_states}")
                    if not cats:
                        value_cache[state] = 0.0
                    else:
                        terminal_values = np.empty(len(DICE_STATES), dtype=np.float64)
                        for dice_idx, dice in enumerate(DICE_STATES):
                            best_value = float("-inf")
                            for category_idx in cats:
                                gain, next_state = score_transition(
                                    mask,
                                    upper_total,
                                    yacht_bonus_available,
                                    dice,
                                    category_idx,
                                )
                                best_value = max(best_value, gain + value_cache[next_state])
                            terminal_values[dice_idx] = best_value
                        value_cache[state] = exact_fresh_turn_ev_from_terminal(terminal_values, roll_context)
                    processed += 1
                    if progress_every and (processed % progress_every == 0 or processed == total_start_states):
                        print(f"[value-table] start_states={processed}/{total_start_states} computed_states={len(value_cache)}")
    return value_cache


def build_value_table_for_states(
    start_states,
    max_exact_open: int,
    max_states: int,
    progress_every: int = 0,
) -> tuple[dict[tuple[int, int, bool], float], dict[tuple[int, int, bool], float]]:
    value_cache: dict[tuple[int, int, bool], float] = {}

    def value(mask: int, upper_total: int, yacht_bonus_available: bool) -> float:
        state = (mask, max(0, min(63, upper_total)), bool(yacht_bonus_available))
        if state in value_cache:
            return value_cache[state]
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

    start_values = {}
    total_states = len(start_states) if hasattr(start_states, "__len__") else None
    for index, state in enumerate(start_states, start=1):
        normalized_state = (state[0], max(0, min(63, state[1])), bool(state[2]))
        start_values[normalized_state] = value(*normalized_state)
        if progress_every and (index % progress_every == 0 or index == total_states):
            total_label = total_states if total_states is not None else "?"
            print(f"[value-table] start_states={index}/{total_label} computed_states={len(value_cache)}")
    return value_cache, start_values


def build_value_table_from_state(
    start_mask: int,
    start_upper_total: int,
    start_yacht_bonus: bool,
    max_exact_open: int,
    max_states: int,
) -> tuple[dict[tuple[int, int, bool], float], float]:
    start_state = (start_mask, start_upper_total, start_yacht_bonus)
    value_cache, start_values = build_value_table_for_states(
        [start_state],
        max_exact_open,
        max_states,
    )
    return value_cache, start_values[(start_mask, max(0, min(63, start_upper_total)), bool(start_yacht_bonus))]


def encode_state(state: tuple[int, int, bool]) -> str:
    mask, upper_total, yacht_bonus_available = state
    return f"{mask}:{upper_total}:{1 if yacht_bonus_available else 0}"


def dense_values_from_cache(values: dict[tuple[int, int, bool], float]) -> np.ndarray:
    dense = np.full((1 << len(CATEGORY_NAMES), 64, 2), np.nan, dtype=np.float32)
    for (mask, upper_total, yacht_bonus_available), value in values.items():
        dense[int(mask), max(0, min(63, int(upper_total))), 1 if yacht_bonus_available else 0] = float(value)
    return dense


def batch_metadata(
    args: argparse.Namespace,
    started: float,
    values: dict[tuple[int, int, bool], float],
    batch_open_count: int,
) -> dict:
    elapsed_s = time.perf_counter() - started
    return {
        "status": "ok",
        "table_type": "endgame_exact_value_table",
        "batch_open_count": batch_open_count,
        "max_exact_open": batch_open_count,
        "max_states": args.max_states,
        "computed_states": len(values),
        "requested_start_states": len(values),
        "start_values": len(values),
        "elapsed_seconds": round(elapsed_s, 3),
        "state_encoding": "closed_mask:upper_total:yacht_bonus_available",
        "upper_total_cap": 63,
        "category_names": CATEGORY_NAMES,
        "open_count_counts": summarize_open_counts(values),
    }


def build_batch_payload(args: argparse.Namespace, started: float) -> tuple[dict, dict[tuple[int, int, bool], float]]:
    batch_open_count = max(0, min(len(CATEGORY_NAMES), int(args.batch_open_count)))
    values = build_exact_endgame_batch_table(
        batch_open_count,
        args.max_states,
        progress_every=max(0, args.progress_every),
    )
    payload = batch_metadata(args, started, values, batch_open_count)
    encoded_values = {
        encode_state(state): round(value, 6)
        for state, value in sorted(values.items())
    }
    payload["values"] = encoded_values
    return payload, values


def resolve_batch_output(args: argparse.Namespace, payload: dict) -> tuple[Path, str]:
    default_suffix = "npz" if args.output_format == "npz" else "json"
    default_output = f"artifacts/generated/value/endgame-value-table-open{payload['batch_open_count']}.{default_suffix}"
    output_path = Path(args.output or default_output)
    output_format = args.output_format
    if output_format == "auto":
        output_format = "npz" if output_path.suffix == ".npz" else "json"
    return output_path, output_format


def write_batch_npz(output_path: Path, payload: dict, values: dict[tuple[int, int, bool], float]) -> None:
    metadata = dict(payload)
    metadata.pop("values", None)
    dense_values = dense_values_from_cache(values)
    np.savez_compressed(
        output_path,
        values=dense_values,
        max_open_count=np.asarray(payload["batch_open_count"], dtype=np.int16),
        metadata_json=np.asarray(json.dumps(metadata, ensure_ascii=False)),
        category_names_json=np.asarray(json.dumps(CATEGORY_NAMES, ensure_ascii=False)),
    )


def main() -> None:
    args = parse_args()
    started = time.perf_counter()

    if args.batch_open_count is not None:
        values = {}
        try:
            payload, values = build_batch_payload(args, started)
        except StateLimitReached as exc:
            payload = {
                "status": "state_limit_reached",
                "error": str(exc),
                "batch_open_count": args.batch_open_count,
                "max_states": args.max_states,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
            }
        preview = dict(payload)
        if "values" in preview:
            preview["values"] = f"<{len(payload['values'])} encoded states>"
        print(json.dumps(preview, ensure_ascii=False, indent=2))

        output_path, output_format = resolve_batch_output(args, payload)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if payload["status"] == "ok" and output_format == "npz":
            write_batch_npz(output_path, payload, values)
        else:
            output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[value-table] wrote {payload.get('computed_states', 0)} states to {output_path}")
        if payload["status"] != "ok":
            raise SystemExit(2)
        return

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
