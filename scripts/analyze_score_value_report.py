#!/usr/bin/env python3
"""Summarize paired score-stage value simulation reports."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from yacht_ai.constants import CATEGORY_NAMES
from yacht_ai.scoring import calc_score


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze score-stage value A/B paired cases.")
    parser.add_argument("report", help="JSON report from simulate_score_value_games.py")
    parser.add_argument("--output", default="", help="optional JSON analysis output")
    parser.add_argument("--markdown-output", default="", help="optional Markdown analysis output")
    return parser.parse_args()


def category_name(category_idx: int | None, fallback: str | None = None) -> str:
    if isinstance(category_idx, int) and 0 <= category_idx < len(CATEGORY_NAMES):
        return CATEGORY_NAMES[category_idx]
    return fallback or "Unknown"


def decision_score(decision: dict[str, Any]) -> int | None:
    category_idx = decision.get("category_idx")
    dice = decision.get("dice")
    if not isinstance(category_idx, int) or not isinstance(dice, list):
        return None
    return int(calc_score(dice, category_idx))


def normalize_decision(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "turn": decision.get("turn"),
        "dice": decision.get("dice"),
        "category": category_name(decision.get("category_idx"), decision.get("category")),
        "category_idx": decision.get("category_idx"),
        "score": decision_score(decision),
        "expected_value": decision.get("expected_value"),
    }


def first_divergence(heuristic_game: dict[str, Any], policy_game: dict[str, Any]) -> dict[str, Any] | None:
    heuristic_decisions = heuristic_game.get("score_decisions", [])
    policy_decisions = policy_game.get("score_decisions", [])
    for heuristic_decision, policy_decision in zip(heuristic_decisions, policy_decisions):
        if heuristic_decision.get("category_idx") != policy_decision.get("category_idx"):
            return {
                "turn": heuristic_decision.get("turn"),
                "heuristic": normalize_decision(heuristic_decision),
                "policy": normalize_decision(policy_decision),
            }
    return None


def case_summary(case: dict[str, Any], policy_label: str) -> dict[str, Any]:
    heuristic_game = case["heuristic"]
    policy_game = case[policy_label]
    divergence = first_divergence(heuristic_game, policy_game)
    return {
        "seed": case["seed"],
        "game_index": case["game_index"],
        "delta_vs_heuristic": case["delta_vs_heuristic"],
        "heuristic_total": heuristic_game["total_score"],
        "policy_total": policy_game["total_score"],
        "upper_bonus_delta": policy_game["upper_bonus"] - heuristic_game["upper_bonus"],
        "upper_score_delta": policy_game["upper_score"] - heuristic_game["upper_score"],
        "yacht_bonus_delta": policy_game["yacht_bonus_count"] - heuristic_game["yacht_bonus_count"],
        "zero_categories_delta": policy_game["zero_categories"] - heuristic_game["zero_categories"],
        "heuristic_scorecard": heuristic_game["scorecard"],
        "policy_scorecard": policy_game["scorecard"],
        "first_divergence": divergence,
    }


def case_group_summary(cases: list[dict[str, Any]], policy_label: str) -> dict[str, Any]:
    summaries = [case_summary(case, policy_label) for case in cases]
    first_turns = Counter()
    first_pairs = Counter()
    for summary in summaries:
        divergence = summary.get("first_divergence")
        if not divergence:
            first_turns["no category divergence"] += 1
            first_pairs["no category divergence"] += 1
            continue
        first_turns[str(divergence["turn"])] += 1
        pair = f"{divergence['heuristic']['category']} -> {divergence['policy']['category']}"
        first_pairs[pair] += 1

    deltas = [summary["delta_vs_heuristic"] for summary in summaries]
    return {
        "cases": summaries,
        "case_count": len(summaries),
        "avg_delta": round(statistics.fmean(deltas), 4) if deltas else 0.0,
        "min_delta": min(deltas) if deltas else 0,
        "max_delta": max(deltas) if deltas else 0,
        "first_divergence_turns": dict(first_turns.most_common()),
        "first_divergence_pairs": dict(first_pairs.most_common()),
        "upper_bonus_delta_sum": sum(summary["upper_bonus_delta"] for summary in summaries),
        "yacht_bonus_delta_sum": sum(summary["yacht_bonus_delta"] for summary in summaries),
        "zero_categories_delta_avg": round(
            statistics.fmean(summary["zero_categories_delta"] for summary in summaries),
            4,
        ) if summaries else 0.0,
    }


def paired_delta_stats(policy_row: dict[str, Any]) -> dict[str, Any]:
    deltas = policy_row.get("paired_delta_vs_heuristic") or []
    if not deltas:
        return {
            "count": 0,
            "mean": 0.0,
            "sample_stdev": 0.0,
            "stderr": 0.0,
            "normal_ci95_low": 0.0,
            "normal_ci95_high": 0.0,
        }
    count = len(deltas)
    mean = statistics.fmean(deltas)
    sample_stdev = statistics.stdev(deltas) if count > 1 else 0.0
    stderr = sample_stdev / (count ** 0.5) if count > 1 else 0.0
    ci_radius = 1.96 * stderr
    return {
        "count": count,
        "mean": round(mean, 4),
        "sample_stdev": round(sample_stdev, 4),
        "stderr": round(stderr, 4),
        "normal_ci95_low": round(mean - ci_radius, 4),
        "normal_ci95_high": round(mean + ci_radius, 4),
    }


def analyze_report(report: dict[str, Any], source_report: str) -> dict[str, Any]:
    policy_rows = {row["label"]: row for row in report.get("policies", [])}
    analyses: dict[str, Any] = {}
    for policy_label, paired in report.get("paired_cases", {}).items():
        policy_row = policy_rows.get(policy_label, {})
        analyses[policy_label] = {
            "baseline_summary": policy_rows.get("heuristic", {}),
            "summary": policy_row,
            "paired_delta_stats": paired_delta_stats(policy_row),
            "worst": case_group_summary(paired.get("worst", []), policy_label),
            "best": case_group_summary(paired.get("best", []), policy_label),
        }

    return {
        "source_report": source_report,
        "mode": report.get("mode"),
        "games": report.get("games"),
        "seed": report.get("seed"),
        "value_table": report.get("value_table"),
        "analyses": analyses,
    }


def render_pair_counts(title: str, counts: dict[str, int]) -> list[str]:
    if not counts:
        return [f"- {title}: none"]
    return [f"- {title}: " + ", ".join(f"{key} ({value})" for key, value in counts.items())]


def render_case_line(case: dict[str, Any], policy_label: str) -> str:
    divergence = case.get("first_divergence")
    if divergence:
        first = (
            f"first split turn {divergence['turn']} "
            f"{divergence['heuristic']['category']}({divergence['heuristic']['score']}) -> "
            f"{divergence['policy']['category']}({divergence['policy']['score']})"
        )
    else:
        first = "no category split in saved turns"
    return (
        f"- seed {case['seed']}: delta {case['delta_vs_heuristic']:+}, "
        f"heuristic {case['heuristic_total']} vs {policy_label} {case['policy_total']}; {first}; "
        f"upper bonus delta {case['upper_bonus_delta']:+}, yacht bonus delta {case['yacht_bonus_delta']:+}"
    )


def render_markdown(analysis: dict[str, Any]) -> str:
    lines = [
        "# Score Value Paired-case Analysis",
        "",
        f"- Source report: `{analysis['source_report']}`",
        f"- Mode: `{analysis['mode']}`",
        f"- Games: `{analysis['games']}` paired seeds",
        f"- Seed: `{analysis['seed']}`",
        f"- Value table: `{analysis['value_table']}`",
        "",
    ]

    for policy_label, policy_analysis in analysis["analyses"].items():
        baseline = policy_analysis["baseline_summary"]
        summary = policy_analysis["summary"]
        delta_stats = policy_analysis["paired_delta_stats"]
        lines.extend([
            f"## {policy_label}",
            "",
            (
                f"- Full-run average: heuristic {baseline.get('avg_total', 0.0)} vs "
                f"{policy_label} {summary.get('avg_total', 0.0)} "
                f"({summary.get('avg_delta_vs_heuristic', 0.0):+.4f}); "
                f"win/loss/tie: {summary.get('win_rate_vs_heuristic', 0.0)} / "
                f"{summary.get('loss_rate_vs_heuristic', 0.0)} / "
                f"{round(1.0 - summary.get('win_rate_vs_heuristic', 0.0) - summary.get('loss_rate_vs_heuristic', 0.0), 6)}"
            ),
            (
                f"- Paired delta uncertainty: n={delta_stats['count']}, "
                f"sample stdev {delta_stats['sample_stdev']}, stderr {delta_stats['stderr']}, "
                f"normal 95% CI [{delta_stats['normal_ci95_low']}, {delta_stats['normal_ci95_high']}]"
            ),
            (
                f"- Upper bonus rate: heuristic {baseline.get('upper_bonus_rate', 0.0)} vs "
                f"{policy_label} {summary.get('upper_bonus_rate', 0.0)}; "
                f"avg exact table hits per game {summary.get('avg_value_score_hits', 0.0)}"
            ),
            "",
        ])
        for group_name in ("worst", "best"):
            group = policy_analysis[group_name]
            lines.extend([
                f"### Saved {group_name.title()} Cases",
                "",
                (
                    f"- Cases: {group['case_count']}; avg delta {group['avg_delta']:+.4f}; "
                    f"range {group['min_delta']} to {group['max_delta']}"
                ),
                (
                    f"- Upper bonus delta sum {group['upper_bonus_delta_sum']:+}; "
                    f"Yacht bonus delta sum {group['yacht_bonus_delta_sum']:+}; "
                    f"avg zero-category delta {group['zero_categories_delta_avg']:+.4f}"
                ),
            ])
            lines.extend(render_pair_counts("First split turns", group["first_divergence_turns"]))
            lines.extend(render_pair_counts("First split pairs", group["first_divergence_pairs"]))
            lines.append("")
            for saved_case in group["cases"]:
                lines.append(render_case_line(saved_case, policy_label))
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    report_path = Path(args.report)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    analysis = analyze_report(report, args.report)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[score-value-analysis] wrote JSON analysis to {output_path}")

    markdown = render_markdown(analysis)
    if args.markdown_output:
        markdown_path = Path(args.markdown_output)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        print(f"[score-value-analysis] wrote Markdown analysis to {markdown_path}")
    elif not args.output:
        print(markdown)


if __name__ == "__main__":
    main()
