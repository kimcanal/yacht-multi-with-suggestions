#!/usr/bin/env python3
"""Randomized soak validation for the Yacht AI solver."""

from __future__ import annotations

import argparse
import itertools
import math
import random
import statistics
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yacht_engine

ALL_SORTED_DICE = list(itertools.combinations_with_replacement(range(1, 7), 5))
POSSIBLE_SCORES = {
    idx: sorted({yacht_engine.calc_score(list(dice), idx) for dice in ALL_SORTED_DICE})
    for idx in range(12)
}


@dataclass
class SoakCase:
    kind: str
    dice: list[int]
    rolls_left: int
    scorecard: list[int | None]
    mode: str

    @property
    def open_categories(self) -> list[int]:
        return [idx for idx, value in enumerate(self.scorecard) if value is None]


def random_dice(rng: random.Random) -> list[int]:
    return [rng.randint(1, 6) for _ in range(5)]


def sampled_closed_score(rng: random.Random, category_idx: int) -> int:
    if category_idx == yacht_engine.CATS["Yacht"]:
        return rng.choice([0, 50, 150, 250])
    return rng.choice(POSSIBLE_SCORES[category_idx])


def random_partial_scorecard(rng: random.Random, open_count: int | None = None) -> list[int | None]:
    if open_count is None:
        open_count = rng.randint(1, 12)
    open_count = max(1, min(12, open_count))
    open_categories = set(rng.sample(range(12), k=open_count))
    scorecard: list[int | None] = []
    for idx in range(12):
        if idx in open_categories:
            scorecard.append(None)
        else:
            scorecard.append(sampled_closed_score(rng, idx))
    return scorecard


def build_case(rng: random.Random) -> SoakCase:
    kind = rng.choices(
        population=[
            "generic",
            "upper_bonus_near",
            "yacht_bonus_active",
            "lowers_closed",
            "one_slot_left",
        ],
        weights=[8, 3, 2, 2, 1],
        k=1,
    )[0]

    mode = rng.choice(["focused", "cover"])
    rolls_left = rng.choice([0, 1, 2])

    if kind == "upper_bonus_near":
        scorecard = random_partial_scorecard(rng, open_count=rng.randint(4, 8))
        upper_total = 0
        for idx in range(6):
            if scorecard[idx] is None:
                continue
            scorecard[idx] = rng.choice([0, (idx + 1) * 2, (idx + 1) * 3, (idx + 1) * 4])
            upper_total += scorecard[idx] or 0

        if upper_total < 42:
            for idx in range(6):
                if scorecard[idx] is not None:
                    scorecard[idx] = (scorecard[idx] or 0) + (idx + 1) * 3
                    upper_total = sum((value or 0) for value in scorecard[:6] if value is not None)
                    if upper_total >= 42:
                        break

        if all(value is not None for value in scorecard[:6]):
            scorecard[rng.randrange(6)] = None
        dice = [6, 6, 6, rng.randint(1, 6), rng.randint(1, 6)]
        rolls_left = rng.choice([1, 2])
    elif kind == "yacht_bonus_active":
        scorecard = random_partial_scorecard(rng, open_count=rng.randint(4, 8))
        scorecard[yacht_engine.CATS["Yacht"]] = rng.choice([50, 150, 250])
        if all(value is not None for value in scorecard):
            scorecard[rng.randrange(11)] = None
        dice = [rng.randint(1, 6)] * 3 + [rng.randint(1, 6), rng.randint(1, 6)]
        rolls_left = rng.choice([1, 2])
    elif kind == "lowers_closed":
        scorecard = random_partial_scorecard(rng, open_count=rng.randint(2, 6))
        for name in ["Choice", "4 of a Kind", "Full House", "Small Straight", "Large Straight", "Yacht"]:
            idx = yacht_engine.CATS[name]
            if scorecard[idx] is None:
                scorecard[idx] = sampled_closed_score(rng, idx)
        if all(value is not None for value in scorecard):
            scorecard[rng.randrange(6)] = None
        dice = random_dice(rng)
    elif kind == "one_slot_left":
        scorecard = random_partial_scorecard(rng, open_count=1)
        dice = random_dice(rng)
    else:
        scorecard = random_partial_scorecard(rng)
        dice = random_dice(rng)

    return SoakCase(
        kind=kind,
        dice=dice,
        rolls_left=rolls_left,
        scorecard=scorecard,
        mode=mode,
    )


def percentile(sorted_values: list[float], ratio: float) -> float:
    if not sorted_values:
        return 0.0
    idx = min(len(sorted_values) - 1, max(0, math.ceil(len(sorted_values) * ratio) - 1))
    return sorted_values[idx]


