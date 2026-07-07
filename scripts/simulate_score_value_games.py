#!/usr/bin/env python3
"""Compare heuristic and exact endgame value score-stage modes over full games."""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yacht_engine
from yacht_ai.constants import CATS
from yacht_ai.endgame_value import DEFAULT_ENDGAME_VALUE_TABLE_PATH
from yacht_ai.scoring import calc_score


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paired full-game simulations for score-stage value mode.")
    parser.add_argument("--games", type=int, default=200, help="paired games to run")
    parser.add_argument("--seed", type=int, default=20260708, help="base random seed")
    parser.add_argument("--mode", choices=("focused", "cover"), default="focused")
    parser.add_argument("--value-table", default=DEFAULT_ENDGAME_VALUE_TABLE_PATH)
    parser.add_argument("--learned-model", default="")
    parser.add_argument("--learned-max-mae", type=float, default=25.0)
    parser.add_argument("--learned-min-turns", type=int, default=5)
    parser.add_argument("--policies", default="heuristic,value", help="comma-separated score policies: heuristic,value,hybrid")
    parser.add_argument("--output", default="")
    parser.add_argument("--markdown-output", default="")
    parser.add_argument("--report-every", type=int, default=25)
    return parser.parse_args()


def total_score(scorecard: list[int | None]) -> int:
    upper = sum((value or 0) for value in scorecard[:6])
    lower = sum((value or 0) for value in scorecard[6:])
    return int(upper + lower + (35 if upper >= 63 else 0))


