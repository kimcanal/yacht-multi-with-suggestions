#!/usr/bin/env python3
"""Estimate long-run opportunity cost of closing categories early."""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yacht_engine
from yacht_ai.constants import CATEGORY_NAMES, CATS
from yacht_ai.ml_policy import RollPolicyModel
from yacht_ai.scoring import calc_score

MODEL_CACHE: dict[str, RollPolicyModel] = {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Estimate long-run score loss when a category is pre-closed.")
    parser.add_argument("--trials", type=int, default=24, help="games per category")
    parser.add_argument("--workers", type=int, default=4, help="parallel workers")
    parser.add_argument("--seed", type=int, default=20260412, help="base seed")
    parser.add_argument(
        "--model",
        default="artifacts/roll_policy_model.json",
        help="learned roll policy path used during rollout",
    )
    parser.add_argument("--mode", default="focused", choices=["focused", "cover"], help="strategy mode")
    parser.add_argument("--output", default="", help="optional JSON output path")
    return parser.parse_args()


def total_score(card: list[int | None]) -> int:
    upper = sum((value or 0) for value in card[:6])
    bonus = 35 if upper >= 63 else 0
    lower = sum((value or 0) for value in card[6:])
    return upper + bonus + lower


def reroll_from_keep(rng: random.Random, dice: list[int], keep_indices: list[int]) -> list[int]:
    keep = set(keep_indices)
    return [value if idx in keep else rng.randint(1, 6) for idx, value in enumerate(dice)]


def score_stage_pick(dice: list[int], scorecard: list[int | None], mode: str) -> None:
    open_categories = [idx for idx, value in enumerate(scorecard) if value is None]
    result = yacht_engine.solve_best_move(dice, 0, open_categories, mode, scorecard)
    cat_name = result.get("primary_target") or result.get("message")
    category_idx = CATS.get(cat_name)

    if category_idx is None or scorecard[category_idx] is not None:
        category_idx = max(open_categories, key=lambda idx: calc_score(dice, idx))

    score = calc_score(dice, category_idx)
    if (
        calc_score(dice, CATS["Yacht"]) == 50
        and isinstance(scorecard[CATS["Yacht"]], (int, float))
        and scorecard[CATS["Yacht"]] >= 50
        and category_idx != CATS["Yacht"]
        and score > 0
    ):
        scorecard[CATS["Yacht"]] += 100

    scorecard[category_idx] = score


def play_turn(
    rng: random.Random,
    scorecard: list[int | None],
    mode: str,
    model_path: str,
    min_confidence: float = 0.95,
) -> None:
    model = MODEL_CACHE.get(model_path)
    if model is None:
        model = RollPolicyModel.load(model_path)
        MODEL_CACHE[model_path] = model
    dice = [rng.randint(1, 6) for _ in range(5)]
    rolls_left = 2

    while rolls_left > 0:
        open_categories = [idx for idx, value in enumerate(scorecard) if value is None]
        result = model.recommend_roll(dice, rolls_left, mode, scorecard, min_confidence=min_confidence)
        if result is None:
            result = yacht_engine.solve_best_move(dice, rolls_left, open_categories, mode, scorecard)
        if len(result.get("keep_indices", [])) == 5:
            break
        dice = reroll_from_keep(rng, dice, result.get("keep_indices", []))
        rolls_left -= 1

    score_stage_pick(dice, scorecard, mode)


def simulate_game(
    closed_category_idx: int | None,
    seed: int,
    mode: str,
    model_path: str,
) -> int:
    rng = random.Random(seed)
    scorecard: list[int | None] = [None] * 12
    if closed_category_idx is not None:
        scorecard[closed_category_idx] = 0

    while any(value is None for value in scorecard):
        play_turn(rng, scorecard, mode, model_path)

    return total_score(scorecard)


def run_bucket(
    closed_category_idx: int | None,
    trials: int,
    seed: int,
    mode: str,
    model_path: str,
) -> dict:
    label = "baseline" if closed_category_idx is None else CATEGORY_NAMES[closed_category_idx]
    totals = [
        simulate_game(closed_category_idx, seed + trial_idx * 9973 + (closed_category_idx or 0) * 131, mode, model_path)
        for trial_idx in range(trials)
    ]
    return {
        "label": label,
        "category_idx": closed_category_idx,
        "trials": trials,
        "avg_total": round(statistics.mean(totals), 3),
        "stdev_total": round(statistics.pstdev(totals), 3),
        "min_total": min(totals),
        "max_total": max(totals),
        "totals": totals,
    }


def main() -> None:
    args = parse_args()
    categories: list[int | None] = [None] + list(range(12))
    results = []

    with ProcessPoolExecutor(max_workers=max(1, int(args.workers))) as executor:
        future_map = {
            executor.submit(run_bucket, category_idx, args.trials, args.seed, args.mode, args.model): category_idx
            for category_idx in categories
        }
        for future in as_completed(future_map):
            results.append(future.result())

    results.sort(key=lambda row: (-1 if row["category_idx"] is None else row["category_idx"]))
    baseline = next(row for row in results if row["category_idx"] is None)
    baseline_avg = baseline["avg_total"]

    summary = []
    for row in results:
        if row["category_idx"] is None:
            continue
        summary.append(
            {
                "label": row["label"],
                "avg_total": row["avg_total"],
                "closing_cost": round(baseline_avg - row["avg_total"], 3),
                "stdev_total": row["stdev_total"],
            }
        )

    payload = {
        "mode": args.mode,
        "trials": args.trials,
        "seed": args.seed,
        "baseline": baseline,
        "summary": summary,
    }

    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