def validate_result(case: SoakCase, result: dict) -> list[str]:
    errors: list[str] = []
    expected_stage = "score" if case.rolls_left == 0 else "roll"

    if result.get("stage") != expected_stage:
        errors.append(f"stage mismatch: expected {expected_stage}, got {result.get('stage')}")

    expected_mode = case.mode if case.mode in ("focused", "cover") else "focused"
    if result.get("strategy_mode") != expected_mode:
        errors.append(f"strategy_mode mismatch: expected {expected_mode}, got {result.get('strategy_mode')}")

    expected_value = result.get("expected_value")
    if not isinstance(expected_value, (int, float)) or not math.isfinite(expected_value):
        errors.append(f"expected_value is not finite: {expected_value!r}")

    keep_indices = result.get("keep_indices")
    if not isinstance(keep_indices, list):
        errors.append("keep_indices is not a list")
        keep_indices = []
    if len(set(keep_indices)) != len(keep_indices):
        errors.append(f"duplicate keep_indices: {keep_indices!r}")
    if any(not isinstance(idx, int) or idx < 0 or idx > 4 for idx in keep_indices):
        errors.append(f"invalid keep_indices contents: {keep_indices!r}")
    if keep_indices != sorted(keep_indices):
        errors.append(f"keep_indices are not sorted: {keep_indices!r}")

    for field in ("message", "summary"):
        value = result.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} missing or blank")

    breakdown = result.get("breakdown")
    if not isinstance(breakdown, list):
        errors.append("breakdown is not a list")
        breakdown = []
    elif not breakdown and case.open_categories:
        errors.append("breakdown unexpectedly empty")
    else:
        for row in breakdown:
            if not isinstance(row, dict):
                errors.append(f"breakdown row is not a dict: {row!r}")
                continue
            name = row.get("name")
            if not isinstance(name, str) or not name.strip():
                errors.append(f"breakdown row missing name: {row!r}")
            row_keep_indices = row.get("keep_indices", [])
            if not isinstance(row_keep_indices, list):
                errors.append(f"breakdown keep_indices invalid: {row_keep_indices!r}")
            elif any(not isinstance(idx, int) or idx < 0 or idx > 4 for idx in row_keep_indices):
                errors.append(f"breakdown keep_indices out of range: {row_keep_indices!r}")

    dice_recommendations = result.get("dice_recommendations")
    if expected_stage == "roll":
        if not isinstance(dice_recommendations, list) or len(dice_recommendations) != 5:
            errors.append("roll stage should return 5 dice_recommendations")
        else:
            seen_indices = []
            for item in dice_recommendations:
                if not isinstance(item, dict):
                    errors.append(f"invalid dice_recommendation entry: {item!r}")
                    continue
                idx = item.get("index")
                seen_indices.append(idx)
                if idx not in range(5):
                    errors.append(f"invalid dice_recommendation index: {idx!r}")
                    continue
                if item.get("value") != case.dice[idx]:
                    errors.append(
                        f"dice value mismatch at index {idx}: expected {case.dice[idx]}, got {item.get('value')}"
                    )
                expected_action = "keep" if idx in keep_indices else "reroll"
                if item.get("action") != expected_action:
                    errors.append(
                        f"action mismatch at index {idx}: expected {expected_action}, got {item.get('action')}"
                    )
            if sorted(seen_indices) != [0, 1, 2, 3, 4]:
                errors.append(f"dice_recommendation indices invalid: {seen_indices!r}")
    else:
        if keep_indices:
            errors.append(f"score stage should not return keep_indices: {keep_indices!r}")
        if dice_recommendations not in ([], None):
            errors.append(f"score stage should not return dice_recommendations: {dice_recommendations!r}")

    cover_success_prob = result.get("cover_success_prob")
    cover_fail_prob = result.get("cover_fail_prob")
    if cover_success_prob is not None or cover_fail_prob is not None:
        if not isinstance(cover_success_prob, (int, float)) or not math.isfinite(cover_success_prob):
            errors.append(f"cover_success_prob invalid: {cover_success_prob!r}")
        if not isinstance(cover_fail_prob, (int, float)) or not math.isfinite(cover_fail_prob):
            errors.append(f"cover_fail_prob invalid: {cover_fail_prob!r}")
        if isinstance(cover_success_prob, (int, float)) and not (0.0 <= cover_success_prob <= 1.0):
            errors.append(f"cover_success_prob out of range: {cover_success_prob!r}")
        if isinstance(cover_fail_prob, (int, float)) and not (0.0 <= cover_fail_prob <= 1.0):
            errors.append(f"cover_fail_prob out of range: {cover_fail_prob!r}")
        if (
            isinstance(cover_success_prob, (int, float))
            and isinstance(cover_fail_prob, (int, float))
            and abs((cover_success_prob + cover_fail_prob) - 1.0) > 1e-5
        ):
            errors.append(
                "cover probabilities do not sum to 1: "
                f"{cover_success_prob!r} + {cover_fail_prob!r}"
            )

    return errors


