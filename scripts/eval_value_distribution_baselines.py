#!/usr/bin/env python3
"""Evaluate multi-target scorecard value distribution baselines."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate scorecard value distribution baseline predictions.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", default="")
    parser.add_argument("--markdown-output", default="")
    parser.add_argument("--limit", type=int, default=10)
    return parser.parse_args()


def load_model(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def predict(model, feature_values):
    weights = np.asarray(model["weights"], dtype=np.float64)
    bias = np.asarray(model["bias"], dtype=np.float64)
    features = np.asarray(feature_values, dtype=np.float64)
    if weights.shape[0] != features.shape[0]:
        raise ValueError(f"feature length mismatch: got {features.shape[0]}, expected {weights.shape[0]}")
    return bias + features @ weights


def load_predictions(path, model):
    targets = model["targets"]
    rows = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if any(target not in row for target in targets):
                continue
            predicted = predict(model, row["feature_values"])
            actual = np.asarray([float(row[target]) for target in targets], dtype=np.float64)
            rows.append({
                "line_number": line_number,
                "source": row.get("source"),
                "turns_completed": row.get("turns_completed"),
                "current_total": row.get("current_total"),
                "upper_score": row.get("upper_score"),
                "upper_gap": row.get("upper_gap"),
                "yacht_bonus_active": row.get("yacht_bonus_active"),
                "open_category_names": row.get("open_category_names", []),
                "scorecard": row.get("scorecard"),
                "actual": actual,
                "predicted": predicted,
                "abs_error": np.abs(predicted - actual),
            })
    if not rows:
        raise SystemExit(f"No usable distribution rows found in {path}")
    return rows


def metric(actual, predicted):
    residual = predicted - actual
    denom = float(np.sum((actual - np.mean(actual)) ** 2))
    r2 = 0.0 if denom <= 0 else 1.0 - float(np.sum(residual ** 2)) / denom
    return {
        "mae": round(float(np.mean(np.abs(residual))), 6),
        "rmse": round(float(math.sqrt(np.mean(residual ** 2))), 6),
        "mean_error": round(float(np.mean(residual)), 6),
        "r2": round(r2, 6),
    }


def metrics_by_target(targets, rows):
    actual_matrix = np.vstack([row["actual"] for row in rows])
    predicted_matrix = np.vstack([row["predicted"] for row in rows])
    return {
        target: metric(actual_matrix[:, idx], predicted_matrix[:, idx])
        for idx, target in enumerate(targets)
    }


def quantile_order_report(targets, rows):
    required = ["target_remaining_p10", "target_remaining_p50", "target_remaining_p90"]
    if any(target not in targets for target in required):
        return None
    predictions = np.vstack([row["predicted"] for row in rows])
    p10_idx = targets.index("target_remaining_p10")
    p50_idx = targets.index("target_remaining_p50")
    p90_idx = targets.index("target_remaining_p90")
    violations = (
        (predictions[:, p10_idx] > predictions[:, p50_idx])
        | (predictions[:, p50_idx] > predictions[:, p90_idx])
    )
    return {
        "examples": len(rows),
        "violations": int(np.sum(violations)),
        "violation_rate": round(float(np.mean(violations)), 6),
    }


def compact_case(row, targets, target_idx):
    actual = float(row["actual"][target_idx])
    predicted = float(row["predicted"][target_idx])
    return {
        "line_number": row["line_number"],
        "source": row["source"],
        "target": targets[target_idx],
        "turns_completed": row["turns_completed"],
        "current_total": row["current_total"],
        "upper_score": row["upper_score"],
        "upper_gap": row["upper_gap"],
        "yacht_bonus_active": row["yacht_bonus_active"],
        "open_category_names": row["open_category_names"],
        "actual": round(actual, 4),
        "predicted": round(predicted, 4),
        "error": round(predicted - actual, 4),
        "abs_error": round(abs(predicted - actual), 4),
        "scorecard": row["scorecard"],
    }


def worst_cases(targets, rows, limit):
    cases = {}
    for idx, target in enumerate(targets):
        ordered = sorted(rows, key=lambda row, target_idx=idx: row["abs_error"][target_idx], reverse=True)
        cases[target] = [compact_case(row, targets, idx) for row in ordered[:limit]]
    return cases


def build_report(data_path, model_path, model, rows, limit):
    targets = model["targets"]
    return {
        "model_path": str(model_path),
        "data_path": str(data_path),
        "model_id": model.get("model_id"),
        "model_type": model.get("model_type"),
        "targets": targets,
        "examples": len(rows),
        "metrics": metrics_by_target(targets, rows),
        "quantile_order": quantile_order_report(targets, rows),
        "worst_cases": worst_cases(targets, rows, max(0, limit)),
    }


def fmt_names(names):
    return ", ".join(names) if names else "-"


def render_markdown(report, limit):
    lines = [
        f"# Value distribution baseline report for {report['model_id']}",
        "",
        "이 문서는 scorecard state -> remaining score 분포 target baseline을 평가한다.",
        "",
        "## Summary",
        "",
        f"- Examples: {report['examples']}",
        f"- Targets: {', '.join(report['targets'])}",
    ]
    if report["quantile_order"]:
        lines.append(f"- Quantile order violations: {report['quantile_order']['violations']} ({report['quantile_order']['violation_rate']})")
    lines.extend(["", "## Metrics", ""])
    for target, metric_row in report["metrics"].items():
        lines.append(
            f"- {target}: MAE {metric_row['mae']}, RMSE {metric_row['rmse']}, "
            f"mean error {metric_row['mean_error']}, R2 {metric_row['r2']}"
        )

    for target in report["targets"]:
        lines.extend(["", f"## Worst Cases - {target}", ""])
        for index, case in enumerate(report["worst_cases"][target][:limit], start=1):
            lines.extend(
                [
                    f"### {index}. line {case['line_number']} - abs error {case['abs_error']}",
                    "",
                    f"- Source: {case['source']}",
                    f"- Turn: `{case['turns_completed']}` completed, current total `{case['current_total']}`",
                    f"- Actual `{case['actual']}`, predicted `{case['predicted']}`, error `{case['error']}`",
                    f"- Upper: `{case['upper_score']}` / gap `{case['upper_gap']}`, yacht bonus active `{case['yacht_bonus_active']}`",
                    f"- Open categories: {fmt_names(case['open_category_names'])}",
                    f"- Scorecard: `{case['scorecard']}`",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def main():
    args = parse_args()
    model = load_model(args.model)
    rows = load_predictions(args.data, model)
    report = build_report(args.data, args.model, model, rows, args.limit)
    print(json.dumps({
        "examples": report["examples"],
        "metrics": report["metrics"],
        "quantile_order": report["quantile_order"],
    }, ensure_ascii=False, indent=2))

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[value-dist-eval] wrote JSON report to {output_path}")

    if args.markdown_output:
        markdown_path = Path(args.markdown_output)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(report, max(0, args.limit)), encoding="utf-8")
        print(f"[value-dist-eval] wrote Markdown report to {markdown_path}")


if __name__ == "__main__":
    main()
