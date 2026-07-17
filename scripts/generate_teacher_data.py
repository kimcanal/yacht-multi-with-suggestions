#!/usr/bin/env python3
import argparse
import json
import random
import sys
from itertools import combinations_with_replacement
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yacht_engine

CATEGORY_NAMES = [
    "Ones",
    "Twos",
    "Threes",
    "Fours",
    "Fives",
    "Sixes",
    "Choice",
    "4 of a Kind",
    "Full House",
    "Small Straight",
    "Large Straight",
    "Yacht",
]
CATS = {name: idx for idx, name in enumerate(CATEGORY_NAMES)}
UNIQUE_DICE_STATES = [tuple(dice) for dice in combinations_with_replacement(range(1, 7), 5)]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate ML teacher data from the exact Yacht AI solver."
    )
    parser.add_argument(
        "--output",
        default="artifacts/teacher_data.jsonl",
        help="output JSONL path",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=1000,
        help="number of samples when not using --all-dice",
    )
    parser.add_argument(
        "--all-dice",
        action="store_true",
        help="cover all 252 unique dice multisets",
    )
    parser.add_argument(
        "--contexts-per-dice",
        type=int,
        default=4,
        help="random scorecard contexts per unique dice state with --all-dice",
    )
    parser.add_argument(
        "--mode",
        choices=("both", "focused", "cover"),
        default="both",
        help="strategy mode to export",
    )
    parser.add_argument(
        "--stage",
        choices=("mixed", "roll", "score"),
        default="mixed",
        help="which stage labels to include",
    )
    parser.add_argument(
        "--dice-source",
        choices=("unique", "weighted"),
        default="unique",
        help="dice sampling mode when not using --all-dice",
    )
    parser.add_argument(
        "--min-completed-turns",
        type=int,
        default=0,
        help="minimum number of already-filled turns in the sampled scorecard",
    )
    parser.add_argument(
        "--max-completed-turns",
        type=int,
        default=11,
        help="maximum number of already-filled turns in the sampled scorecard",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260412,
        help="random seed for reproducible data generation",
    )
    parser.add_argument(
        "--report-every",
        type=int,
        default=200,
        help="progress print interval",
    )
    parser.add_argument(
        "--clear-cache-every",
        type=int,
        default=500,
        help="clear solver cache every N samples (0 disables)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="overwrite an existing output file",
    )
    parser.add_argument(
        "--include-breakdown",
        action="store_true",
        help="include the full solver breakdown rows in each sample",
    )
    return parser.parse_args()


def dice_counts(dice):
    counts = [0] * 6
    for value in dice:
        counts[value - 1] += 1
    return counts


def keep_counts(dice, keep_indices):
    kept = [dice[idx] for idx in keep_indices]
    return dice_counts(kept)


def weighted_random_dice(rng):
    return tuple(sorted(rng.randint(1, 6) for _ in range(5)))


def choose_strategy_mode(mode_arg, rng):
    if mode_arg in ("focused", "cover"):
        return mode_arg
    return "cover" if rng.random() < 0.5 else "focused"


def choose_rolls_left(stage_arg, rng):
    if stage_arg == "score":
        return 0
    if stage_arg == "roll":
        return 2 if rng.random() < 0.6 else 1

    roll = rng.random()
    if roll < 0.45:
        return 2
    if roll < 0.8:
        return 1
    return 0


def pick_scoring_category(result, open_categories):
    target_name = result.get("primary_target")
    if target_name in CATS and CATS[target_name] in open_categories:
        return CATS[target_name]

    for row in result.get("breakdown", []):
        row_name = row.get("name")
        if row_name in CATS and CATS[row_name] in open_categories:
            return CATS[row_name]

    return open_categories[0]


def apply_score(scorecard, dice, category_idx):
    score = yacht_engine.calc_score(dice, category_idx)
    yacht_idx = CATS["Yacht"]
    yacht_slot = scorecard[yacht_idx]
    if (
        yacht_slot is not None
        and yacht_slot >= 50
        and category_idx != yacht_idx
        and score > 0
        and yacht_engine.calc_score(dice, yacht_idx) == 50
    ):
        scorecard[yacht_idx] += 100
    scorecard[category_idx] = score
    return score


def simulate_scorecard(rng, turns_completed):
    scorecard = [None] * 12
    for _ in range(turns_completed):
        open_categories = [idx for idx, value in enumerate(scorecard) if value is None]
        if not open_categories:
            break
        final_dice = list(weighted_random_dice(rng))
        mode = choose_strategy_mode("both", rng)
        result = yacht_engine.solve_best_move(final_dice, 0, open_categories, mode, scorecard)
        category_idx = pick_scoring_category(result, open_categories)
        apply_score(scorecard, final_dice, category_idx)
    return scorecard