def score_metrics(scorecard: list[int | None]) -> dict:
    upper = sum((value or 0) for value in scorecard[:6])
    yacht_slot = scorecard[CATS["Yacht"]] or 0
    yacht_bonus_count = max(0, int((yacht_slot - 50) // 100)) if yacht_slot >= 50 else 0
    return {
        "total_score": total_score(scorecard),
        "upper_score": int(upper),
        "upper_bonus": int(upper >= 63),
        "yacht_score": int(yacht_slot),
        "yacht_bonus_count": yacht_bonus_count,
        "zero_categories": sum(1 for value in scorecard if value == 0),
        "scorecard": list(scorecard),
    }


def reroll_from_keep(rng: random.Random, dice: list[int], keep_indices: list[int]) -> list[int]:
    keep = set(keep_indices)
    return [value if idx in keep else rng.randint(1, 6) for idx, value in enumerate(dice)]


def solve_move(
    dice: list[int],
    rolls_left: int,
    scorecard: list[int | None],
    mode: str,
    score_mode: str,
    value_table: str,
    learned_model: str,
    learned_max_mae: float,
    learned_min_turns: int,
) -> dict:
    open_categories = [idx for idx, value in enumerate(scorecard) if value is None]
    if score_mode in ("value", "hybrid"):
        return yacht_engine.solve_best_move(
            dice,
            rolls_left,
            open_categories,
            mode,
            scorecard,
            score_value_mode=score_mode,
            endgame_value_table_path=value_table,
            learned_value_model_path=learned_model,
            learned_value_max_mae=learned_max_mae,
            learned_value_min_turns=learned_min_turns,
        )
    return yacht_engine.solve_best_move(dice, rolls_left, open_categories, mode, scorecard)


def choose_score_category(
    dice: list[int],
    scorecard: list[int | None],
    mode: str,
    score_mode: str,
    value_table: str,
    learned_model: str,
    learned_max_mae: float,
    learned_min_turns: int,
) -> tuple[int, dict]:
    open_categories = [idx for idx, value in enumerate(scorecard) if value is None]
    result = solve_move(dice, 0, scorecard, mode, score_mode, value_table, learned_model, learned_max_mae, learned_min_turns)
    category_idx = CATS.get(result.get("primary_target"))
    if category_idx in open_categories:
        return category_idx, result

    for row in result.get("breakdown", []):
        category_idx = CATS.get(row.get("name"))
        if category_idx in open_categories:
            return category_idx, result

    return max(open_categories, key=lambda idx: calc_score(dice, idx)), result


def apply_score(dice: list[int], scorecard: list[int | None], category_idx: int) -> None:
    score = calc_score(dice, category_idx)
    yacht_idx = CATS["Yacht"]
    if (
        calc_score(dice, yacht_idx) == 50
        and isinstance(scorecard[yacht_idx], (int, float))
        and scorecard[yacht_idx] >= 50
        and category_idx != yacht_idx
        and score > 0
    ):
        scorecard[yacht_idx] += 100
    scorecard[category_idx] = score


def play_game(
    seed: int,
    mode: str,
    score_mode: str,
    value_table: str,
    learned_model: str,
    learned_max_mae: float,
    learned_min_turns: int,
) -> dict:
    rng = random.Random(seed)
    scorecard: list[int | None] = [None] * 12
    score_decisions = []
    roll_decisions = 0
    value_score_hits = 0
    learned_value_score_hits = 0
    value_score_fallbacks = 0

    while any(value is None for value in scorecard):
        dice = [rng.randint(1, 6) for _ in range(5)]
        rolls_left = 2
        while rolls_left > 0:
            result = solve_move(
                dice,
                rolls_left,
                scorecard,
                mode,
                score_mode,
                value_table,
                learned_model,
                learned_max_mae,
                learned_min_turns,
            )
            keep_indices = list(result.get("keep_indices", []))
            roll_decisions += 1
            if len(keep_indices) == 5:
                break
            dice = reroll_from_keep(rng, dice, keep_indices)
            rolls_left -= 1

        category_idx, score_result = choose_score_category(
            dice,
            scorecard,
            mode,
            score_mode,
            value_table,
            learned_model,
            learned_max_mae,
            learned_min_turns,
        )
        row_names = {row.get("name") for row in score_result.get("breakdown", [])}
        if "Endgame V" in row_names:
            value_score_hits += 1
        elif "Learned V" in row_names:
            learned_value_score_hits += 1
        elif score_mode in ("value", "hybrid"):
            value_score_fallbacks += 1
        score_decisions.append({
            "turn": len(score_decisions) + 1,
            "dice": list(dice),
            "category": score_result.get("primary_target"),
            "category_idx": category_idx,
            "expected_value": score_result.get("expected_value"),
        })
        apply_score(dice, scorecard, category_idx)

    metrics = score_metrics(scorecard)
    metrics["roll_decisions"] = roll_decisions
    metrics["value_score_hits"] = value_score_hits
    metrics["learned_value_score_hits"] = learned_value_score_hits
    metrics["value_score_fallbacks"] = value_score_fallbacks
    metrics["score_decisions"] = score_decisions
    return metrics


def summarize(label: str, games: list[dict], baseline_games: list[dict] | None = None) -> dict:
    totals = [game["total_score"] for game in games]
    paired_delta = []
    if baseline_games is not None:
        paired_delta = [
            game["total_score"] - baseline["total_score"]
            for game, baseline in zip(games, baseline_games)
        ]
    return {
        "label": label,
        "games": len(games),
        "avg_total": round(statistics.fmean(totals), 4),
        "median_total": round(statistics.median(totals), 4),
        "stdev_total": round(statistics.pstdev(totals), 4),
        "min_total": min(totals),
        "max_total": max(totals),
        "avg_upper_score": round(statistics.fmean(game["upper_score"] for game in games), 4),
        "upper_bonus_rate": round(statistics.fmean(game["upper_bonus"] for game in games), 6),
        "avg_yacht_bonus_count": round(statistics.fmean(game["yacht_bonus_count"] for game in games), 6),
        "avg_zero_categories": round(statistics.fmean(game["zero_categories"] for game in games), 4),
        "avg_value_score_hits": round(statistics.fmean(game["value_score_hits"] for game in games), 4),
        "avg_learned_value_score_hits": round(statistics.fmean(game["learned_value_score_hits"] for game in games), 4),
        "avg_value_score_fallbacks": round(statistics.fmean(game["value_score_fallbacks"] for game in games), 4),
        "avg_delta_vs_heuristic": round(statistics.fmean(paired_delta), 4) if paired_delta else 0.0,
        "median_delta_vs_heuristic": round(statistics.median(paired_delta), 4) if paired_delta else 0.0,
        "min_delta_vs_heuristic": min(paired_delta) if paired_delta else 0,
        "max_delta_vs_heuristic": max(paired_delta) if paired_delta else 0,
        "win_rate_vs_heuristic": round(
            sum(1 for delta in paired_delta if delta > 0) / len(paired_delta),
            6,
        ) if paired_delta else 0.0,
        "loss_rate_vs_heuristic": round(
            sum(1 for delta in paired_delta if delta < 0) / len(paired_delta),
            6,
        ) if paired_delta else 0.0,
        "totals": totals,
        "paired_delta_vs_heuristic": paired_delta,
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Score Value Mode Full-game A/B",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Games: `{report['games']}` paired seeds",
        f"- Seed: `{report['seed']}`",
        f"- Value table: `{report['value_table']}`",
        f"- Learned model: `{report['learned_model'] or '-'}`",
        f"- Learned guard: validation MAE <= `{report['learned_max_mae']}`, next turns >= `{report['learned_min_turns']}`",
        "",
        "## Summary",
        "",
    ]
    for row in report["policies"]:
        lines.append(
            f"- {row['label']}: avg {row['avg_total']}, stdev {row['stdev_total']}, "
            f"upper bonus {row['upper_bonus_rate']}, yacht bonus avg {row['avg_yacht_bonus_count']}, "
            f"delta {row['avg_delta_vs_heuristic']:+.4f}"
        )
    for value_row in [row for row in report["policies"] if row["label"] != "heuristic"]:
        lines.extend([
            "",
            f"## {value_row['label']} Details",
            "",
            f"- Win/loss/tie vs heuristic: {value_row['win_rate_vs_heuristic']} / {value_row['loss_rate_vs_heuristic']} / "
            f"{round(1.0 - value_row['win_rate_vs_heuristic'] - value_row['loss_rate_vs_heuristic'], 6)}",
            f"- Avg score-stage exact table hits per game: {value_row['avg_value_score_hits']}",
            f"- Avg score-stage learned hits per game: {value_row['avg_learned_value_score_hits']}",
            f"- Avg score-stage fallback turns per game: {value_row['avg_value_score_fallbacks']}",
            f"- Delta range: {value_row['min_delta_vs_heuristic']} to {value_row['max_delta_vs_heuristic']}",
        ])
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    seeds = [args.seed + idx * 1009 for idx in range(args.games)]
    policies = [name.strip() for name in args.policies.split(",") if name.strip()]
    unknown = [name for name in policies if name not in ("heuristic", "value", "hybrid")]
    if unknown:
        raise SystemExit(f"unknown policies: {', '.join(unknown)}")
    if "heuristic" not in policies:
        raise SystemExit("--policies must include heuristic as the baseline")
    raw_results = {}
    summaries = []

    for label in policies:
        games = []
        for idx, seed in enumerate(seeds, start=1):
            games.append(
                play_game(
                    seed,
                    args.mode,
                    label,
                    args.value_table,
                    args.learned_model,
                    args.learned_max_mae,
                    args.learned_min_turns,
                )
            )
            if args.report_every and (idx % args.report_every == 0 or idx == args.games):
                print(f"[score-value-sim] policy={label} games={idx}/{args.games}")
        raw_results[label] = games
        baseline = raw_results.get("heuristic") if label != "heuristic" else None
        summaries.append(summarize(label, games, baseline))

    report = {
        "mode": args.mode,
        "games": args.games,
        "seed": args.seed,
        "value_table": args.value_table,
        "learned_model": args.learned_model,
        "learned_max_mae": args.learned_max_mae,
        "learned_min_turns": args.learned_min_turns,
        "policies": summaries,
    }
    print("[score-value-sim] summary")
    for row in summaries:
        print(
            f"- {row['label']}: avg={row['avg_total']:.2f} "
            f"delta={row['avg_delta_vs_heuristic']:+.2f} "
            f"upper_bonus={row['upper_bonus_rate']:.3f}"
        )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[score-value-sim] wrote JSON report to {output_path}")

    if args.markdown_output:
        markdown_path = Path(args.markdown_output)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(report), encoding="utf-8")
        print(f"[score-value-sim] wrote Markdown report to {markdown_path}")


if __name__ == "__main__":
    main()
