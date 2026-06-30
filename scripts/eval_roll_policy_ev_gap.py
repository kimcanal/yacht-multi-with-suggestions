#!/usr/bin/env python3
import argparse
import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from yacht_ai.ml_policy import RollPolicyModel, _fixed_keep_roll_explanation, keep_counts_to_indices


def parse_args():
    parser = argparse.ArgumentParser(
        description="Evaluate roll-policy mistakes by exact expected-value gap."
    )
    parser.add_argument("--data", default="artifacts/teacher_roll_32768.jsonl", help="teacher JSONL path")
    parser.add_argument("--model", required=True, help="trained roll-policy model path")
    parser.add_argument("--output", help="optional JSON report path")
    parser.add_argument("--val-ratio", type=float, default=0.2, help="validation split ratio")
    parser.add_argument("--seed", type=int, default=20260412, help="validation split seed")
    parser.add_argument("--limit", type=int, default=0, help="maximum validation rows to evaluate; 0 means all")
    parser.add_argument("--worst", type=int, default=12, help="number of worst-gap rows to include")
    parser.add_argument(
        "--thresholds",
        default="0.80,0.90,0.95,0.98,0.99",
        help="comma-separated confidence thresholds to summarize",
    )
    parser.add_argument("--progress-every", type=int, default=500, help="progress print interval; 0 disables")
    return parser.parse_args()


def load_roll_rows(path):
    rows = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row.get("stage") != "roll":
                continue
            keep_counts = row.get("label_keep_counts")
            if not isinstance(keep_counts, list) or len(keep_counts) != 6:
                continue
            rows.append(row)
    if not rows:
        raise SystemExit(f"No roll-stage rows found in {path}")
    return rows


def split_validation_rows(rows, val_ratio, rng):
    indices = list(range(len(rows)))
    rng.shuffle(indices)
    val_size = max(1, min(len(rows) - 1, int(round(len(rows) * val_ratio)))) if len(rows) > 1 else 0
    return [rows[idx] for idx in indices[:val_size]]


def percentile(values, pct):
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * pct
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return float((ordered[lower] * (1.0 - weight)) + (ordered[upper] * weight))


def summarize_gaps(rows, key="excess_ev_gap"):
    gaps = [row[key] for row in rows]
    if not gaps:
        return {
            "count": 0,
            "mean_ev_gap": 0.0,
            "median_ev_gap": 0.0,
            "p95_ev_gap": 0.0,
            "p99_ev_gap": 0.0,
            "max_ev_gap": 0.0,
            "gap_gt_0_25": 0,
            "gap_gt_1": 0,
            "gap_gt_2": 0,
        }
    return {
        "count": len(gaps),
        "mean_ev_gap": round(float(statistics.fmean(gaps)), 6),
        "median_ev_gap": round(float(statistics.median(gaps)), 6),
        "p95_ev_gap": round(percentile(gaps, 0.95), 6),
        "p99_ev_gap": round(percentile(gaps, 0.99), 6),
        "max_ev_gap": round(max(gaps), 6),
        "gap_gt_0_25": sum(1 for gap in gaps if gap > 0.25),
        "gap_gt_1": sum(1 for gap in gaps if gap > 1.0),
        "gap_gt_2": sum(1 for gap in gaps if gap > 2.0),
    }


def compact_case(row, model_action, model_explanation, model_gap, teacher_gap, excess_gap):
    return {
        "sample_id": row.get("sample_id"),
        "dice": row.get("dice"),
        "rolls_left": row.get("rolls_left"),
        "strategy_mode": row.get("strategy_mode"),
        "turns_completed": row.get("turns_completed"),
        "open_category_names": row.get("open_category_names"),
        "teacher_keep_values": row.get("label_keep_values"),
        "teacher_target": row.get("label_primary_target"),
        "model_keep_values": model_action.get("keep_values"),
        "model_confidence": round(model_action.get("confidence", 0.0), 6),
        "model_message": model_explanation.get("message"),
        "model_target": model_explanation.get("primary_target"),
        "model_expected_value": model_explanation.get("expected_value"),
        "teacher_objective_gap": round(teacher_gap, 6),
        "model_objective_gap": round(model_gap, 6),
        "excess_ev_gap": round(excess_gap, 6),
    }


