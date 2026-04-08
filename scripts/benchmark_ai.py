#!/usr/bin/env python3
"""Benchmark representative AI recommendation scenarios."""

from __future__ import annotations

import argparse
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
]
def run_case(case: dict, repeats: int, warm_cache: bool) -> tuple[float, float, float, str]:
    timings = []
    message = ""
    open_categories = [i for i, value in enumerate(case["scorecard"]) if value is None]
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
        )
        timings.append((time.perf_counter() - started) * 1000)
        message = result.get("message", "")
    return min(timings), statistics.mean(timings), max(timings), message


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=5, help="number of runs per scenario")
    parser.add_argument("--warm-cache", action="store_true", help="measure repeated hot-cache calls instead of cold calls")
    args = parser.parse_args()

    mode_label = "warm-cache" if args.warm_cache else "cold-cache"
    print(f"Benchmarking {len(SCENARIOS)} AI scenarios, repeats={args.repeats}, mode={mode_label}")
    for case in SCENARIOS:
        best, avg, worst, message = run_case(case, args.repeats, args.warm_cache)
        print(
            f"- {case['name']}: mode={case['mode']} rolls={case['rolls_left']} "
            f"min={best:.2f}ms avg={avg:.2f}ms max={worst:.2f}ms"
        )
        print(f"  recommendation: {message}")


if __name__ == "__main__":
    main()