def format_case(case: SoakCase) -> str:
    return (
        f"kind={case.kind} mode={case.mode} rolls_left={case.rolls_left} "
        f"dice={case.dice} scorecard={case.scorecard}"
    )


def run_soak(args: argparse.Namespace) -> int:
    rng = random.Random(args.seed)
    timings_ms: list[float] = []
    failures: list[str] = []
    deterministic_checks = 0
    kind_counts: Counter[str] = Counter()
    mode_counts: Counter[str] = Counter()

    for case_index in range(1, args.cases + 1):
        case = build_case(rng)
        kind_counts[case.kind] += 1
        mode_counts[case.mode] += 1
        scorecard_before = list(case.scorecard)
        dice_before = list(case.dice)

        if args.cold_cache:
            yacht_engine.clear_solver_cache()

        started = time.perf_counter()
        result = yacht_engine.solve_best_move(
            case.dice,
            case.rolls_left,
            case.open_categories,
            case.mode,
            case.scorecard,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        timings_ms.append(elapsed_ms)

        if case.scorecard != scorecard_before:
            failures.append(f"[case {case_index}] scorecard mutated: {format_case(case)}")
        if case.dice != dice_before:
            failures.append(f"[case {case_index}] dice mutated: {format_case(case)}")

        errors = validate_result(case, result)
        if errors:
            failures.append(f"[case {case_index}] {format_case(case)} :: " + " | ".join(errors))
            if args.fail_fast:
                break

        if case_index % args.determinism_every == 0:
            deterministic_checks += 1
            second = yacht_engine.solve_best_move(
                list(case.dice),
                case.rolls_left,
                list(case.open_categories),
                case.mode,
                list(case.scorecard),
            )
            if result != second:
                failures.append(
                    f"[case {case_index}] non-deterministic result for {format_case(case)}"
                )
                if args.fail_fast:
                    break

        if args.report_every and case_index % args.report_every == 0:
            timings_sorted = sorted(timings_ms)
            print(
                f"[progress] {case_index}/{args.cases} cases, "
                f"avg={statistics.mean(timings_ms):.2f}ms "
                f"p95={percentile(timings_sorted, 0.95):.2f}ms "
                f"failures={len(failures)}"
            )

    timings_sorted = sorted(timings_ms)
    avg_ms = statistics.mean(timings_ms) if timings_ms else 0.0

    print(
        f"Soak complete: cases={len(timings_ms)} seed={args.seed} "
        f"cold_cache={'yes' if args.cold_cache else 'no'} determinism_checks={deterministic_checks}"
    )
    print(
        f"Latency: min={min(timings_ms):.2f}ms avg={avg_ms:.2f}ms "
        f"p95={percentile(timings_sorted, 0.95):.2f}ms "
        f"p99={percentile(timings_sorted, 0.99):.2f}ms max={max(timings_ms):.2f}ms"
    )
    print(
        "Case mix: "
        + ", ".join(f"{kind}={count}" for kind, count in sorted(kind_counts.items()))
    )
    print(
        "Mode mix: "
        + ", ".join(f"{mode}={count}" for mode, count in sorted(mode_counts.items()))
    )

    if failures:
        print(f"Failures: {len(failures)}")
        for failure in failures[: args.max_failures]:
            print(f"  - {failure}")
        if len(failures) > args.max_failures:
            print(f"  ... {len(failures) - args.max_failures} more")
        return 1

    print("Failures: 0")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=250, help="number of randomized cases to run")
    parser.add_argument("--seed", type=int, default=20260411, help="random seed for reproducibility")
    parser.add_argument("--cold-cache", action="store_true", help="clear solver cache before each case")
    parser.add_argument("--fail-fast", action="store_true", help="stop at the first failure")
    parser.add_argument(
        "--determinism-every",
        type=int,
        default=25,
        help="rerun every Nth case and assert the solver returns the exact same result",
    )
    parser.add_argument("--max-failures", type=int, default=10, help="max failures to print")
    parser.add_argument(
        "--report-every",
        type=int,
        default=0,
        help="print progress every N cases (0 disables progress logs)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raise SystemExit(run_soak(args))


if __name__ == "__main__":
    main()
