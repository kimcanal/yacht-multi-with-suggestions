#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.train_roll_policy import load_roll_examples, split_indices
from yacht_ai.ml_policy import RollPolicyModel, _softmax, valid_keep_class_indices


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate a trained roll-stage policy on the held-out split.")
    parser.add_argument("--data", default="artifacts/teacher_roll_32768.jsonl", help="teacher JSONL path")
    parser.add_argument("--model", default="artifacts/roll_policy_model.json", help="trained model path")
    parser.add_argument("--val-ratio", type=float, default=0.2, help="validation split ratio")
    parser.add_argument("--seed", type=int, default=20260412, help="split seed")
    parser.add_argument(
        "--thresholds",
        default="0.80,0.90,0.95,0.98,0.99",
        help="comma-separated confidence thresholds to report",
    )
    parser.add_argument(
        "--output",
        help="optional JSON report path",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    x, y, _ = load_roll_examples(args.data)
    _, val_idx = split_indices(x.shape[0], args.val_ratio, __import__("random").Random(args.seed))
    x_val = x[val_idx]
    y_val = y[val_idx]
    thresholds = [float(part.strip()) for part in args.thresholds.split(",") if part.strip()]

    model = RollPolicyModel.load(args.model)

    total = len(y_val)
    correct = 0
    top3 = 0
    threshold_hits = {threshold: {"covered": 0, "correct": 0} for threshold in thresholds}

    for features, label_idx in zip(x_val, y_val):
        logits = model.predict_logits(features)
        probs = _softmax(logits)
        dice_counts = tuple(int(round(value * 5)) for value in features[:6])
        valid_indices = valid_keep_class_indices(dice_counts)
        valid_probs = probs[list(valid_indices)]
        valid_probs = valid_probs / float(np.sum(valid_probs))
        ranked_positions = np.argsort(valid_probs)[::-1]
        ranked_indices = [valid_indices[int(position)] for position in ranked_positions]
        best_index = ranked_indices[0]
        best_confidence = float(valid_probs[int(ranked_positions[0])])

        is_correct = int(best_index == label_idx)
        correct += is_correct
        top3 += int(label_idx in ranked_indices[:3])

        for threshold in thresholds:
            if best_confidence >= threshold:
                threshold_hits[threshold]["covered"] += 1
                threshold_hits[threshold]["correct"] += is_correct

    top1_acc = correct / total if total else 0.0
    top3_acc = top3 / total if total else 0.0
    threshold_rows = []
    print(
        f"[roll-policy-eval] val_examples={total} "
        f"top1_acc={top1_acc:.6f} top3_acc={top3_acc:.6f}"
    )
    for threshold in thresholds:
        covered = threshold_hits[threshold]["covered"]
        coverage = covered / total if total else 0.0
        acc = threshold_hits[threshold]["correct"] / covered if covered else 0.0
        threshold_rows.append(
            {
                "threshold": threshold,
                "coverage": round(coverage, 6),
                "accuracy": round(acc, 6),
                "covered_examples": int(covered),
            }
        )
        print(
            f"[roll-policy-eval] threshold={threshold:.2f} "
            f"coverage={coverage:.6f} acc={acc:.6f} covered_examples={covered}"
        )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "model_path": args.model,
            "data_path": args.data,
            "val_ratio": args.val_ratio,
            "seed": args.seed,
            "val_examples": int(total),
            "top1_accuracy": round(top1_acc, 6),
            "top3_accuracy": round(top3_acc, 6),
            "thresholds": threshold_rows,
            "model_metadata": model.metadata,
        }
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print(f"[roll-policy-eval] wrote report to {output_path}")


if __name__ == "__main__":
    main()
