#!/usr/bin/env python3
"""Measure per-decision EV regret of recommendation policies against exact optimal play.

Every roll/score decision a policy makes is re-evaluated with the full-game exact
value table: regret = Q*(best action) - Q*(chosen action). This gives a
policy-quality metric in points that does not depend on dice luck.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import simulate_score_value_games as base_sim
import yacht_engine
from yacht_ai.constants import CATS, CATEGORY_NAMES
from yacht_ai.endgame_value import DEFAULT_ENDGAME_VALUE_TABLE_PATH, load_endgame_value_table
from yacht_ai.scoring import calc_score, get_keep_options, get_transition_distribution

MATCH_EPS = 1e-6
YACHT_IDX = CATS["Yacht"]

POLICY_SPECS = {
    "focused": {"mode": "focused", "score_mode": "heuristic"},
    "cover": {"mode": "cover", "score_mode": "heuristic"},
    "value_score_only": {"mode": "focused", "score_mode": "value_score_only"},
    "optimal": {"mode": "focused", "score_mode": "value_optimal"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate per-decision EV regret vs exact optimal play.")
    parser.add_argument("--games", type=int, default=100, help="games per policy")
    parser.add_argument("--seed", type=int, default=20260709, help="base random seed")
    parser.add_argument(
        "--policies",
        default="focused,cover,optimal",
        help=f"comma-separated policies: {', '.join(POLICY_SPECS)}",
    )
    parser.add_argument("--value-table", default=DEFAULT_ENDGAME_VALUE_TABLE_PATH)
    parser.add_argument("--random-source", choices=("stream", "indexed"), default="indexed")
    parser.add_argument("--top-cases", type=int, default=8, help="worst decisions to keep per policy")
    parser.add_argument("--output", default="")
    parser.add_argument("--markdown-output", default="")
    parser.add_argument("--report-every", type=int, default=10)
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Exact Q evaluation against the full-game value table
# ---------------------------------------------------------------------------

class ExactEvaluator:
    """Q* values for any decision, using the open12 exact value table."""

    def __init__(self, value_table):
        self.table = value_table

    def state_value(self, scorecard_tuple) -> float:
        if all(value is not None for value in scorecard_tuple):
            return 0.0
        value, key = self.table.lookup_scorecard(scorecard_tuple)
        if value is None:
            raise RuntimeError(f"value table has no entry for state {key}; use the open12 table")
        return value

    def immediate_gain(self, dice_tuple, scorecard_tuple, category_idx) -> float:
        score = calc_score(list(dice_tuple), category_idx)
        gain = float(score)
        if category_idx < 6:
            upper = sum((value or 0) for value in scorecard_tuple[:6])
            if upper < 63 <= upper + score:
                gain += 35.0
        yacht_value = scorecard_tuple[YACHT_IDX]
        if (
            category_idx != YACHT_IDX
            and score > 0
            and isinstance(yacht_value, (int, float))
            and yacht_value >= 50
            and calc_score(list(dice_tuple), YACHT_IDX) == 50
        ):
            gain += 100.0
        return gain

    def score_q_values(self, dice_tuple, scorecard_tuple) -> dict[int, float]:
        """Q*(record category) for every open category."""
        q_values = {}
        for category_idx, value in enumerate(scorecard_tuple):
            if value is not None:
                continue
            next_scorecard = list(scorecard_tuple)
            next_scorecard[category_idx] = calc_score(list(dice_tuple), category_idx)
            q_values[category_idx] = (
                self.immediate_gain(dice_tuple, scorecard_tuple, category_idx)
                + self.state_value(tuple(next_scorecard))
            )
        return q_values

    def make_turn_solver(self, scorecard_tuple):
        """Per-turn DP: W(dice, rerolls) assuming optimal play from here on."""

        @lru_cache(maxsize=None)
        def stop_value(dice_tuple) -> float:
            return max(self.score_q_values(dice_tuple, scorecard_tuple).values())

        @lru_cache(maxsize=None)
        def turn_value(dice_tuple, rerolls) -> float:
            best = stop_value(dice_tuple)
            if rerolls == 0:
                return best
            for kept_tuple in get_keep_options(dice_tuple):
                value = keep_q(dice_tuple, kept_tuple, rerolls)
                if value > best:
                    best = value
            return best

        @lru_cache(maxsize=None)
        def keep_q(dice_tuple, kept_tuple, rerolls) -> float:
            return sum(
                prob * turn_value(next_dice, rerolls - 1)
                for next_dice, prob in get_transition_distribution(kept_tuple)
            )

        return stop_value, keep_q


# ---------------------------------------------------------------------------
# Game playthrough with per-decision regret accounting
# ---------------------------------------------------------------------------

def _keep_tuple_from_indices(dice, keep_indices):
    return tuple(sorted(dice[idx] for idx in keep_indices))


def _keep_label(kept_tuple) -> str:
    if len(kept_tuple) == 5:
        return "지금 기록"
    if not kept_tuple:
        return "모두 굴리기"
    return "[" + ", ".join(str(value) for value in sorted(kept_tuple)) + "] Keep"


def _optimal_roll_actions(q_stop, q_keeps, q_best):
    actions = []
    if abs(q_stop - q_best) <= MATCH_EPS:
        actions.append({"type": "score_now", "label": "지금 기록", "value": round(q_stop, 4)})
    for kept_tuple, value in sorted(q_keeps.items(), key=lambda item: (item[1], len(item[0]), item[0]), reverse=True):
        if abs(value - q_best) <= MATCH_EPS:
            actions.append({"type": "keep", "label": _keep_label(kept_tuple), "value": round(value, 4)})
    return actions


def _optimal_score_actions(q_values, q_best):
    return [
        {"category_idx": idx, "label": CATEGORY_NAMES[idx], "value": round(value, 4)}
        for idx, value in sorted(q_values.items(), key=lambda item: (item[1], -item[0]), reverse=True)
        if abs(value - q_best) <= MATCH_EPS
    ]


def play_game_with_regret(seed, policy_label, spec, value_table_path, evaluator, random_source):
    rng = random.Random(seed)
    scorecard: list[int | None] = [None] * 12
    decisions = []

    turn_index = 0
    while any(value is None for value in scorecard):
        dice = base_sim.initial_dice(rng, seed, turn_index, random_source)
        scorecard_tuple = tuple(scorecard)
        stop_value, keep_q = evaluator.make_turn_solver(scorecard_tuple)
        rolls_left = 2

        while rolls_left > 0:
            dice_tuple = tuple(sorted(dice))
            roll_score_mode = "heuristic" if spec["score_mode"] == "value_score_only" else spec["score_mode"]
            result = base_sim.solve_move(
                dice, rolls_left, scorecard, spec["mode"], roll_score_mode,
                value_table_path, "", 25.0, 5,
            )
            keep_indices = list(result.get("keep_indices", []))

            q_stop = stop_value(dice_tuple)
            keep_options = list(get_keep_options(dice_tuple))
            q_keeps = {kt: keep_q(dice_tuple, kt, rolls_left) for kt in keep_options}
            q_best = max(q_stop, max(q_keeps.values()))
            if len(keep_indices) == 5:
                q_chosen = q_stop
                chosen_label = "지금 기록"
            else:
                chosen_tuple = _keep_tuple_from_indices(dice, keep_indices)
                q_chosen = q_keeps[chosen_tuple]
                chosen_label = _keep_label(chosen_tuple)

            decisions.append({
                "stage": "roll",
                "turn": turn_index + 1,
                "rolls_left": rolls_left,
                "dice": list(dice),
                "scorecard": list(scorecard),
                "chosen": sorted(dice[idx] for idx in keep_indices),
                "chosen_label": chosen_label,
                "chosen_value": round(q_chosen, 4),
                "best_value": round(q_best, 4),
                "optimal_actions": _optimal_roll_actions(q_stop, q_keeps, q_best),
                "regret": max(0.0, q_best - q_chosen),
            })

            if len(keep_indices) == 5:
                break
            dice = base_sim.reroll_from_keep(
                rng, dice, keep_indices,
                seed=seed, turn_index=turn_index, roll_step=3 - rolls_left,
                random_source=random_source,
            )
            rolls_left -= 1

        category_idx, _ = base_sim.choose_score_category(
            dice, scorecard, spec["mode"], spec["score_mode"],
            value_table_path, "", 25.0, 5,
        )
        dice_tuple = tuple(sorted(dice))
        q_cats = evaluator.score_q_values(dice_tuple, scorecard_tuple)
        q_best = max(q_cats.values())
        q_chosen = q_cats[category_idx]
        decisions.append({
            "stage": "score",
            "turn": turn_index + 1,
            "rolls_left": 0,
            "dice": list(dice),
            "scorecard": list(scorecard),
            "chosen": category_idx,
            "chosen_label": CATEGORY_NAMES[category_idx],
            "chosen_value": round(q_chosen, 4),
            "best_value": round(q_best, 4),
            "optimal_actions": _optimal_score_actions(q_cats, q_best),
            "regret": max(0.0, q_best - q_chosen),
        })

        base_sim.apply_score(dice, scorecard, category_idx)
        turn_index += 1

    return {
        "seed": seed,
        "policy": policy_label,
        "total_score": base_sim.total_score(scorecard),
        "scorecard": list(scorecard),
        "decisions": decisions,
        "game_regret": round(sum(row["regret"] for row in decisions), 4),
    }


# ---------------------------------------------------------------------------
# Aggregation / reporting
# ---------------------------------------------------------------------------

def summarize_policy(label, games, top_cases):
    all_decisions = [row for game in games for row in game["decisions"]]
    roll_rows = [row for row in all_decisions if row["stage"] == "roll"]
    score_rows = [row for row in all_decisions if row["stage"] == "score"]

    def _bucket(rows):
        regrets = [row["regret"] for row in rows]
        mistakes = [regret for regret in regrets if regret > MATCH_EPS]
        return {
            "decisions": len(rows),
            "avg_regret": round(statistics.fmean(regrets), 4) if regrets else 0.0,
            "match_rate": round(1.0 - len(mistakes) / len(rows), 4) if rows else 1.0,
            "avg_mistake_size": round(statistics.fmean(mistakes), 4) if mistakes else 0.0,
            "max_regret": round(max(regrets), 4) if regrets else 0.0,
        }

    per_turn = {}
    for row in all_decisions:
        per_turn.setdefault(row["turn"], []).append(row["regret"])
    regret_by_turn = {
        str(turn): round(statistics.fmean(values), 4) for turn, values in sorted(per_turn.items())
    }

    worst = sorted(all_decisions, key=lambda row: row["regret"], reverse=True)[: max(0, top_cases)]
    return {
        "label": label,
        "games": len(games),
        "avg_total_score": round(statistics.fmean(game["total_score"] for game in games), 4),
        "avg_game_regret": round(statistics.fmean(game["game_regret"] for game in games), 4),
        "median_game_regret": round(statistics.median(game["game_regret"] for game in games), 4),
        "roll": _bucket(roll_rows),
        "score": _bucket(score_rows),
        "regret_by_turn": regret_by_turn,
        "worst_decisions": [
            {
                "stage": row["stage"],
                "turn": row["turn"],
                "rolls_left": row["rolls_left"],
                "dice": row["dice"],
                "scorecard": row["scorecard"],
                "chosen": row["chosen"],
                "chosen_label": row.get("chosen_label"),
                "chosen_value": row.get("chosen_value"),
                "best_value": row.get("best_value"),
                "optimal_actions": row.get("optimal_actions", []),
                "regret": round(row["regret"], 4),
            }
            for row in worst
        ],
    }


def render_markdown(report) -> str:
    lines = [
        "# AI Decision Regret vs Exact Optimal",
        "",
        f"- Games per policy: `{report['games']}`",
        f"- Seed: `{report['seed']}` / random source: `{report['random_source']}`",
        f"- Value table: `{report['value_table']}`",
        f"- Metric: regret = Q*(best action) - Q*(chosen action), in expected final-score points",
        "",
        "## Summary",
        "",
        "| policy | avg score | avg regret/game | roll match | score match | roll avg regret | score avg regret |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in report["policies"]:
        lines.append(
            f"| {row['label']} | {row['avg_total_score']} | {row['avg_game_regret']} "
            f"| {row['roll']['match_rate']} | {row['score']['match_rate']} "
            f"| {row['roll']['avg_regret']} | {row['score']['avg_regret']} |"
        )
    for row in report["policies"]:
        lines.extend([
            "",
            f"## {row['label']}",
            "",
            f"- Avg regret per game: {row['avg_game_regret']} (median {row['median_game_regret']})",
            f"- Roll decisions: {row['roll']['decisions']}, match {row['roll']['match_rate']}, "
            f"avg mistake size {row['roll']['avg_mistake_size']}, max {row['roll']['max_regret']}",
            f"- Score decisions: {row['score']['decisions']}, match {row['score']['match_rate']}, "
            f"avg mistake size {row['score']['avg_mistake_size']}, max {row['score']['max_regret']}",
            f"- Regret by turn: {row['regret_by_turn']}",
            "",
            "### Worst Decisions",
            "",
        ])
        for case in row["worst_decisions"][:5]:
            optimal = ", ".join(action["label"] for action in case.get("optimal_actions", [])[:3])
            if optimal:
                optimal = f", optimal `{optimal}`"
            lines.append(
                f"- turn {case['turn']} {case['stage']} (rolls_left {case['rolls_left']}): "
                f"dice {case['dice']}, chosen `{case.get('chosen_label') or case['chosen']}`{optimal}, "
                f"regret {case['regret']}, "
                f"scorecard `{case['scorecard']}`"
            )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    policies = [name.strip() for name in args.policies.split(",") if name.strip()]
    unknown = [name for name in policies if name not in POLICY_SPECS]
    if unknown:
        raise SystemExit(f"unknown policies: {', '.join(unknown)}")

    value_table = load_endgame_value_table(args.value_table)
    evaluator = ExactEvaluator(value_table)
    seeds = [args.seed + idx * 1009 for idx in range(args.games)]

    summaries = []
    for label in policies:
        spec = POLICY_SPECS[label]
        games = []
        for idx, seed in enumerate(seeds, start=1):
            games.append(
                play_game_with_regret(seed, label, spec, args.value_table, evaluator, args.random_source)
            )
            if args.report_every and (idx % args.report_every == 0 or idx == args.games):
                print(f"[decision-regret] policy={label} games={idx}/{args.games}")
        summaries.append(summarize_policy(label, games, args.top_cases))

    report = {
        "games": args.games,
        "seed": args.seed,
        "random_source": args.random_source,
        "value_table": args.value_table,
        "policies": summaries,
    }

    print("[decision-regret] summary")
    for row in summaries:
        print(
            f"- {row['label']}: avg_score={row['avg_total_score']:.2f} "
            f"regret/game={row['avg_game_regret']:.2f} "
            f"roll_match={row['roll']['match_rate']:.3f} score_match={row['score']['match_rate']:.3f}"
        )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[decision-regret] wrote JSON report to {output_path}")

    if args.markdown_output:
        markdown_path = Path(args.markdown_output)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(report), encoding="utf-8")
        print(f"[decision-regret] wrote Markdown report to {markdown_path}")


if __name__ == "__main__":
    main()
