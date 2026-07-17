#!/usr/bin/env python3
"""Compare exact and learned roll policies over complete games."""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yacht_engine
from yacht_ai.constants import CATS
from yacht_ai.ml_policy import RollPolicyModel
from yacht_ai.scoring import calc_score


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paired full-game simulations for roll-policy variants.")
    parser.add_argument("--games", type=int, default=32, help="games per policy")
    parser.add_argument("--seed", type=int, default=20260630, help="base random seed")
    parser.add_argument("--mode", choices=("focused", "cover"), default="focused", help="strategy mode")
    parser.add_argument("--model-v1", default="artifacts/runtime/models/model-20260630-roll-policy-v1.json")
    parser.add_argument("--model-v2", default="artifacts/runtime/models/model-20260630-roll-policy-v2.json")
    parser.add_argument("--label-v1", default="v1", help="report label for --model-v1")
    parser.add_argument("--label-v2", default="v2", help="report label for --model-v2")
    parser.add_argument("--min-confidence", type=float, default=0.95)
    parser.add_argument("--output", help="optional JSON report path")
    return parser.parse_args()


def total_score(scorecard: list[int | None]) -> int:
    upper = sum((value or 0) for value in scorecard[:6])
    lower = sum((value or 0) for value in scorecard[6:])
    return int(upper + lower + (35 if upper >= 63 else 0))


