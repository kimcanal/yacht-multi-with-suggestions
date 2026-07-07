#!/usr/bin/env python3
"""Train ridge baselines for scorecard value distribution targets."""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from yacht_ai.value_model import VALUE_FEATURE_NAMES


DEFAULT_TARGETS = (
    "target_remaining_mean",
    "target_remaining_stdev",
    "target_remaining_p10",
    "target_remaining_p50",
    "target_remaining_p90",
    "target_upper_bonus_rate",
)


def parse_args():
    parser = argparse.ArgumentParser(description="Train multi-target linear baselines for value distribution data.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", default="artifacts/models/scorecard-value-distribution-linear-v1.json")
    parser.add_argument("--targets", default=",".join(DEFAULT_TARGETS))
    parser.add_argument("--ridge", type=float, default=1.0)
    parser.add_argument("--validation-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=20260708)
    parser.add_argument("--model-id", default="scorecard-value-distribution-linear-v1")
    return parser.parse_args()


def parse_targets(raw):
    targets = [name.strip() for name in raw.split(",") if name.strip()]
    if not targets:
        raise SystemExit("at least one target is required")
    return targets


def load_rows(path, targets):
    features = []
    target_rows = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if any(target not in row for target in targets):
                continue
            features.append([float(value) for value in row["feature_values"]])
            target_rows.append([float(row[target]) for target in targets])
    if not features:
        raise SystemExit(f"No usable distribution rows found in {path}")
    return np.asarray(features, dtype=np.float64), np.asarray(target_rows, dtype=np.float64)


def split_indices(count, validation_ratio, seed):
    indices = list(range(count))
    random.Random(seed).shuffle(indices)
    val_count = max(1, min(count - 1, int(round(count * validation_ratio)))) if count > 1 else 0
    return indices[val_count:], indices[:val_count]


def fit_ridge_multi(x_train, y_train, ridge):
    ones = np.ones((x_train.shape[0], 1), dtype=np.float64)
    design = np.hstack([ones, x_train])
    penalty = np.eye(design.shape[1], dtype=np.float64) * float(ridge)
    penalty[0, 0] = 0.0
    return np.linalg.solve(design.T @ design + penalty, design.T @ y_train)


def predict(weights, x):
    ones = np.ones((x.shape[0], 1), dtype=np.float64)
    return np.hstack([ones, x]) @ weights


def target_metrics(y_true, y_pred):
    residual = y_pred - y_true
    denom = float(np.sum((y_true - np.mean(y_true)) ** 2))
    r2 = 0.0 if denom <= 0 else 1.0 - float(np.sum(residual ** 2)) / denom
    return {
        "mae": round(float(np.mean(np.abs(residual))), 6),
        "rmse": round(float(math.sqrt(np.mean(residual ** 2))), 6),
        "mean_error": round(float(np.mean(residual)), 6),
        "r2": round(r2, 6),
    }


def metrics_by_target(targets, y_true, y_pred):
    return {
        target: target_metrics(y_true[:, idx], y_pred[:, idx])
        for idx, target in enumerate(targets)
    }


def quantile_order_report(targets, predictions):
    required = ["target_remaining_p10", "target_remaining_p50", "target_remaining_p90"]
    if any(target not in targets for target in required):
        return None
    p10_idx = targets.index("target_remaining_p10")
    p50_idx = targets.index("target_remaining_p50")
    p90_idx = targets.index("target_remaining_p90")
    lower_violations = int(np.sum(predictions[:, p10_idx] > predictions[:, p50_idx]))
    upper_violations = int(np.sum(predictions[:, p50_idx] > predictions[:, p90_idx]))
    any_violations = int(np.sum(
        (predictions[:, p10_idx] > predictions[:, p50_idx])
        | (predictions[:, p50_idx] > predictions[:, p90_idx])
    ))
    return {
        "examples": int(predictions.shape[0]),
        "p10_gt_p50": lower_violations,
        "p50_gt_p90": upper_violations,
        "any_violation": any_violations,
        "violation_rate": round(any_violations / max(1, predictions.shape[0]), 6),
    }


def main():
    args = parse_args()
    targets = parse_targets(args.targets)
    x, y = load_rows(args.data, targets)
    train_idx, val_idx = split_indices(len(y), args.validation_ratio, args.seed)
    x_train = x[train_idx]
    y_train = y[train_idx]
    x_val = x[val_idx] if val_idx else x_train
    y_val = y[val_idx] if val_idx else y_train

    weights = fit_ridge_multi(x_train, y_train, args.ridge)
    train_predictions = predict(weights, x_train)
    val_predictions = predict(weights, x_val)
    payload = {
        "model_id": args.model_id,
        "model_type": "scorecard_value_distribution_linear_v1",
        "targets": targets,
        "ridge": args.ridge,
        "feature_names": list(VALUE_FEATURE_NAMES),
        "train_examples": int(len(y_train)),
        "validation_examples": int(len(y_val)),
        "train_metrics": metrics_by_target(targets, y_train, train_predictions),
        "validation_metrics": metrics_by_target(targets, y_val, val_predictions),
        "train_quantile_order": quantile_order_report(targets, train_predictions),
        "validation_quantile_order": quantile_order_report(targets, val_predictions),
        "bias": [float(value) for value in weights[0, :]],
        "weights": [
            [float(value) for value in row]
            for row in weights[1:, :]
        ],
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "model_id": payload["model_id"],
        "targets": targets,
        "train_examples": payload["train_examples"],
        "validation_examples": payload["validation_examples"],
        "validation_metrics": payload["validation_metrics"],
        "validation_quantile_order": payload["validation_quantile_order"],
    }, ensure_ascii=False, indent=2))
    print(f"[value-dist-baseline] wrote model to {output_path}")


if __name__ == "__main__":
    main()
