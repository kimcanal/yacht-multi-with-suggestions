#!/usr/bin/env python3
"""Generate self-play scorecard value targets.

Each JSONL row represents the scorecard state before a turn starts and the
final/remaining score reached by the exact self-play policy from that state.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from yacht_ai.self_play import play_self_play_game
from yacht_ai.value_model import VALUE_FEATURE_NAMES


def parse_args():
    parser = argparse.ArgumentParser(description="Generate full-game value-model JSONL from exact self-play.")
    parser.add_argument("--games", type=int, default=32, help="number of self-play games")
    parser.add_argument("--seed", type=int, default=20260708, help="base random seed")
    parser.add_argument("--mode", choices=("focused", "cover"), default="focused")
    parser.add_argument("--output", default="artifacts/generated/data/self-play-value-focused.jsonl")
    parser.add_argument("--summary-output", default="")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--report-every", type=int, default=8)
    parser.add_argument("--clear-cache-every", type=int, default=48)
    return parser.parse_args()


def flatten_sample(game_id, game_seed, sample):
    state = sample["state"]
    turn = sample["turn"]
    return {
        "game_id": game_id,
        "seed": game_seed,
        "turn_index": sample["turn_index"],
        "strategy_mode": state["strategy_mode"],
        "scorecard": state["scorecard"],
        "scorecard_after": sample["scorecard_after"],
        "turns_completed": state["turns_completed"],
        "open_categories": state["open_categories"],
        "open_category_names": state["open_category_names"],
        "open_mask": state["open_mask"],
        "closed_mask": state["closed_mask"],
        "upper_score": state["upper_score"],
        "upper_gap": state["upper_gap"],
        "upper_bonus_obtained": state["upper_bonus_obtained"],
        "lower_score": state["lower_score"],
        "current_total": state["current_total"],
        "yacht_value": state["yacht_value"],
        "yacht_bonus_active": state["yacht_bonus_active"],
        "feature_values": state["feature_values"],
        "target_final_score": sample["target_final_score"],
        "target_remaining_score": sample["target_remaining_score"],
        "target_upper_bonus": sample["target_upper_bonus"],
        "turn_score_delta": sample["turn_score_delta"],
        "initial_dice": turn["initial_dice"],
        "final_dice": turn["final_dice"],
        "scored_category_idx": turn["category_idx"],
        "scored_category_name": turn["category_name"],
        "scored_points": turn["score"],
        "yacht_bonus_awarded": turn["yacht_bonus_awarded"],
    }


def summarize(games, samples, args):
    totals = [game["final_score"] for game in games]
    upper_bonus_flags = [1 if game["final_totals"]["upper_bonus"] else 0 for game in games]
    return {
        "model_family": "scorecard_value_self_play_v1",
        "games": len(games),
        "samples": len(samples),
        "seed": args.seed,
        "mode": args.mode,
        "feature_names": list(VALUE_FEATURE_NAMES),
        "target": "target_remaining_score",
        "avg_final_score": round(statistics.fmean(totals), 4),
        "median_final_score": round(statistics.median(totals), 4),
        "stdev_final_score": round(statistics.pstdev(totals), 4) if len(totals) > 1 else 0.0,
        "min_final_score": min(totals),
        "max_final_score": max(totals),
        "upper_bonus_rate": round(statistics.fmean(upper_bonus_flags), 6),
        "avg_target_remaining": round(statistics.fmean(row["target_remaining_score"] for row in samples), 4),
        "avg_turn_delta": round(statistics.fmean(row["turn_score_delta"] for row in samples), 4),
        "output": args.output,
    }


def main():
    args = parse_args()
    output_path = Path(args.output)
    if output_path.exists() and not args.overwrite:
        raise SystemExit(f"{output_path} already exists. Use --overwrite to replace it.")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    games = []
    rows = []
    with output_path.open("w", encoding="utf-8") as handle:
        for game_id in range(args.games):
            game_seed = args.seed + game_id * 1009
            game = play_self_play_game(
                game_seed,
                args.mode,
                clear_cache_every=args.clear_cache_every,
            )
            games.append(game)
            for sample in game["samples"]:
                row = flatten_sample(game_id, game_seed, sample)
                rows.append(row)
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            if args.report_every and ((game_id + 1) % args.report_every == 0 or game_id + 1 == args.games):
                print(f"[value-data] games={game_id + 1}/{args.games} samples={len(rows)}")

    summary = summarize(games, rows, args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.summary_output:
        summary_path = Path(args.summary_output)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
