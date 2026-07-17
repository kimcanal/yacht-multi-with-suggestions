#!/usr/bin/env python3
"""Benchmark representative AI recommendation scenarios."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yacht_engine

SCENARIOS = [
    {
        "name": "straight_upgrade_focused",
        "mode": "focused",
        "dice": [1, 2, 3, 4, 6],
        "rolls_left": 1,
        "scorecard": [None] * 12,
    },
    {
        "name": "full_house_focus",
        "mode": "focused",
        "dice": [6, 6, 5, 1, 5],
        "rolls_left": 2,
        "scorecard": [None] * 12,
    },
    {
        "name": "full_house_cover",
        "mode": "cover",
        "dice": [6, 6, 5, 1, 5],
        "rolls_left": 2,
        "scorecard": [None] * 12,
    },
    {
        "name": "yacht_bonus_focused",
        "mode": "focused",
        "dice": [6, 6, 6, 2, 1],
        "rolls_left": 2,
        "scorecard": [3, None, 9, None, None, 18, 22, None, None, None, None, 50],
    },
    {
        "name": "yacht_bonus_cover",
        "mode": "cover",
        "dice": [6, 6, 6, 2, 1],
        "rolls_left": 2,
        "scorecard": [3, None, 9, None, None, 18, 22, None, None, None, None, 50],
    },
    {
        "name": "upper_bonus_finish_focused",
        "mode": "focused",
        "dice": [6, 6, 6, 1, 2],
        "rolls_left": 2,
        "scorecard": [3, 6, 9, 12, 15, None, None, None, None, None, None, None],
    },
]
def run_case(
    case: dict,
    repeats: int,
    warm_cache: bool,
    score_value_mode: str | None,
    value_table: str | None,
) -> dict:
    timings = []
    message = ""
    summary = ""
    policy_source = ""
    open_categories = [i for i, value in enumerate(case["scorecard"]) if value is None]
    if warm_cache:
        yacht_engine.clear_solver_cache()
        yacht_engine.solve_best_move(
            case["dice"],
            case["rolls_left"],
            open_categories,
            case["mode"],
            case["scorecard"],
            score_value_mode=score_value_mode,
            endgame_value_table_path=value_table,
        )
    for _ in range(repeats):
        if not warm_cache:
            yacht_engine.clear_solver_cache()
        started = time.perf_counter()
        result = yacht_engine.solve_best_move(
            case["dice"],
            case["rolls_left"],
            open_categories,
            case["mode"],
            case["scorecard"],
            score_value_mode=score_value_mode,
            endgame_value_table_path=value_table,
        )
        timings.append((time.perf_counter() - started) * 1000)
        message = result.get("message", "")
        summary = result.get("summary", "")
        policy_source = result.get("policy_source", "")
    return {
        "name": case["name"],
        "mode": case["mode"],
        "rolls_left": case["rolls_left"],
        "min_ms": min(timings),
        "avg_ms": statistics.mean(timings),
        "max_ms": max(timings),
        "message": message,
        "summary": summary,
        "policy_source": policy_source,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=5, help="number of runs per scenario")
    parser.add_argument("--warm-cache", action="store_true", help="measure repeated hot-cache calls instead of cold calls")
    parser.add_argument("--score-value-mode", default=None, help="solver score value mode, for example value_optimal")
    parser.add_argument("--value-table", default=None, help="path to an endgame/full-game value table")
    parser.add_argument("--output", default=None, help="optional JSON report path")
    args = parser.parse_args()

    mode_label = "warm-cache" if args.warm_cache else "cold-cache"
    print(
        f"Benchmarking {len(SCENARIOS)} AI scenarios, repeats={args.repeats}, mode={mode_label}, "
        f"score_value_mode={args.score_value_mode or 'heuristic'}"
    )
    results = []
    for case in SCENARIOS:
        result = run_case(case, args.repeats, args.warm_cache, args.score_value_mode, args.value_table)
        results.append(result)
        print(
            f"- {case['name']}: mode={case['mode']} rolls={case['rolls_left']} "
            f"min={result['min_ms']:.2f}ms avg={result['avg_ms']:.2f}ms max={result['max_ms']:.2f}ms"
        )
        print(f"  recommendation: {result['message']}")

    if args.output:
        payload = {
            "repeats": args.repeats,
            "warm_cache": args.warm_cache,
            "score_value_mode": args.score_value_mode or "heuristic",
            "value_table": args.value_table,
            "scenarios": results,
        }
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