def build_open_mask(scorecard):
    mask = 0
    for idx, value in enumerate(scorecard):
        if value is None:
            mask |= 1 << idx
    return mask


def serialize_sample(sample_id, dice, rolls_left, strategy_mode, scorecard, result, turns_completed, include_breakdown):
    open_categories = [idx for idx, value in enumerate(scorecard) if value is None]
    upper_score = sum((value or 0) for value in scorecard[:6])
    keep_idx = list(result.get("keep_indices", []))
    sample = {
        "sample_id": sample_id,
        "dice": list(dice),
        "dice_counts": dice_counts(dice),
        "rolls_left": rolls_left,
        "stage": result.get("stage"),
        "strategy_mode": strategy_mode,
        "scorecard": list(scorecard),
        "turns_completed": turns_completed,
        "open_categories": open_categories,
        "open_category_names": [CATEGORY_NAMES[idx] for idx in open_categories],
        "open_mask": build_open_mask(scorecard),
        "upper_score": upper_score,
        "upper_gap": max(0, 63 - upper_score),
        "yacht_value": scorecard[CATS["Yacht"]],
        "yacht_bonus_active": bool(scorecard[CATS["Yacht"]] is not None and scorecard[CATS["Yacht"]] >= 50),
        "label_primary_target": result.get("primary_target"),
        "label_primary_target_idx": CATS.get(result.get("primary_target")),
        "label_expected_value": result.get("expected_value"),
        "label_message": result.get("message"),
        "label_summary": result.get("summary"),
        "label_keep_indices": keep_idx,
        "label_keep_values": [dice[idx] for idx in keep_idx],
        "label_keep_counts": keep_counts(dice, keep_idx),
        "label_breakdown_names": [row.get("name") for row in result.get("breakdown", [])[:5]],
    }
    if include_breakdown:
        sample["label_breakdown"] = result.get("breakdown", [])
    return sample


def iter_current_dice(args, rng):
    if args.all_dice:
        states = list(UNIQUE_DICE_STATES)
        rng.shuffle(states)
        for _ in range(args.contexts_per_dice):
            for dice in states:
                yield dice
        return

    for _ in range(args.samples):
        if args.dice_source == "weighted":
            yield weighted_random_dice(rng)
        else:
            yield rng.choice(UNIQUE_DICE_STATES)


def main():
    args = parse_args()
    output_path = Path(args.output)
    if output_path.exists() and not args.overwrite:
        raise SystemExit(f"{output_path} already exists. Use --overwrite to replace it.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    min_turns = max(0, min(args.min_completed_turns, 11))
    max_turns = max(min_turns, min(args.max_completed_turns, 11))
    rng = random.Random(args.seed)

    total = len(UNIQUE_DICE_STATES) * args.contexts_per_dice if args.all_dice else args.samples
    stage_counts = {"roll": 0, "score": 0}
    mode_counts = {"focused": 0, "cover": 0}

    with output_path.open("w", encoding="utf-8") as handle:
        for sample_id, dice in enumerate(iter_current_dice(args, rng), start=1):
            turns_completed = rng.randint(min_turns, max_turns)
            scorecard = simulate_scorecard(rng, turns_completed)
            strategy_mode = choose_strategy_mode(args.mode, rng)
            rolls_left = choose_rolls_left(args.stage, rng)
            open_categories = [idx for idx, value in enumerate(scorecard) if value is None]
            result = yacht_engine.solve_best_move(list(dice), rolls_left, open_categories, strategy_mode, scorecard)
            sample = serialize_sample(
                sample_id,
                list(dice),
                rolls_left,
                strategy_mode,
                scorecard,
                result,
                turns_completed,
                args.include_breakdown,
            )
            handle.write(json.dumps(sample, ensure_ascii=False) + "\n")

            stage_counts[sample["stage"]] = stage_counts.get(sample["stage"], 0) + 1
            mode_counts[strategy_mode] = mode_counts.get(strategy_mode, 0) + 1

            if args.clear_cache_every and sample_id % args.clear_cache_every == 0:
                yacht_engine.clear_solver_cache()

            if args.report_every and (sample_id % args.report_every == 0 or sample_id == total):
                print(
                    f"[teacher-data] {sample_id}/{total} "
                    f"roll={stage_counts.get('roll', 0)} score={stage_counts.get('score', 0)} "
                    f"focused={mode_counts.get('focused', 0)} cover={mode_counts.get('cover', 0)}"
                )

    print(f"[teacher-data] wrote {total} samples to {output_path}")


if __name__ == "__main__":
    main()
