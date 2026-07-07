import random

from .constants import CATS, CATEGORY_NAMES
from .scoring import calc_score
from .solver import clear_solver_cache, solve_best_move
from .value_model import scorecard_totals, value_state_payload


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
