#!/usr/bin/env python3
import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.eval_roll_policy_ev_gap import load_roll_rows, split_validation_rows, summarize_gaps
from yacht_ai.ml_policy import RollPolicyModel, _fixed_keep_roll_explanation, keep_counts_to_indices


def parse_args():
    parser = argparse.ArgumentParser(
        description="Evaluate the learned roll policy as deployed: confidence gate + exact fallback guard."
    )
    parser.add_argument("--data", default="artifacts/teacher_roll_32768.jsonl", help="teacher JSONL path")
    parser.add_argument("--model", required=True, help="trained roll-policy model path")
    parser.add_argument("--output", help="optional JSON report path")
    parser.add_argument("--val-ratio", type=float, default=0.2, help="validation split ratio")
    parser.add_argument("--seed", type=int, default=20260412, help="validation split seed")
    parser.add_argument("--min-confidence", type=float, default=0.95, help="runtime confidence gate")
    parser.add_argument("--guard-gap", type=float, default=0.25, help="runtime pure-objective gap guard")
    parser.add_argument("--limit", type=int, default=0, help="maximum validation rows to evaluate; 0 means all")
    parser.add_argument("--progress-every", type=int, default=500, help="progress print interval; 0 disables")
    return parser.parse_args()


def keep_counts_from_indices(dice, keep_indices):
    counts = [0] * 6
    for idx in keep_indices:
        value = int(dice[idx])
        if 1 <= value <= 6:
            counts[value - 1] += 1
    return tuple(counts)


def main():
    args = parse_args()
    rows = split_validation_rows(load_roll_rows(args.data), args.val_ratio, random.Random(args.seed))
    if args.limit and args.limit > 0:
        rows = rows[: args.limit]

    model = RollPolicyModel.load(args.model)
    accepted = []
    accepted_mismatches = []
    rejected_by_confidence = 0
    rejected_by_guard = 0
    missing_predictions = 0
    effective_excess_rows = []

    for idx, row in enumerate(rows, start=1):
        actions = model.predict_valid_actions(
            row.get("dice", []),
            row.get("rolls_left", 0),
            row.get("strategy_mode", "focused"),
            row.get("scorecard", []),
            top_k=1,
        )
        if not actions:
            missing_predictions += 1
            effective_excess_rows.append({"excess_ev_gap": 0.0})
            continue

        action = actions[0]
        confidence = float(action.get("confidence", 0.0))
        if confidence < args.min_confidence:
            rejected_by_confidence += 1
            effective_excess_rows.append({"excess_ev_gap": 0.0})
            continue

        model_explanation = _fixed_keep_roll_explanation(
            row.get("dice", []),
            action["keep_indices"],
            int(row.get("rolls_left", 0)),
            row.get("strategy_mode", "focused"),
            row.get("scorecard", []),
        )
        model_gap = float(model_explanation.get("optimality_gap", 0.0))
        if model_gap > args.guard_gap:
            rejected_by_guard += 1
            effective_excess_rows.append({"excess_ev_gap": 0.0})
            continue

        teacher_counts = tuple(int(value) for value in row.get("label_keep_counts", []))
        model_counts = keep_counts_from_indices(row.get("dice", []), action["keep_indices"])
        top1_match = model_counts == teacher_counts
        excess_gap = 0.0
        if not top1_match:
            teacher_indices = keep_counts_to_indices(row.get("dice", []), teacher_counts)
            teacher_explanation = _fixed_keep_roll_explanation(
                row.get("dice", []),
                teacher_indices,
                int(row.get("rolls_left", 0)),
                row.get("strategy_mode", "focused"),
                row.get("scorecard", []),
            )
            teacher_gap = float(teacher_explanation.get("optimality_gap", 0.0))
            excess_gap = max(0.0, model_gap - teacher_gap)

        record = {
            "top1_match": top1_match,
            "confidence": confidence,
            "model_objective_gap": model_gap,
            "excess_ev_gap": excess_gap,
        }
        accepted.append(record)
        effective_excess_rows.append(record)
        if not top1_match:
            accepted_mismatches.append(record)

        if args.progress_every and (idx % args.progress_every == 0 or idx == len(rows)):
            print(
                f"[roll-policy-runtime] evaluated={idx}/{len(rows)} "
                f"accepted={len(accepted)} guard_rejects={rejected_by_guard}"
            )

    total = len(rows)
    report = {
        "model_path": args.model,
        "data_path": args.data,
        "val_ratio": args.val_ratio,
        "seed": args.seed,
        "min_confidence": args.min_confidence,
        "guard_gap": args.guard_gap,
        "evaluated_examples": total,
        "accepted_examples": len(accepted),
        "acceptance_rate": round(len(accepted) / total, 6) if total else 0.0,
        "rejected_by_confidence": rejected_by_confidence,
        "rejected_by_guard": rejected_by_guard,
        "missing_predictions": missing_predictions,
        "accepted_top1_accuracy": round(
            sum(1 for row in accepted if row["top1_match"]) / len(accepted), 6
        )
        if accepted
        else 0.0,
        "accepted_excess_ev_gap": summarize_gaps(accepted, "excess_ev_gap"),
        "accepted_mismatch_excess_ev_gap": summarize_gaps(accepted_mismatches, "excess_ev_gap"),
        "effective_excess_ev_gap_with_fallback": summarize_gaps(effective_excess_rows, "excess_ev_gap"),
        "model_metadata": model.metadata,
    }

    print(
        "[roll-policy-runtime] "
        f"examples={total} accepted={report['accepted_examples']} "
        f"acceptance={report['acceptance_rate']:.6f} "
        f"accepted_acc={report['accepted_top1_accuracy']:.6f} "
        f"guard_rejects={rejected_by_guard}"
    )
    print(
        "[roll-policy-runtime] "
        f"effective_mean_gap={report['effective_excess_ev_gap_with_fallback']['mean_ev_gap']:.6f} "
        f"effective_max_gap={report['effective_excess_ev_gap_with_fallback']['max_ev_gap']:.6f}"
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print(f"[roll-policy-runtime] wrote report to {output_path}")


if __name__ == "__main__":
    main()
