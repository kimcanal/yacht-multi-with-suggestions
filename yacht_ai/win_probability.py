"""Monte Carlo win-probability estimation between two independent scorecards.

Two players never interact (no shared dice, no blocking), so their final
scores are independent random variables. Given each player's current
scorecard (and, for whoever is mid-turn, their in-progress dice/rolls_left),
this rolls each player forward to game completion under the exact EV-optimal
policy (`score_value_mode="value_optimal"`) many times and reports the
empirical win/loss/tie rate.

This assumes both players follow the EV-maximizing policy for the rest of
the game. That policy does not adapt to the score gap (a risk-seeking or
risk-averse policy conditioned on the margin would need a different,
target-dependent optimization) -- this module answers "who wins if both
sides play optimally from here," not "what should the losing side do
differently."
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import simulate_score_value_games as base_sim  # noqa: E402
import yacht_engine  # noqa: E402
from yacht_ai.constants import CATS  # noqa: E402
from yacht_ai.scoring import calc_score  # noqa: E402

_OPTIMAL_MODE = "focused"
_OPTIMAL_SCORE_VALUE_MODE = "value_optimal"


def _optimal_move(dice, rolls_left, scorecard, open_categories):
    return yacht_engine.solve_best_move(
        dice, rolls_left, open_categories, _OPTIMAL_MODE, scorecard,
        score_value_mode=_OPTIMAL_SCORE_VALUE_MODE,
    )


def _play_remaining_turns(seed, scorecard, dice, rolls_left, turn_index, random_source):
    scorecard = list(scorecard)
    rng = random.Random(seed)
    pending_dice = dice
    pending_rolls_left = rolls_left

    while any(value is None for value in scorecard):
        if pending_dice is None:
            cur_dice = base_sim.initial_dice(rng, seed, turn_index, random_source)
            cur_rolls_left = 2
        else:
            cur_dice = list(pending_dice)
            cur_rolls_left = pending_rolls_left
        pending_dice = None
        pending_rolls_left = None

        while cur_rolls_left > 0:
            open_categories = [i for i, value in enumerate(scorecard) if value is None]
            result = _optimal_move(cur_dice, cur_rolls_left, scorecard, open_categories)
            keep_indices = list(result.get("keep_indices", []))
            if len(keep_indices) == 5:
                break
            cur_dice = base_sim.reroll_from_keep(
                rng, cur_dice, keep_indices,
                seed=seed, turn_index=turn_index, roll_step=3 - cur_rolls_left,
                random_source=random_source,
            )
            cur_rolls_left -= 1

        open_categories = [i for i, value in enumerate(scorecard) if value is None]
        result = _optimal_move(cur_dice, 0, scorecard, open_categories)
        category_idx = CATS.get(result.get("primary_target"))
        if category_idx not in open_categories:
            category_idx = max(open_categories, key=lambda idx: calc_score(cur_dice, idx))
        base_sim.apply_score(cur_dice, scorecard, category_idx)
        turn_index += 1

    return base_sim.total_score(scorecard)


def estimate_win_probability(
    my_scorecard,
    opp_scorecard,
    my_dice=None,
    my_rolls_left=None,
    opp_dice=None,
    opp_rolls_left=None,
    samples=300,
    seed=None,
    random_source="indexed",
):
    """Estimate P(my final score > opponent's), assuming EV-optimal play from here.

    my_dice/my_rolls_left (and the opp_* equivalents) describe an in-progress
    turn for that player; leave both None if that player hasn't started their
    next turn yet.
    """
    if seed is None:
        seed = random.SystemRandom().randrange(1, 2**31)

    my_turn_index = sum(1 for value in my_scorecard if value is not None)
    opp_turn_index = sum(1 for value in opp_scorecard if value is not None)

    wins = losses = ties = 0
    my_finals = []
    opp_finals = []
    for i in range(max(1, int(samples))):
        my_final = _play_remaining_turns(
            seed + i * 2, my_scorecard, my_dice, my_rolls_left, my_turn_index, random_source,
        )
        opp_final = _play_remaining_turns(
            seed + i * 2 + 1, opp_scorecard, opp_dice, opp_rolls_left, opp_turn_index, random_source,
        )
        my_finals.append(my_final)
        opp_finals.append(opp_final)
        if my_final > opp_final:
            wins += 1
        elif my_final < opp_final:
            losses += 1
        else:
            ties += 1

    n = len(my_finals)
    win_rate = wins / n
    loss_rate = losses / n
    tie_rate = ties / n
    # binomial standard error on the win-rate estimate
    win_rate_stderr = (win_rate * (1 - win_rate) / n) ** 0.5

    return {
        "samples": n,
        "seed": seed,
        "win_rate": round(win_rate, 6),
        "loss_rate": round(loss_rate, 6),
        "tie_rate": round(tie_rate, 6),
        "win_rate_stderr": round(win_rate_stderr, 6),
        "my_avg_final": round(sum(my_finals) / n, 4),
        "opp_avg_final": round(sum(opp_finals) / n, 4),
    }
