#!/usr/bin/env python3
"""Reset game_data.json and repopulate it with simulated dummy data."""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yacht_engine
from yacht_ai.advice import score_stage_category_advice

CATEGORY_NAMES = list(yacht_engine.CATS.keys())
YACHT_IDX = yacht_engine.CATS["Yacht"]
DEFAULT_NAMES = [
    "Astra", "Blaze", "Comet", "Delta", "Echo", "Falcon", "Glint", "Harbor",
    "Iris", "Jolt", "Kite", "Lumen", "Miso", "Nova", "Orion", "Pixel",
    "Quartz", "Rin", "Sora", "Tango", "Uma", "Vega", "Willow", "Xeno",
    "Yuna", "Zeph", "다이스왕", "요트짱", "초코", "민트", "코코", "하늘",
    "노을", "별빛", "파도", "루나", "모카", "연두", "제트", "호두",
    "라임", "단비", "유자", "토리", "서리", "해솔", "가온", "나래",
]
SOLO_ONLY_NAMES = [
    "Ace", "Lucky", "Tempo", "Maverick", "Nori", "Bori", "Loki", "Cyan",
    "모험가", "집중러", "스트레이트", "풀하우스", "소다", "유니", "새벽", "윤슬",
]


@dataclass(frozen=True)
class PlayerProfile:
    username: str
    skill: float
    preferred_mode: str
    created_at: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset and seed the Yacht JSON database.")
    parser.add_argument("--output", default="game_data.json", help="target JSON DB path")
    parser.add_argument("--seed", type=int, default=20260417, help="random seed")
    parser.add_argument("--players", type=int, default=32, help="number of multiplayer users")
    parser.add_argument("--multiplayer-games", type=int, default=120, help="number of multiplayer match records")
    parser.add_argument("--single-simulations", type=int, default=72, help="number of simulated solo runs before ranking cut")
    parser.add_argument("--single-entries", type=int, default=20, help="number of single leaderboard rows to keep")
    parser.add_argument("--days", type=int, default=45, help="history window in days")
    return parser.parse_args()


def iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def build_player_pool(rng: random.Random, size: int, start_at: datetime) -> list[PlayerProfile]:
    names = DEFAULT_NAMES[:]
    while len(names) < size:
        names.append(f"Player{len(names) + 1:02d}")
    rng.shuffle(names)
    selected = names[:size]

    profiles: list[PlayerProfile] = []
    for username in selected:
        skill = min(0.98, max(0.72, rng.gauss(0.87, 0.07)))
        preferred_mode = "focused" if rng.random() < 0.55 else "cover"
        created_at = start_at - timedelta(days=rng.randint(8, 70), hours=rng.randint(0, 23))
        profiles.append(
            PlayerProfile(
                username=username,
                skill=round(skill, 3),
                preferred_mode=preferred_mode,
                created_at=iso(created_at),
            )
        )
    return profiles


def calc_totals(scorecard: list[int | None]) -> dict[str, int]:
    upper = sum(value or 0 for value in scorecard[:6])
    bonus = 35 if upper >= 63 else 0
    lower = sum(value or 0 for value in scorecard[6:])
    return {"upper": upper, "bonus": bonus, "total": upper + bonus + lower}


def choose_mode(profile: PlayerProfile, rng: random.Random) -> str:
    if rng.random() < 0.75:
        return profile.preferred_mode
    return "cover" if profile.preferred_mode == "focused" else "focused"


def apply_score(scorecard: list[int | None], dice: list[int], category_idx: int) -> tuple[int, int]:
    score = yacht_engine.calc_score(dice, category_idx)
    yacht_bonus = 0
    if (
        category_idx != YACHT_IDX
        and yacht_engine.calc_score(dice, YACHT_IDX) == 50
        and (scorecard[YACHT_IDX] or 0) >= 50
        and score > 0
    ):
        yacht_bonus = 100
        scorecard[YACHT_IDX] = (scorecard[YACHT_IDX] or 0) + yacht_bonus

    scorecard[category_idx] = score
    return score, yacht_bonus


def choose_category_rows(
    dice: list[int],
    scorecard: list[int | None],
    mode: str,
) -> list[dict]:
    open_categories = [idx for idx, value in enumerate(scorecard) if value is None]
    rows = [score_stage_category_advice(dice, scorecard, idx, mode) for idx in open_categories]
    rows.sort(key=lambda row: (row["utility"], row["score"], -row["category_idx"]), reverse=True)
    return rows


def choose_turn_candidate(
    scorecard: list[int | None],
    profile: PlayerProfile,
    rng: random.Random,
) -> tuple[list[int], int]:
    candidate_count = 2 + int(profile.skill >= 0.82) + int(profile.skill >= 0.9)
    candidates: list[tuple[tuple[float, int, int], list[int], int]] = []
    for _ in range(candidate_count):
        dice = [rng.randint(1, 6) for _ in range(5)]
        mode = choose_mode(profile, rng)
        rows = choose_category_rows(dice, scorecard, mode)
        if not rows:
            break
        best_row = rows[0]
        sort_key = (best_row["utility"], best_row["score"], -best_row["category_idx"])
        candidates.append((sort_key, dice, int(best_row["category_idx"])))

    if not candidates:
        raise RuntimeError("failed to sample a turn candidate")

    candidates.sort(key=lambda item: item[0], reverse=True)
    if rng.random() <= profile.skill or len(candidates) == 1:
        _, dice, category_idx = candidates[0]
        return dice, category_idx

    noisy_pool = candidates[: min(3, len(candidates))]
    _, dice, category_idx = rng.choice(noisy_pool)
    return dice, category_idx


