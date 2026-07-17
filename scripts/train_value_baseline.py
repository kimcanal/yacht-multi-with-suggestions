#!/usr/bin/env python3
"""Train a small ridge-regression baseline for scorecard value targets."""

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


def parse_args():
    parser = argparse.ArgumentParser(description="Train a linear value baseline from self-play JSONL.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", default="artifacts/generated/models/scorecard-value-linear-v1.json")
    parser.add_argument("--target", default="target_remaining_score")
    parser.add_argument("--ridge", type=float, default=1.0)
    parser.add_argument("--validation-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=20260708)
    parser.add_argument("--model-id", default="scorecard-value-linear-v1")
    return parser.parse_args()


def load_rows(path, target_name):
    features = []
    targets = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if target_name not in row:
                continue
            features.append([float(value) for value in row["feature_values"]])
            targets.append(float(row[target_name]))
    if not features:
        raise SystemExit(f"No usable value rows found in {path}")
    return np.asarray(features, dtype=np.float64), np.asarray(targets, dtype=np.float64)


def split_indices(count, validation_ratio, seed):
    indices = list(range(count))
    random.Random(seed).shuffle(indices)
    val_count = max(1, min(count - 1, int(round(count * validation_ratio)))) if count > 1 else 0
    return indices[val_count:], indices[:val_count]


def fit_ridge(x_train, y_train, ridge):
    ones = np.ones((x_train.shape[0], 1), dtype=np.float64)
    design = np.hstack([ones, x_train])
    penalty = np.eye(design.shape[1], dtype=np.float64) * float(ridge)
    penalty[0, 0] = 0.0
    return np.linalg.solve(design.T @ design + penalty, design.T @ y_train)


def predict(weights, x):
    ones = np.ones((x.shape[0], 1), dtype=np.float64)
    return np.hstack([ones, x]) @ weights


def metrics(y_true, y_pred):
    residual = y_pred - y_true
    mae = float(np.mean(np.abs(residual)))
    rmse = float(math.sqrt(np.mean(residual ** 2)))
    denom = float(np.sum((y_true - np.mean(y_true)) ** 2))
    r2 = 0.0 if denom <= 0 else 1.0 - float(np.sum(residual ** 2)) / denom
    return {
        "mae": round(mae, 6),
        "rmse": round(rmse, 6),
        "r2": round(r2, 6),
    }


def main():
    args = parse_args()
    x, y = load_rows(args.data, args.target)
    train_idx, val_idx = split_indices(len(y), args.validation_ratio, args.seed)
    x_train = x[train_idx]
    y_train = y[train_idx]
    x_val = x[val_idx] if val_idx else x_train
    y_val = y[val_idx] if val_idx else y_train

    weights = fit_ridge(x_train, y_train, args.ridge)
    train_metrics = metrics(y_train, predict(weights, x_train))
    val_metrics = metrics(y_val, predict(weights, x_val))
    payload = {
        "model_id": args.model_id,
        "model_type": "scorecard_value_linear_v1",
        "target": args.target,
        "ridge": args.ridge,
        "feature_names": list(VALUE_FEATURE_NAMES),
        "train_examples": int(len(y_train)),
        "validation_examples": int(len(y_val)),
        "train_metrics": train_metrics,
        "validation_metrics": val_metrics,
        "bias": float(weights[0]),
        "weights": [float(value) for value in weights[1:]],
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("model_id", "train_examples", "validation_examples", "train_metrics", "validation_metrics")}, ensure_ascii=False, indent=2))
    print(f"[value-baseline] wrote model to {output_path}")


if __name__ == "__main__":
    main()
