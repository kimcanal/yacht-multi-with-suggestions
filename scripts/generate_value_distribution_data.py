#!/usr/bin/env python3
"""Generate quantile/variance value targets for scorecard states."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from yacht_ai.self_play import simulate_state_distribution
from yacht_ai.value_model import normalize_scorecard

PRESET_SCORECARDS = {
    "empty": [None] * 12,
    "yacht_bonus_active": [None, None, None, None, 15, None, 18, None, None, None, None, 50],
    "upper_bonus_live": [3, 6, 9, None, 15, None, 22, None, None, 15, None, None],
    "upper_bonus_locked_out": [1, 2, 3, 4, 5, 6, 22, None, None, 15, 30, None],
}


def parse_args():
    parser = argparse.ArgumentParser(description="Generate scorecard distribution target JSONL.")
    parser.add_argument("--source-jsonl", default="", help="optional value-data JSONL to sample states from")
    parser.add_argument("--presets", default="empty,yacht_bonus_active", help="comma-separated preset names")
    parser.add_argument("--max-states", type=int, default=16)
    parser.add_argument("--min-turns", type=int, default=0)
    parser.add_argument("--max-turns", type=int, default=12)
    parser.add_argument("--trials-per-state", type=int, default=32)
    parser.add_argument("--seed", type=int, default=20260708)
    parser.add_argument("--mode", choices=("focused", "cover"), default="focused")
    parser.add_argument("--output", default="artifacts/generated/data/self-play-value-distribution-focused.jsonl")
    parser.add_argument("--summary-output", default="")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--report-every", type=int, default=4)
    return parser.parse_args()


def scorecard_key(scorecard, mode):
    return (mode, tuple("__open__" if value is None else int(value) for value in normalize_scorecard(scorecard)))


def iter_preset_states(preset_arg, mode):
    for raw_name in preset_arg.split(","):
        name = raw_name.strip()
        if not name:
            continue
        if name not in PRESET_SCORECARDS:
            choices = ", ".join(sorted(PRESET_SCORECARDS))
            raise SystemExit(f"unknown preset {name!r}; choices: {choices}")
        yield {
            "source": f"preset:{name}",
            "mode": mode,
            "scorecard": list(PRESET_SCORECARDS[name]),
        }


def iter_jsonl_states(path, min_turns, max_turns, default_mode):
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            scorecard = normalize_scorecard(row.get("scorecard"))
            turns_completed = sum(1 for value in scorecard if value is not None)
            if turns_completed < min_turns or turns_completed > max_turns:
                continue
            yield {
                "source": f"{Path(path).name}:{line_number}",
                "mode": row.get("strategy_mode") or default_mode,
                "scorecard": scorecard,
            }


def collect_states(args):
    seen = set()
    states = []

    def add_state(candidate):
        if len(states) >= max(0, args.max_states):
            return
        key = scorecard_key(candidate["scorecard"], candidate["mode"])
        if key in seen:
            return
        seen.add(key)
        states.append(candidate)

    for candidate in iter_preset_states(args.presets, args.mode):
        add_state(candidate)
    if args.source_jsonl:
        for candidate in iter_jsonl_states(args.source_jsonl, args.min_turns, args.max_turns, args.mode):
            add_state(candidate)
            if len(states) >= max(0, args.max_states):
                break
    return states


def flatten_distribution(state_id, source, report):
    state = report["initial_state"]
    final_score = report["final_score"]
    remaining = report["remaining_score"]
    return {
        "state_id": state_id,
        "source": source,
        "strategy_mode": report["strategy_mode"],
        "seed": report["seed"],
        "trials": report["trials"],
        "scorecard": state["scorecard"],
        "turns_completed": state["turns_completed"],
        "open_categories": state["open_categories"],
        "open_category_names": state["open_category_names"],
        "open_mask": state["open_mask"],
        "closed_mask": state["closed_mask"],
        "upper_score": state["upper_score"],
        "upper_gap": state["upper_gap"],
        "lower_score": state["lower_score"],
        "current_total": state["current_total"],
        "yacht_bonus_active": state["yacht_bonus_active"],
        "feature_names": state["feature_names"],
        "feature_values": state["feature_values"],
        "target_upper_bonus_rate": report["upper_bonus_rate"],
        "target_final_mean": final_score["mean"],
        "target_final_stdev": final_score["stdev"],
        "target_final_min": final_score["min"],
        "target_final_p10": final_score["p10"],
        "target_final_p25": final_score["p25"],
        "target_final_p50": final_score["p50"],
        "target_final_p75": final_score["p75"],
        "target_final_p90": final_score["p90"],
        "target_final_max": final_score["max"],
        "target_remaining_mean": remaining["mean"],
        "target_remaining_stdev": remaining["stdev"],
        "target_remaining_min": remaining["min"],
        "target_remaining_p10": remaining["p10"],
        "target_remaining_p25": remaining["p25"],
        "target_remaining_p50": remaining["p50"],
        "target_remaining_p75": remaining["p75"],
        "target_remaining_p90": remaining["p90"],
        "target_remaining_max": remaining["max"],
        "worst_outcomes": report["worst_outcomes"],
        "best_outcomes": report["best_outcomes"],
    }


def build_summary(rows, args):
    if not rows:
        return {
            "states": 0,
            "trials_per_state": args.trials_per_state,
            "seed": args.seed,
            "mode": args.mode,
            "output": args.output,
        }
    return {
        "states": len(rows),
        "trials_per_state": args.trials_per_state,
        "seed": args.seed,
        "mode": args.mode,
        "output": args.output,
        "avg_remaining_mean": round(statistics.fmean(row["target_remaining_mean"] for row in rows), 6),
        "avg_remaining_stdev": round(statistics.fmean(row["target_remaining_stdev"] for row in rows), 6),
        "max_remaining_stdev": max(row["target_remaining_stdev"] for row in rows),
        "max_upside_gap": max(row["target_remaining_p90"] - row["target_remaining_p10"] for row in rows),
        "highest_variance_states": [
            {
                "state_id": row["state_id"],
                "source": row["source"],
                "turns_completed": row["turns_completed"],
                "remaining_mean": row["target_remaining_mean"],
                "remaining_stdev": row["target_remaining_stdev"],
                "remaining_p10": row["target_remaining_p10"],
                "remaining_p90": row["target_remaining_p90"],
            }
            for row in sorted(rows, key=lambda item: item["target_remaining_stdev"], reverse=True)[:5]
        ],
    }


def main():
    args = parse_args()
    output_path = Path(args.output)
    if output_path.exists() and not args.overwrite:
        raise SystemExit(f"{output_path} already exists. Use --overwrite to replace it.")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    states = collect_states(args)
    rows = []
    with output_path.open("w", encoding="utf-8") as handle:
        for state_id, state in enumerate(states):
            report = simulate_state_distribution(
                state["scorecard"],
                trials=args.trials_per_state,
                seed=args.seed + state_id * 100003,
                mode=state["mode"],
            )
            row = flatten_distribution(state_id, state["source"], report)
            rows.append(row)
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            if args.report_every and ((state_id + 1) % args.report_every == 0 or state_id + 1 == len(states)):
                print(f"[value-dist-data] states={state_id + 1}/{len(states)}")

    summary = build_summary(rows, args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.summary_output:
        summary_path = Path(args.summary_output)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