def evaluate(args):
    rows = load_roll_rows(args.data)
    val_rows = split_validation_rows(rows, args.val_ratio, random.Random(args.seed))
    if args.limit and args.limit > 0:
        val_rows = val_rows[: args.limit]

    thresholds = [float(part.strip()) for part in args.thresholds.split(",") if part.strip()]
    model = RollPolicyModel.load(args.model)

    evaluated = []
    mismatches = []
    top3_matches = 0
    misses = 0

    for idx, row in enumerate(val_rows, start=1):
        actions = model.predict_valid_actions(
            row.get("dice", []),
            row.get("rolls_left", 0),
            row.get("strategy_mode", "focused"),
            row.get("scorecard", []),
            top_k=3,
        )
        if not actions:
            misses += 1
            continue

        teacher_counts = tuple(int(value) for value in row.get("label_keep_counts", []))
        top1_action = actions[0]
        top1_match = tuple(top1_action["keep_counts"]) == teacher_counts
        top3_match = any(tuple(action["keep_counts"]) == teacher_counts for action in actions)
        top3_matches += int(top3_match)

        model_gap = 0.0
        teacher_gap = 0.0
        excess_gap = 0.0
        case = None
        if not top1_match:
            model_explanation = _fixed_keep_roll_explanation(
                row.get("dice", []),
                top1_action["keep_indices"],
                int(row.get("rolls_left", 0)),
                row.get("strategy_mode", "focused"),
                row.get("scorecard", []),
            )
            teacher_indices = keep_counts_to_indices(row.get("dice", []), teacher_counts)
            teacher_explanation = _fixed_keep_roll_explanation(
                row.get("dice", []),
                teacher_indices,
                int(row.get("rolls_left", 0)),
                row.get("strategy_mode", "focused"),
                row.get("scorecard", []),
            )
            model_gap = float(model_explanation.get("optimality_gap", 0.0))
            teacher_gap = float(teacher_explanation.get("optimality_gap", 0.0))
            excess_gap = max(0.0, model_gap - teacher_gap)
            case = compact_case(row, top1_action, model_explanation, model_gap, teacher_gap, excess_gap)
        record = {
            "top1_match": top1_match,
            "top3_match": top3_match,
            "confidence": float(top1_action.get("confidence", 0.0)),
            "teacher_objective_gap": teacher_gap,
            "model_objective_gap": model_gap,
            "excess_ev_gap": excess_gap,
            "case": case,
        }
        evaluated.append(record)
        if not top1_match:
            mismatches.append(record)

        if args.progress_every and (idx % args.progress_every == 0 or idx == len(val_rows)):
            print(f"[roll-policy-ev-gap] evaluated={idx}/{len(val_rows)} mismatches={len(mismatches)}")

    total = len(evaluated)
    correct = sum(1 for row in evaluated if row["top1_match"])
    threshold_rows = []
    for threshold in thresholds:
        covered = [row for row in evaluated if row["confidence"] >= threshold]
        covered_correct = sum(1 for row in covered if row["top1_match"])
        threshold_rows.append(
            {
                "threshold": threshold,
                "coverage": round(len(covered) / total, 6) if total else 0.0,
                "accuracy": round(covered_correct / len(covered), 6) if covered else 0.0,
                "covered_examples": len(covered),
                **summarize_gaps(covered),
            }
        )

    worst_cases = [
        row["case"]
        for row in sorted(evaluated, key=lambda item: (item["excess_ev_gap"], item["confidence"]), reverse=True)
        if row["case"] is not None
    ]
    worst_cases = worst_cases[: max(0, args.worst)]
    report = {
        "model_path": args.model,
        "data_path": args.data,
        "val_ratio": args.val_ratio,
        "seed": args.seed,
        "evaluated_examples": total,
        "missing_predictions": misses,
        "top1_accuracy": round(correct / total, 6) if total else 0.0,
        "top3_accuracy": round(top3_matches / total, 6) if total else 0.0,
        "overall_excess_ev_gap": summarize_gaps(evaluated, "excess_ev_gap"),
        "mismatch_excess_ev_gap": summarize_gaps(mismatches, "excess_ev_gap"),
        "teacher_objective_gap": summarize_gaps(evaluated, "teacher_objective_gap"),
        "model_objective_gap": summarize_gaps(evaluated, "model_objective_gap"),
        "thresholds": threshold_rows,
        "worst_cases": worst_cases,
        "model_metadata": model.metadata,
    }
    return report


def main():
    args = parse_args()
    report = evaluate(args)

    print(
        "[roll-policy-ev-gap] "
        f"examples={report['evaluated_examples']} "
        f"top1={report['top1_accuracy']:.6f} "
        f"mean_excess_gap={report['overall_excess_ev_gap']['mean_ev_gap']:.6f} "
        f"p95_excess_gap={report['overall_excess_ev_gap']['p95_ev_gap']:.6f} "
        f"max_excess_gap={report['overall_excess_ev_gap']['max_ev_gap']:.6f}"
    )
    print(
        "[roll-policy-ev-gap] "
        f"mismatches={report['mismatch_excess_ev_gap']['count']} "
        f"mismatch_mean_excess_gap={report['mismatch_excess_ev_gap']['mean_ev_gap']:.6f} "
        f"mismatch_p95_excess_gap={report['mismatch_excess_ev_gap']['p95_ev_gap']:.6f}"
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print(f"[roll-policy-ev-gap] wrote report to {output_path}")


if __name__ == "__main__":
    main()
