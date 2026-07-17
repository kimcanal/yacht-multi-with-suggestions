#!/usr/bin/env python3
"""Estimate final-score distribution from a specific scorecard state."""

from __future__ import annotations

import argparse
import json
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
}


def parse_args():
    parser = argparse.ArgumentParser(description="Simulate score distribution from one scorecard state.")
    parser.add_argument("--scorecard", default="", help="JSON list of 12 scores/nulls, or a preset name")
    parser.add_argument("--jsonl", default="", help="load scorecard from a JSONL value-data row")
    parser.add_argument("--line", type=int, default=0, help="1-based line number for --jsonl")
    parser.add_argument("--trials", type=int, default=64)
    parser.add_argument("--seed", type=int, default=20260708)
    parser.add_argument("--mode", choices=("focused", "cover"), default="focused")
    parser.add_argument("--output", default="")
    parser.add_argument("--markdown-output", default="")
    return parser.parse_args()


def parse_scorecard_arg(raw):
    if raw in PRESET_SCORECARDS:
        return list(PRESET_SCORECARDS[raw])
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        presets = ", ".join(sorted(PRESET_SCORECARDS))
        raise SystemExit(f"--scorecard must be JSON or one of: {presets}") from exc
    if not isinstance(parsed, list) or len(parsed) != 12:
        raise SystemExit("scorecard must have 12 entries")
    return normalize_scorecard(parsed)


def load_scorecard_from_jsonl(path, line_number):
    if line_number <= 0:
        raise SystemExit("--line must be provided with --jsonl")
    with Path(path).open("r", encoding="utf-8") as handle:
        for current, line in enumerate(handle, start=1):
            if current != line_number:
                continue
            row = json.loads(line)
            return normalize_scorecard(row.get("scorecard"))
    raise SystemExit(f"line {line_number} not found in {path}")


def resolve_scorecard(args):
    if args.scorecard:
        return parse_scorecard_arg(args.scorecard)
    if args.jsonl:
        return load_scorecard_from_jsonl(args.jsonl, args.line)
    return list(PRESET_SCORECARDS["empty"])


def render_markdown(report):
    initial = report["initial_state"]
    final_score = report["final_score"]
    remaining = report["remaining_score"]
    lines = [
        "# Scorecard value distribution",
        "",
        "특정 점수판 상태에서 exact self-play를 여러 번 이어서 최종 점수 분포를 추정한 결과다.",
        "",
        "## Summary",
        "",
        f"- Mode: {report['strategy_mode']}",
        f"- Trials: {report['trials']}",
        f"- Current total: {initial['current_total']}",
        f"- Upper score: {initial['upper_score']} / gap {initial['upper_gap']}",
        f"- Yacht bonus active: {initial['yacht_bonus_active']}",
        f"- Open categories: {', '.join(initial['open_category_names']) or '-'}",
        f"- Upper bonus rate: {report['upper_bonus_rate']}",
        "",
        "## Final Score",
        "",
        f"- mean {final_score['mean']}, stdev {final_score['stdev']}",
        f"- p10/p50/p90 {final_score['p10']} / {final_score['p50']} / {final_score['p90']}",
        f"- min/max {final_score['min']} / {final_score['max']}",
        "",
        "## Remaining Score",
        "",
        f"- mean {remaining['mean']}, stdev {remaining['stdev']}",
        f"- p10/p50/p90 {remaining['p10']} / {remaining['p50']} / {remaining['p90']}",
        f"- min/max {remaining['min']} / {remaining['max']}",
        "",
        "## Worst Outcomes",
        "",
    ]
    for row in report["worst_outcomes"]:
        lines.append(f"- seed {row['seed']}: final {row['final_score']}, remaining {row['remaining_score']}")
    lines.extend(["", "## Best Outcomes", ""])
    for row in report["best_outcomes"]:
        lines.append(f"- seed {row['seed']}: final {row['final_score']}, remaining {row['remaining_score']}")
    return "\n".join(lines).rstrip() + "\n"


def main():
    args = parse_args()
    scorecard = resolve_scorecard(args)
    report = simulate_state_distribution(scorecard, args.trials, args.seed, args.mode)
    print(json.dumps({
        "trials": report["trials"],
        "final_score": report["final_score"],
        "remaining_score": report["remaining_score"],
        "upper_bonus_rate": report["upper_bonus_rate"],
    }, ensure_ascii=False, indent=2))

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[value-distribution] wrote JSON report to {output_path}")

    if args.markdown_output:
        markdown_path = Path(args.markdown_output)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(report), encoding="utf-8")
        print(f"[value-distribution] wrote Markdown report to {markdown_path}")


if __name__ == "__main__":
    main()