def simulate_scorecard(profile: PlayerProfile, rng: random.Random) -> list[int | None]:
    scorecard: list[int | None] = [None] * len(CATEGORY_NAMES)
    for _ in range(len(CATEGORY_NAMES)):
        dice, category_idx = choose_turn_candidate(scorecard, profile, rng)
        apply_score(scorecard, dice, category_idx)
    return scorecard


def build_empty_user(profile: PlayerProfile) -> dict:
    return {
        "username": profile.username,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "total_score": 0,
        "games_played": 0,
        "created_at": profile.created_at,
    }


def update_user_stats(users: dict[str, dict], player1: str, score1: int, player2: str, score2: int) -> str:
    users[player1]["games_played"] += 1
    users[player1]["total_score"] += score1
    users[player2]["games_played"] += 1
    users[player2]["total_score"] += score2

    if score1 == score2:
        users[player1]["draws"] += 1
        users[player2]["draws"] += 1
        return "DRAW"
    if score1 > score2:
        users[player1]["wins"] += 1
        users[player2]["losses"] += 1
        return player1

    users[player1]["losses"] += 1
    users[player2]["wins"] += 1
    return player2


def choose_match_pair(profiles: list[PlayerProfile], rng: random.Random) -> tuple[PlayerProfile, PlayerProfile]:
    player1 = rng.choice(profiles)
    player2 = rng.choice(profiles)
    while player2.username == player1.username:
        player2 = rng.choice(profiles)
    return player1, player2


def seed_multiplayer_games(
    profiles: list[PlayerProfile],
    rng: random.Random,
    games_count: int,
    start_at: datetime,
    days: int,
) -> tuple[dict[str, dict], list[dict]]:
    users = {profile.username: build_empty_user(profile) for profile in profiles}
    games: list[dict] = []
    window_minutes = max(1, days * 24 * 60)

    for game_index in range(games_count):
        player1, player2 = choose_match_pair(profiles, rng)
        scorecard1 = simulate_scorecard(player1, rng)
        scorecard2 = simulate_scorecard(player2, rng)
        score1 = calc_totals(scorecard1)["total"]
        score2 = calc_totals(scorecard2)["total"]
        timestamp = start_at + timedelta(minutes=((game_index + 1) * window_minutes) / (games_count + 1))
        winner = update_user_stats(users, player1.username, score1, player2.username, score2)
        games.append({
            "player1": player1.username,
            "score1": score1,
            "player2": player2.username,
            "score2": score2,
            "winner": winner,
            "timestamp": iso(timestamp),
        })

    return users, games


def seed_single_leaderboard(
    profiles: list[PlayerProfile],
    rng: random.Random,
    simulations: int,
    entries: int,
    start_at: datetime,
    days: int,
) -> list[dict]:
    candidate_names = [profile.username for profile in profiles] + SOLO_ONLY_NAMES
    solo_entries: list[dict] = []
    for sim_index in range(simulations):
        username = rng.choice(candidate_names)
        temp_profile = PlayerProfile(
            username=username,
            skill=min(0.99, max(0.78, rng.gauss(0.9, 0.05))),
            preferred_mode="focused" if rng.random() < 0.6 else "cover",
            created_at=iso(start_at),
        )
        scorecard = simulate_scorecard(temp_profile, rng)
        score = calc_totals(scorecard)["total"]
        timestamp = start_at + timedelta(hours=((sim_index + 1) * max(1, days * 24)) / (simulations + 1))
        solo_entries.append({
            "username": username,
            "score": score,
            "timestamp": iso(timestamp),
        })

    solo_entries.sort(key=lambda entry: (entry["score"], entry["timestamp"]), reverse=True)
    return solo_entries[:entries]


def main() -> int:
    args = parse_args()
    rng = random.Random(args.seed)
    output_path = (ROOT / args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    start_at = now - timedelta(days=args.days)
    profiles = build_player_pool(rng, args.players, start_at)
    users, games = seed_multiplayer_games(profiles, rng, args.multiplayer_games, start_at, args.days)
    single_leaderboard = seed_single_leaderboard(
        profiles,
        rng,
        args.single_simulations,
        args.single_entries,
        start_at,
        args.days,
    )

    data = {
        "users": users,
        "games": games,
        "single_leaderboard": single_leaderboard,
    }

    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    sorted_users = sorted(users.values(), key=lambda row: (row["wins"], row["draws"], row["total_score"]), reverse=True)
    print(f"[seed-db] wrote {output_path}")
    print(f"[seed-db] users={len(users)} games={len(games)} single_leaderboard={len(single_leaderboard)}")
    if sorted_users:
        top = sorted_users[0]
        print(
            "[seed-db] top-multi "
            f"{top['username']} wins={top['wins']} draws={top['draws']} "
            f"losses={top['losses']} total_score={top['total_score']}"
        )
    if single_leaderboard:
        top_single = single_leaderboard[0]
        print(f"[seed-db] top-single {top_single['username']} score={top_single['score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