def score_metrics(scorecard: list[int | None]) -> dict:
    upper = sum((value or 0) for value in scorecard[:6])
    yacht_slot = scorecard[CATS["Yacht"]] or 0
    yacht_bonus_count = max(0, int((yacht_slot - 50) // 100)) if yacht_slot >= 50 else 0
    return {
        "total_score": total_score(scorecard),
        "upper_score": int(upper),
        "upper_bonus": int(upper >= 63),
        "yacht_score": int(yacht_slot),
        "yacht_bonus_count": yacht_bonus_count,
        "zero_categories": sum(1 for value in scorecard if value == 0),
        "scorecard": list(scorecard),
    }


def reroll_from_keep(rng: random.Random, dice: list[int], keep_indices: list[int]) -> list[int]:
    keep = set(keep_indices)
    return [value if idx in keep else rng.randint(1, 6) for idx, value in enumerate(dice)]


def choose_score_category(dice: list[int], scorecard: list[int | None], mode: str) -> int:
    open_categories = [idx for idx, value in enumerate(scorecard) if value is None]
    result = yacht_engine.solve_best_move(dice, 0, open_categories, mode, scorecard)
    category_idx = CATS.get(result.get("primary_target"))
    if category_idx in open_categories:
        return category_idx

    for row in result.get("breakdown", []):
        category_idx = CATS.get(row.get("name"))
        if category_idx in open_categories:
            return category_idx

    return max(open_categories, key=lambda idx: calc_score(dice, idx))


def apply_score(dice: list[int], scorecard: list[int | None], category_idx: int) -> None:
    score = calc_score(dice, category_idx)
    yacht_idx = CATS["Yacht"]
    if (
        calc_score(dice, yacht_idx) == 50
        and isinstance(scorecard[yacht_idx], (int, float))
        and scorecard[yacht_idx] >= 50
        and category_idx != yacht_idx
        and score > 0
    ):
        scorecard[yacht_idx] += 100
    scorecard[category_idx] = score


def choose_keep(
    dice: list[int],
    rolls_left: int,
    scorecard: list[int | None],
    mode: str,
    policy: dict,
) -> tuple[list[int], str]:
    open_categories = [idx for idx, value in enumerate(scorecard) if value is None]
    policy_type = policy["type"]

    if policy_type == "exact":
        result = yacht_engine.solve_best_move(dice, rolls_left, open_categories, mode, scorecard)
        return list(result.get("keep_indices", [])), "exact"

    model: RollPolicyModel = policy["model"]
    if policy_type == "model_only":
        actions = model.predict_valid_actions(dice, rolls_left, mode, scorecard, top_k=1)
        if actions:
            return list(actions[0].get("keep_indices", [])), "model_only"
        result = yacht_engine.solve_best_move(dice, rolls_left, open_categories, mode, scorecard)
        return list(result.get("keep_indices", [])), "missing_fallback"

    if policy_type == "model_runtime":
        result = model.recommend_roll(
            dice,
            rolls_left,
            mode,
            scorecard,
            min_confidence=policy["min_confidence"],
        )
        if result is not None:
            return list(result.get("keep_indices", [])), "model_runtime"
        result = yacht_engine.solve_best_move(dice, rolls_left, open_categories, mode, scorecard)
        return list(result.get("keep_indices", [])), "exact_fallback"

    raise ValueError(f"Unknown policy type: {policy_type}")


def play_game(seed: int, mode: str, policy: dict) -> dict:
    rng = random.Random(seed)
    scorecard: list[int | None] = [None] * 12
    roll_decisions = {
        "exact": 0,
        "model_only": 0,
        "model_runtime": 0,
        "exact_fallback": 0,
        "missing_fallback": 0,
    }

    while any(value is None for value in scorecard):
        dice = [rng.randint(1, 6) for _ in range(5)]
        rolls_left = 2
        while rolls_left > 0:
            keep_indices, source = choose_keep(dice, rolls_left, scorecard, mode, policy)
            roll_decisions[source] = roll_decisions.get(source, 0) + 1
            if len(keep_indices) == 5:
                break
            dice = reroll_from_keep(rng, dice, keep_indices)
            rolls_left -= 1
        category_idx = choose_score_category(dice, scorecard, mode)
        apply_score(dice, scorecard, category_idx)

    metrics = score_metrics(scorecard)
    metrics["roll_decisions"] = roll_decisions
    return metrics


def summarize_policy(label: str, games: list[dict], exact_games: list[dict] | None = None) -> dict:
    totals = [game["total_score"] for game in games]
    paired_delta = []
    if exact_games is not None:
        paired_delta = [
            game["total_score"] - exact_game["total_score"]
            for game, exact_game in zip(games, exact_games)
        ]

    roll_decisions = {}
    for game in games:
        for key, value in game["roll_decisions"].items():
            roll_decisions[key] = roll_decisions.get(key, 0) + value

    return {
        "label": label,
        "games": len(games),
        "avg_total": round(statistics.fmean(totals), 4),
        "median_total": round(statistics.median(totals), 4),
        "stdev_total": round(statistics.pstdev(totals), 4),
        "min_total": min(totals),
        "max_total": max(totals),
        "avg_upper_score": round(statistics.fmean(game["upper_score"] for game in games), 4),
        "upper_bonus_rate": round(statistics.fmean(game["upper_bonus"] for game in games), 6),
        "avg_yacht_bonus_count": round(statistics.fmean(game["yacht_bonus_count"] for game in games), 6),
        "avg_zero_categories": round(statistics.fmean(game["zero_categories"] for game in games), 4),
        "avg_delta_vs_exact": round(statistics.fmean(paired_delta), 4) if paired_delta else 0.0,
        "median_delta_vs_exact": round(statistics.median(paired_delta), 4) if paired_delta else 0.0,
        "min_delta_vs_exact": min(paired_delta) if paired_delta else 0,
        "max_delta_vs_exact": max(paired_delta) if paired_delta else 0,
        "roll_decisions": roll_decisions,
        "totals": totals,
        "paired_delta_vs_exact": paired_delta,
    }


def main() -> None:
    args = parse_args()
    v1 = RollPolicyModel.load(args.model_v1)
    v2 = RollPolicyModel.load(args.model_v2)
    seeds = [args.seed + idx * 1009 for idx in range(args.games)]
    policies = [
        ("exact", {"type": "exact"}),
        (f"{args.label_v1}_runtime", {"type": "model_runtime", "model": v1, "min_confidence": args.min_confidence}),
        (f"{args.label_v2}_runtime", {"type": "model_runtime", "model": v2, "min_confidence": args.min_confidence}),
        (f"{args.label_v1}_model_only", {"type": "model_only", "model": v1}),
        (f"{args.label_v2}_model_only", {"type": "model_only", "model": v2}),
    ]

    raw_results = {}
    summaries = []
    for label, policy in policies:
        games = []
        for idx, seed in enumerate(seeds, start=1):
            games.append(play_game(seed, args.mode, policy))
            if idx % max(1, min(10, args.games)) == 0 or idx == args.games:
                print(f"[full-game-sim] policy={label} games={idx}/{args.games}")
        raw_results[label] = games
        summaries.append(summarize_policy(label, games, raw_results.get("exact")))

    report = {
        "mode": args.mode,
        "games": args.games,
        "seed": args.seed,
        "min_confidence": args.min_confidence,
        "policies": summaries,
    }

    print("[full-game-sim] summary")
    for row in summaries:
        print(
            f"- {row['label']}: avg={row['avg_total']:.2f} "
            f"delta={row['avg_delta_vs_exact']:+.2f} "
            f"upper_bonus={row['upper_bonus_rate']:.3f}"
        )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print(f"[full-game-sim] wrote report to {output_path}")


if __name__ == "__main__":
    main()
