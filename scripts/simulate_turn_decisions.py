#!/usr/bin/env python3
import argparse
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yacht_engine
from yacht_ai.scoring import get_keep_options, kept_tuple_to_indices


def sample_next_dice(dice, keep_idx):
    out = dice[:]
    for i in range(5):
        if i not in keep_idx:
            out[i] = random.randint(1, 6)
    return out


def estimate_keep_ev(dice, keep_idx, rolls_left, scorecard, mode, trials):
    if rolls_left <= 0:
        open_c = [i for i, v in enumerate(scorecard) if v is None]
        res = yacht_engine.solve_best_move(dice, 0, open_c, mode, scorecard)
        return float(res.get("expected_value", 0.0))

    vals = []
    for _ in range(trials):
        nxt = sample_next_dice(dice, keep_idx)
        open_c = [i for i, v in enumerate(scorecard) if v is None]
        res = yacht_engine.solve_best_move(nxt, rolls_left - 1, open_c, mode, scorecard)
        vals.append(float(res.get("expected_value", 0.0)))
    return statistics.fmean(vals)


def run_case(name, dice, rolls_left, mode, scorecard, trials):
    dice_tuple = tuple(sorted(dice))
    keep_tuples = get_keep_options(dice_tuple)
    rows = []
    for kt in keep_tuples:
        keep_idx = kept_tuple_to_indices(dice, kt)
        ev = estimate_keep_ev(dice, keep_idx, rolls_left, scorecard, mode, trials)
        rows.append((ev, keep_idx, kt))
    rows.sort(reverse=True, key=lambda x: x[0])

    open_c = [i for i, v in enumerate(scorecard) if v is None]
    ai = yacht_engine.solve_best_move(dice, rolls_left, open_c, mode, scorecard)
    print(f"\n[{name}] dice={dice} rolls_left={rolls_left} mode={mode}")
    print("AI choice:", ai.get("keep_indices"), ai.get("message"))
    for ev, keep_idx, kt in rows[:5]:
        print(f"  EV={ev:6.2f} keep={keep_idx} values={list(kt)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=1200)
    args = ap.parse_args()

    random.seed(20260521)
    empty = [None] * 12
    upper_pushed = [3, 6, 9, 12, 15, None, None, None, None, None, None, None]

    run_case("ones_triplet_open", [1, 1, 1, 4, 6], 2, "focused", empty, args.trials)
    run_case("small_to_large_upgrade", [2, 3, 4, 5, 5], 1, "focused", empty, args.trials)
    run_case("upper_bonus_pressure", [1, 1, 1, 4, 6], 2, "focused", upper_pushed, args.trials)
