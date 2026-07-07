#!/usr/bin/env python3
"""Evaluate a scorecard value baseline and render high-error states."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate a scorecard value baseline on self-play JSONL.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--target", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--markdown-output", default="")
    parser.add_argument("--limit", type=int, default=10)
    return parser.parse_args()


def load_model(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload


def predict_row(model, feature_values):
    weights = np.asarray(model["weights"], dtype=np.float64)
    features = np.asarray(feature_values, dtype=np.float64)
    if features.shape[0] != weights.shape[0]:
        raise ValueError(f"feature length mismatch: got {features.shape[0]}, expected {weights.shape[0]}")
    return float(model["bias"] + np.dot(features, weights))


def load_predictions(data_path, model, target_name):
    rows = []
    with Path(data_path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if target_name not in row:
                continue
            predicted = predict_row(model, row["feature_values"])
            target = float(row[target_name])
            error = predicted - target
            rows.append(
                {
                    "line_number": line_number,
                    "game_id": row.get("game_id"),
                    "turn_index": row.get("turn_index"),
                    "turns_completed": row.get("turns_completed"),
                    "strategy_mode": row.get("strategy_mode"),
                    "current_total": row.get("current_total"),
                    "upper_score": row.get("upper_score"),
                    "upper_gap": row.get("upper_gap"),
                    "yacht_bonus_active": row.get("yacht_bonus_active"),
                    "open_category_names": row.get("open_category_names", []),
                    "scored_category_name": row.get("scored_category_name"),
                    "scored_points": row.get("scored_points"),
                    "target": target,
                    "predicted": predicted,
                    "error": error,
                    "abs_error": abs(error),
                    "scorecard": row.get("scorecard"),
                }
            )
    if not rows:
        raise SystemExit(f"No usable value rows found in {data_path}")
    return rows


def regression_metrics(rows):
    targets = np.asarray([row["target"] for row in rows], dtype=np.float64)
    predictions = np.asarray([row["predicted"] for row in rows], dtype=np.float64)
    residual = predictions - targets
    denom = float(np.sum((targets - np.mean(targets)) ** 2))
    r2 = 0.0 if denom <= 0 else 1.0 - float(np.sum(residual ** 2)) / denom
    return {
        "examples": len(rows),
        "mae": round(float(np.mean(np.abs(residual))), 6),
        "rmse": round(float(math.sqrt(np.mean(residual ** 2))), 6),
        "mean_error": round(float(np.mean(residual)), 6),
        "r2": round(r2, 6),
    }


def group_by_turn(rows):
    grouped = {}
    for row in rows:
        key = int(row.get("turns_completed") or 0)
        grouped.setdefault(key, []).append(row)
    return [
        {
            "turns_completed": key,
            "examples": len(group_rows),
            "mae": round(statistics.fmean(row["abs_error"] for row in group_rows), 6),
            "mean_target": round(statistics.fmean(row["target"] for row in group_rows), 6),
        }
        for key, group_rows in sorted(grouped.items())
    ]


def compact_case(row):
    return {
        "line_number": row["line_number"],
        "game_id": row["game_id"],
        "turn_index": row["turn_index"],
        "turns_completed": row["turns_completed"],
        "current_total": row["current_total"],
        "upper_score": row["upper_score"],
        "upper_gap": row["upper_gap"],
        "yacht_bonus_active": row["yacht_bonus_active"],
        "open_category_names": row["open_category_names"],
        "scored_category_name": row["scored_category_name"],
        "scored_points": row["scored_points"],
        "target": round(row["target"], 4),
        "predicted": round(row["predicted"], 4),
        "error": round(row["error"], 4),
        "abs_error": round(row["abs_error"], 4),
        "scorecard": row["scorecard"],
    }


def build_report(data_path, model_path, rows, model, limit):
    worst_over = sorted(rows, key=lambda row: row["error"], reverse=True)[:limit]
    worst_under = sorted(rows, key=lambda row: row["error"])[:limit]
    worst_abs = sorted(rows, key=lambda row: row["abs_error"], reverse=True)[:limit]
    return {
        "model_path": str(model_path),
        "data_path": str(data_path),
        "model_id": model.get("model_id"),
        "model_type": model.get("model_type"),
        "target": model.get("target"),
        "metrics": regression_metrics(rows),
        "by_turn": group_by_turn(rows),
        "worst_abs": [compact_case(row) for row in worst_abs],
        "worst_over_prediction": [compact_case(row) for row in worst_over],
        "worst_under_prediction": [compact_case(row) for row in worst_under],
    }


def fmt_categories(names):
    return ", ".join(names) if names else "-"


def render_markdown(report, limit):
    metrics = report["metrics"]
    lines = [
        f"# Value baseline hard cases for {report.get('model_id')}",
        "",
        "이 문서는 scorecard state -> remaining score baseline이 크게 빗나간 상태를 모은 것이다.",
        "목적은 모델 운영 투입이 아니라, score-stage 휴리스틱이 실제 self-play 결과와 어긋나는 구간을 찾는 것이다.",
        "",
        "## Summary",
        "",
        f"- Examples: {metrics['examples']}",
        f"- MAE: {metrics['mae']}",
        f"- RMSE: {metrics['rmse']}",
        f"- Mean error: {metrics['mean_error']}",
        f"- R2: {metrics['r2']}",
        "",
        "## Error By Turn",
        "",
    ]
    for row in report["by_turn"]:
        lines.append(
            f"- turns_completed={row['turns_completed']}: n={row['examples']}, "
            f"MAE={row['mae']}, mean_target={row['mean_target']}"
        )

    def add_cases(title, cases):
        lines.extend(["", f"## {title}", ""])
        for index, case in enumerate(cases[:limit], start=1):
            lines.extend(
                [
                    f"### {index}. line {case['line_number']} - abs error {case['abs_error']}",
                    "",
                    f"- Turn: `{case['turns_completed']}` completed, current total `{case['current_total']}`",
                    f"- Target remaining: `{case['target']}`, predicted `{case['predicted']}`, error `{case['error']}`",
                    f"- Upper: `{case['upper_score']}` / gap `{case['upper_gap']}`, yacht bonus active `{case['yacht_bonus_active']}`",
                    f"- Open categories: {fmt_categories(case['open_category_names'])}",
                    f"- Next scored: {case['scored_category_name']} {case['scored_points']}점",
                    f"- Scorecard: `{case['scorecard']}`",
                    "",
                ]
            )

    add_cases("Worst Absolute Errors", report["worst_abs"])
    add_cases("Over-predictions", report["worst_over_prediction"])
    add_cases("Under-predictions", report["worst_under_prediction"])
    return "\n".join(lines).rstrip() + "\n"


def main():
    args = parse_args()
    model = load_model(args.model)
    target_name = args.target or model.get("target") or "target_remaining_score"
    rows = load_predictions(args.data, model, target_name)
    report = build_report(args.data, args.model, rows, model, max(0, args.limit))
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[value-eval] wrote JSON report to {output_path}")

    if args.markdown_output:
        markdown_path = Path(args.markdown_output)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(report, max(0, args.limit)), encoding="utf-8")
        print(f"[value-eval] wrote Markdown report to {markdown_path}")


if __name__ == "__main__":
    main()
