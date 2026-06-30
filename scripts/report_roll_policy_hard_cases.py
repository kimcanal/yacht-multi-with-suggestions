#!/usr/bin/env python3
"""Render worst roll-policy EV-gap cases as a compact Markdown report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render roll-policy hard cases from an EV-gap report.")
    parser.add_argument("--input", required=True, help="EV-gap JSON report")
    parser.add_argument("--output", required=True, help="Markdown output path")
    parser.add_argument("--limit", type=int, default=10, help="number of cases to render")
    return parser.parse_args()


def fmt_list(values) -> str:
    if values is None:
        return "-"
    if isinstance(values, list):
        return ", ".join(str(value) for value in values) or "-"
    return str(values)


def main() -> None:
    args = parse_args()
    with Path(args.input).open("r", encoding="utf-8") as handle:
        report = json.load(handle)

    cases = report.get("worst_cases", [])[: max(0, args.limit)]
    lines = [
        f"# Hard cases for {Path(report.get('model_path', args.input)).name}",
        "",
        "이 문서는 teacher top-1 accuracy가 아니라, 모델이 teacher와 다른 keep을 골랐을 때의 추가 EV 손실이 큰 케이스를 모은 것이다.",
        "서버 runtime에서는 confidence gate와 exact gap guard를 통과하지 못하면 exact solver로 fallback한다.",
        "",
        "## Summary",
        "",
        f"- Evaluated examples: {report.get('evaluated_examples')}",
        f"- Top-1 accuracy: {report.get('top1_accuracy')}",
        f"- Mean excess EV gap: {report.get('overall_excess_ev_gap', {}).get('mean_ev_gap')}",
        f"- p99 excess EV gap: {report.get('overall_excess_ev_gap', {}).get('p99_ev_gap')}",
        f"- Max excess EV gap: {report.get('overall_excess_ev_gap', {}).get('max_ev_gap')}",
        "",
        "## Worst Cases",
        "",
    ]

    for index, case in enumerate(cases, start=1):
        lines.extend(
            [
                f"### {index}. sample {case.get('sample_id')} - excess EV gap {case.get('excess_ev_gap')}",
                "",
                f"- Dice: `{fmt_list(case.get('dice'))}`",
                f"- Rolls left: `{case.get('rolls_left')}`",
                f"- Mode: `{case.get('strategy_mode')}`",
                f"- Open categories: {fmt_list(case.get('open_category_names'))}",
                f"- Teacher keep: `{fmt_list(case.get('teacher_keep_values'))}` -> {case.get('teacher_target')}",
                f"- Model keep: `{fmt_list(case.get('model_keep_values'))}` -> {case.get('model_target')}",
                f"- Model confidence: `{case.get('model_confidence')}`",
                f"- Teacher objective gap: `{case.get('teacher_objective_gap')}`",
                f"- Model objective gap: `{case.get('model_objective_gap')}`",
                "",
            ]
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"[hard-cases] wrote {len(cases)} cases to {output_path}")


if __name__ == "__main__":
    main()
