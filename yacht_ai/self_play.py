import random
import statistics

from yacht_core.constants import CATEGORY_NAMES, CATS
from yacht_core.scoring import calc_score

from .solvers import clear_solver_cache, solve_best_move
from .value.model import normalize_scorecard, scorecard_totals, value_state_payload


def reroll_from_keep(rng, dice, keep_indices):
    keep = set(keep_indices)
    return [value if idx in keep else rng.randint(1, 6) for idx, value in enumerate(dice)]


def choose_score_category(dice, scorecard, mode):
    open_categories = [idx for idx, value in enumerate(scorecard) if value is None]
    result = solve_best_move(dice, 0, open_categories, mode, scorecard)
    category_idx = CATS.get(result.get("primary_target"))
    if category_idx in open_categories:
        return category_idx, result

    for row in result.get("breakdown", []):
        category_idx = CATS.get(row.get("name"))
        if category_idx in open_categories:
            return category_idx, result

    return max(open_categories, key=lambda idx: calc_score(dice, idx)), result


def apply_score(dice, scorecard, category_idx):
    score = calc_score(dice, category_idx)
    yacht_idx = CATS["Yacht"]
    yacht_bonus = 0
    if (
        calc_score(dice, yacht_idx) == 50
        and isinstance(scorecard[yacht_idx], (int, float))
        and scorecard[yacht_idx] >= 50
        and category_idx != yacht_idx
        and score > 0
    ):
        yacht_bonus = 100
        scorecard[yacht_idx] += yacht_bonus
    scorecard[category_idx] = score
    return score, yacht_bonus


def play_exact_turn(rng, scorecard, mode):
    dice = [rng.randint(1, 6) for _ in range(5)]
    initial_dice = list(dice)
    rolls_left = 2
    roll_trace = []

    while rolls_left > 0:
        open_categories = [idx for idx, value in enumerate(scorecard) if value is None]
        result = solve_best_move(dice, rolls_left, open_categories, mode, scorecard)
        keep_indices = list(result.get("keep_indices", []))
        roll_trace.append(
            {
                "dice": list(dice),
                "rolls_left": rolls_left,
                "keep_indices": keep_indices,
                "message": result.get("message"),
                "primary_target": result.get("primary_target"),
                "expected_value": result.get("expected_value"),
            }
        )
        if len(keep_indices) == 5:
            break
        dice = reroll_from_keep(rng, dice, keep_indices)
        rolls_left -= 1

    category_idx, score_result = choose_score_category(dice, scorecard, mode)
    score, yacht_bonus = apply_score(dice, scorecard, category_idx)
    return {
        "initial_dice": initial_dice,
        "final_dice": list(dice),
        "roll_trace": roll_trace,
        "category_idx": category_idx,
        "category_name": CATEGORY_NAMES[category_idx],
        "score": score,
        "yacht_bonus_awarded": yacht_bonus,
        "score_summary": score_result.get("summary"),
    }


def play_self_play_game(seed, mode="focused", initial_scorecard=None, clear_cache_every=0):
    rng = random.Random(seed)
    scorecard = list(initial_scorecard) if initial_scorecard is not None else [None] * 12
    samples = []
    turn_index = sum(1 for value in scorecard if value is not None)

    while any(value is None for value in scorecard):
        before_scorecard = list(scorecard)
        before_totals = scorecard_totals(before_scorecard)
        state = value_state_payload(before_scorecard, mode)
        turn = play_exact_turn(rng, scorecard, mode)
        after_totals = scorecard_totals(scorecard)
        samples.append(
            {
                "turn_index": turn_index,
                "seed": seed,
                "state": state,
                "turn": turn,
                "scorecard_after": list(scorecard),
                "turn_score_delta": after_totals["total_score"] - before_totals["total_score"],
            }
        )
        turn_index += 1
        if clear_cache_every and turn_index % clear_cache_every == 0:
            clear_solver_cache()

    final_totals = scorecard_totals(scorecard)
    final_score = final_totals["total_score"]
    for sample in samples:
        current_total = sample["state"]["current_total"]
        sample["target_final_score"] = final_score
        sample["target_remaining_score"] = final_score - current_total
        sample["target_upper_bonus"] = final_totals["upper_bonus"] > 0

    return {
        "seed": seed,
        "strategy_mode": mode,
        "final_score": final_score,
        "final_scorecard": list(scorecard),
        "final_totals": final_totals,
        "samples": samples,
    }


def percentile(values, ratio):
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    pos = max(0.0, min(1.0, float(ratio))) * (len(sorted_values) - 1)
    lower = int(pos)
    upper = min(len(sorted_values) - 1, lower + 1)
    weight = pos - lower
    return float(sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight)


def distribution_summary(values):
    if not values:
        return {
            "count": 0,
            "mean": 0.0,
            "stdev": 0.0,
            "min": 0.0,
            "p10": 0.0,
            "p25": 0.0,
            "p50": 0.0,
            "p75": 0.0,
            "p90": 0.0,
            "max": 0.0,
        }
    return {
        "count": len(values),
        "mean": round(statistics.fmean(values), 6),
        "stdev": round(statistics.pstdev(values), 6) if len(values) > 1 else 0.0,
        "min": min(values),
        "p10": round(percentile(values, 0.10), 6),
        "p25": round(percentile(values, 0.25), 6),
        "p50": round(percentile(values, 0.50), 6),
        "p75": round(percentile(values, 0.75), 6),
        "p90": round(percentile(values, 0.90), 6),
        "max": max(values),
    }


def simulate_state_distribution(scorecard, trials=64, seed=20260708, mode="focused", clear_cache_every=0):
    initial_scorecard = normalize_scorecard(scorecard)
    initial_totals = scorecard_totals(initial_scorecard)
    outcomes = []
    for trial_idx in range(max(0, int(trials))):
        trial_seed = int(seed) + trial_idx * 1009
        game = play_self_play_game(
            trial_seed,
            mode,
            initial_scorecard=initial_scorecard,
            clear_cache_every=clear_cache_every,
        )
        outcomes.append(
            {
                "trial": trial_idx,
                "seed": trial_seed,
                "final_score": game["final_score"],
                "remaining_score": game["final_score"] - initial_totals["total_score"],
                "upper_bonus": bool(game["final_totals"]["upper_bonus"]),
                "final_scorecard": game["final_scorecard"],
            }
        )

    final_scores = [row["final_score"] for row in outcomes]
    remaining_scores = [row["remaining_score"] for row in outcomes]
    return {
        "strategy_mode": mode,
        "seed": int(seed),
        "trials": len(outcomes),
        "initial_state": value_state_payload(initial_scorecard, mode),
        "initial_totals": initial_totals,
        "final_score": distribution_summary(final_scores),
        "remaining_score": distribution_summary(remaining_scores),
        "upper_bonus_rate": (
            round(statistics.fmean(1.0 if row["upper_bonus"] else 0.0 for row in outcomes), 6)
            if outcomes else 0.0
        ),
        "worst_outcomes": sorted(outcomes, key=lambda row: row["final_score"])[:5],
        "best_outcomes": sorted(outcomes, key=lambda row: row["final_score"], reverse=True)[:5],
    }
