#!/usr/bin/env python3
import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from yacht_ai.ml_policy import (
    FEATURE_NAMES,
    KEEP_COUNT_CLASSES,
    KEEP_COUNT_TO_INDEX,
    encode_roll_state,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Train a roll-stage distillation policy from teacher JSONL.")
    parser.add_argument("--data", default="artifacts/teacher_data.jsonl", help="input JSONL path")
    parser.add_argument("--output", default="artifacts/roll_policy_model.json", help="output model JSON path")
    parser.add_argument("--epochs", type=int, default=120, help="training epochs")
    parser.add_argument("--hidden-dim", type=int, default=96, help="hidden layer width")
    parser.add_argument("--batch-size", type=int, default=256, help="mini-batch size")
    parser.add_argument("--learning-rate", type=float, default=0.003, help="Adam learning rate")
    parser.add_argument("--weight-decay", type=float, default=1e-5, help="L2 penalty")
    parser.add_argument("--val-ratio", type=float, default=0.2, help="validation split ratio")
    parser.add_argument("--seed", type=int, default=20260412, help="random seed")
    parser.add_argument("--model-id", help="optional model identifier stored in metadata")
    parser.add_argument("--created-date", help="optional creation date stored in metadata")
    return parser.parse_args()


def load_roll_examples(path):
    features = []
    labels = []
    strategy_counts = {"focused": 0, "cover": 0}
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row.get("stage") != "roll":
                continue
            keep_counts = tuple(int(value) for value in row.get("label_keep_counts", []))
            if len(keep_counts) != 6:
                continue
            label_idx = KEEP_COUNT_TO_INDEX.get(keep_counts)
            if label_idx is None:
                continue
            features.append(
                encode_roll_state(
                    row.get("dice", []),
                    row.get("rolls_left", 0),
                    row.get("strategy_mode", "focused"),
                    row.get("scorecard", []),
                )
            )
            labels.append(label_idx)
            strategy = row.get("strategy_mode", "focused")
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1

    if not features:
        raise SystemExit(f"No roll-stage samples found in {path}")

    x = np.vstack(features).astype(np.float32)
    y = np.asarray(labels, dtype=np.int64)
    return x, y, strategy_counts


def split_indices(size, val_ratio, rng):
    indices = list(range(size))
    rng.shuffle(indices)
    val_size = max(1, min(size - 1, int(round(size * val_ratio)))) if size > 1 else 0
    return indices[val_size:], indices[:val_size]


def evaluate(x, y, w1, b1, w2, b2):
    if x.shape[0] == 0:
        return {"loss": 0.0, "accuracy": 0.0}

    hidden = np.maximum(x @ w1 + b1, 0.0)
    logits = hidden @ w2 + b2
    logits = logits - np.max(logits, axis=1, keepdims=True)
    exp = np.exp(logits)
    probs = exp / np.sum(exp, axis=1, keepdims=True)
    chosen = probs[np.arange(y.shape[0]), y]
    loss = float(-np.mean(np.log(chosen + 1e-12)))
    accuracy = float(np.mean(np.argmax(probs, axis=1) == y))
    return {"loss": loss, "accuracy": accuracy}


def main():
    args = parse_args()
    rng = random.Random(args.seed)
    np_rng = np.random.default_rng(args.seed)

    x, y, strategy_counts = load_roll_examples(args.data)
    train_idx, val_idx = split_indices(x.shape[0], args.val_ratio, rng)
    x_train = x[train_idx]
    y_train = y[train_idx]
    x_val = x[val_idx]
    y_val = y[val_idx]

    feature_mean = x_train.mean(axis=0)
    feature_std = x_train.std(axis=0)
    feature_std[feature_std < 1e-6] = 1.0

    x_train = ((x_train - feature_mean) / feature_std).astype(np.float32)
    x_val = ((x_val - feature_mean) / feature_std).astype(np.float32)

    input_dim = x_train.shape[1]
    num_classes = len(KEEP_COUNT_CLASSES)
    hidden_dim = int(args.hidden_dim)

    w1 = (np_rng.standard_normal((input_dim, hidden_dim)).astype(np.float32) * np.sqrt(2.0 / max(1, input_dim)))
    b1 = np.zeros(hidden_dim, dtype=np.float32)
    w2 = (np_rng.standard_normal((hidden_dim, num_classes)).astype(np.float32) * np.sqrt(2.0 / max(1, hidden_dim)))
    b2 = np.zeros(num_classes, dtype=np.float32)

    m_w1 = np.zeros_like(w1)
    v_w1 = np.zeros_like(w1)
    m_b1 = np.zeros_like(b1)
    v_b1 = np.zeros_like(b1)
    m_w2 = np.zeros_like(w2)
    v_w2 = np.zeros_like(w2)
    m_b2 = np.zeros_like(b2)
    v_b2 = np.zeros_like(b2)
    beta1 = 0.9
    beta2 = 0.999
    epsilon = 1e-8
    step = 0

    best_val = {"loss": float("inf"), "accuracy": float("-inf"), "epoch": 0}
    best_state = None
    batch_size = max(1, int(args.batch_size))

    for epoch in range(1, args.epochs + 1):
        order = np_rng.permutation(x_train.shape[0])
        epoch_loss = 0.0
        seen = 0

        for start in range(0, x_train.shape[0], batch_size):
            batch_ids = order[start : start + batch_size]
            xb = x_train[batch_ids]
            yb = y_train[batch_ids]

            z1 = xb @ w1 + b1
            h1 = np.maximum(z1, 0.0)
            logits = h1 @ w2 + b2
            logits = logits - np.max(logits, axis=1, keepdims=True)
            exp = np.exp(logits)
            probs = exp / np.sum(exp, axis=1, keepdims=True)
            batch_loss = -np.mean(np.log(probs[np.arange(yb.shape[0]), yb] + 1e-12))
            epoch_loss += float(batch_loss) * yb.shape[0]
            seen += yb.shape[0]

            grad_logits = probs
            grad_logits[np.arange(yb.shape[0]), yb] -= 1.0
            grad_logits /= yb.shape[0]

            grad_w2 = h1.T @ grad_logits + (args.weight_decay * w2)
            grad_b2 = np.sum(grad_logits, axis=0)
            grad_h1 = grad_logits @ w2.T
            grad_z1 = grad_h1 * (z1 > 0)
            grad_w1 = xb.T @ grad_z1 + (args.weight_decay * w1)
            grad_b1 = np.sum(grad_z1, axis=0)

            step += 1
            for param, grad, m, v in (
                (w1, grad_w1, m_w1, v_w1),
                (b1, grad_b1, m_b1, v_b1),
                (w2, grad_w2, m_w2, v_w2),
                (b2, grad_b2, m_b2, v_b2),
            ):
                m *= beta1
                m += (1.0 - beta1) * grad
                v *= beta2
                v += (1.0 - beta2) * (grad * grad)
                m_hat = m / (1.0 - (beta1**step))
                v_hat = v / (1.0 - (beta2**step))
                param -= args.learning_rate * m_hat / (np.sqrt(v_hat) + epsilon)

        train_metrics = evaluate(x_train, y_train, w1, b1, w2, b2)
        val_metrics = evaluate(x_val, y_val, w1, b1, w2, b2)
        avg_epoch_loss = epoch_loss / max(1, seen)
        print(
            f"[roll-policy] epoch={epoch:03d} "
            f"train_loss={avg_epoch_loss:.4f} train_acc={train_metrics['accuracy']:.4f} "
            f"val_loss={val_metrics['loss']:.4f} val_acc={val_metrics['accuracy']:.4f}"
        )

        if (
            val_metrics["accuracy"] > best_val["accuracy"]
            or (
                abs(val_metrics["accuracy"] - best_val["accuracy"]) <= 1e-9
                and val_metrics["loss"] < best_val["loss"]
            )
        ):
            best_val = val_metrics
            best_val["epoch"] = epoch
            best_state = (
                w1.copy(),
                b1.copy(),
                w2.copy(),
                b2.copy(),
            )

    if best_state is None:
        raise SystemExit("Training did not produce a model state.")

    w1, b1, w2, b2 = best_state
    train_metrics = evaluate(x_train, y_train, w1, b1, w2, b2)
    val_metrics = evaluate(x_val, y_val, w1, b1, w2, b2)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "feature_names": list(FEATURE_NAMES),
        "feature_mean": feature_mean.astype(np.float32).tolist(),
        "feature_std": feature_std.astype(np.float32).tolist(),
        "w1": w1.astype(np.float32).tolist(),
        "b1": b1.astype(np.float32).tolist(),
        "w2": w2.astype(np.float32).tolist(),
        "b2": b2.astype(np.float32).tolist(),
        "metadata": {
            "model_id": args.model_id or output_path.stem,
            "model_type": "roll_mlp_v1",
            "created_date": args.created_date,
            "data_path": args.data,
            "input_dim": input_dim,
            "hidden_dim": hidden_dim,
            "num_classes": num_classes,
            "epochs": args.epochs,
            "batch_size": batch_size,
            "learning_rate": args.learning_rate,
            "weight_decay": args.weight_decay,
            "seed": args.seed,
            "best_epoch": best_val["epoch"],
            "train_examples": int(x_train.shape[0]),
            "val_examples": int(x_val.shape[0]),
            "train_loss": round(train_metrics["loss"], 6),
            "train_accuracy": round(train_metrics["accuracy"], 6),
            "val_loss": round(val_metrics["loss"], 6),
            "val_accuracy": round(val_metrics["accuracy"], 6),
            "strategy_counts": strategy_counts,
        },
    }
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)

    print(f"[roll-policy] wrote model to {output_path}")
    print(
        f"[roll-policy] best_epoch={best_val['epoch']} "
        f"final train_acc={train_metrics['accuracy']:.4f} "
        f"val_acc={val_metrics['accuracy']:.4f}"
    )


if __name__ == "__main__":
    main()
