#!/usr/bin/env python3
"""HTTP soak for multiplayer bot-vs-bot rooms with a spectator client."""

from __future__ import annotations

import argparse
import math
import random
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yacht_engine
from yacht_ai.advice import score_stage_category_advice

CATEGORY_NAMES = list(yacht_engine.CATS.keys())
CATEGORY_SET = set(CATEGORY_NAMES)
YACHT_IDX = yacht_engine.CATS["Yacht"]


@dataclass
class PlayerState:
    username: str
    token: str
    mode: str
    scorecard: list[int | None] = field(default_factory=lambda: [None] * 12)


@dataclass
class MatchState:
    turn: str
    dice: list[int] = field(default_factory=lambda: [1] * 5)
    kept: list[int] = field(default_factory=lambda: [0] * 5)
    rolls_left: int = 3
    game_over: bool = False
    winner: str | None = None
    loser: str | None = None
    end_reason: str | None = None
    ai_rec: dict[str, Any] | None = None


@dataclass
class SoakStats:
    games: int = 0
    turns: int = 0
    rolls: int = 0
    syncs: int = 0
    recommends: int = 0
    heartbeats: int = 0
    observer_polls: int = 0
    unchanged_hits: int = 0
    categories_written: int = 0
    recommend_ms: list[float] = field(default_factory=list)
    roll_ms: list[float] = field(default_factory=list)
    sync_ms: list[float] = field(default_factory=list)
    get_ms: list[float] = field(default_factory=list)
    heartbeat_ms: list[float] = field(default_factory=list)


class SoakFailure(RuntimeError):
    pass


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    idx = min(len(sorted_values) - 1, max(0, math.ceil(len(sorted_values) * ratio) - 1))
    return sorted_values[idx]


def summarize_ms(values: list[float]) -> str:
    if not values:
        return "n=0"
    return (
        f"n={len(values)} avg={statistics.mean(values):.2f}ms "
        f"p95={percentile(values, 0.95):.2f}ms max={max(values):.2f}ms"
    )


def api_request(
    session: requests.Session,
    method: str,
    base_url: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout_s: float = 20.0,
) -> tuple[dict[str, Any], float]:
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    started = time.perf_counter()
    response = session.request(method, url, json=json_body, params=params, timeout=timeout_s)
    elapsed_ms = (time.perf_counter() - started) * 1000
    try:
        payload = response.json()
    except ValueError as exc:
        raise SoakFailure(f"{method} {path} returned non-JSON status={response.status_code}") from exc
    if not response.ok:
        raise SoakFailure(f"{method} {path} failed status={response.status_code} payload={payload}")
    if not isinstance(payload, dict):
        raise SoakFailure(f"{method} {path} returned unexpected payload type {type(payload)!r}")
    return payload, elapsed_ms


def calc_totals(card: list[int | None]) -> dict[str, int]:
    upper = sum(value or 0 for value in card[:6])
    bonus = 35 if upper >= 63 else 0
    lower = sum(value or 0 for value in card[6:])
    return {"upper": upper, "bonus": bonus, "total": upper + bonus + lower}


def build_scores_payload(host: PlayerState, guest: PlayerState) -> dict[str, list[int | None]]:
    return {
        host.username: host.scorecard[:],
        guest.username: guest.scorecard[:],
    }


def keep_indices_to_mask(keep_indices: list[int]) -> list[int]:
    keep_set = set(keep_indices)
    return [1 if idx in keep_set else 0 for idx in range(5)]


def should_stop_roll(recommendation: dict[str, Any]) -> bool:
    keep_indices = recommendation.get("keep_indices") or []
    message = str(recommendation.get("message") or "")
    return len(keep_indices) == 5 or message.startswith("지금 기록 추천")


def choose_category(
    recommendation: dict[str, Any],
    dice: list[int],
    scorecard: list[int | None],
    mode: str,
) -> int:
    candidates: list[str] = []
    primary = recommendation.get("primary_target")
    if isinstance(primary, str):
        candidates.append(primary)
    for row in recommendation.get("breakdown") or []:
        if isinstance(row, dict) and isinstance(row.get("name"), str):
            candidates.append(row["name"])

    for name in candidates:
        if name in CATEGORY_SET:
            idx = yacht_engine.CATS[name]
            if scorecard[idx] is None:
                return idx

    open_categories = [idx for idx, value in enumerate(scorecard) if value is None]
    rows = [score_stage_category_advice(dice, scorecard, idx, mode) for idx in open_categories]
    if not rows:
        raise SoakFailure("no open categories left while choosing score category")
    best_row = max(rows, key=lambda row: (row["utility"], row["score"], -row["category_idx"]))
    return int(best_row["category_idx"])


def apply_score(scorecard: list[int | None], dice: list[int], category_idx: int) -> tuple[int, int]:
    if scorecard[category_idx] is not None:
        raise SoakFailure(f"category already filled: {CATEGORY_NAMES[category_idx]}")

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


def assert_room_snapshot(
    payload: dict[str, Any],
    code: str,
    observer_name: str,
    host: PlayerState,
    guest: PlayerState,
    match: MatchState,
) -> int:
    if payload.get("code") != code:
        raise SoakFailure(f"observer room code mismatch: expected {code}, got {payload.get('code')}")
    players = payload.get("players") or []
    if players != [host.username, guest.username]:
        raise SoakFailure(f"observer players mismatch: {players}")
    observers = payload.get("observers") or []
    if observer_name not in observers:
        raise SoakFailure(f"observer missing from room payload: {observers}")
    if int(payload.get("observer_count") or 0) < 1:
        raise SoakFailure(f"observer_count unexpectedly low: {payload.get('observer_count')}")

    state = payload.get("state") or {}
    if not isinstance(state, dict):
        raise SoakFailure("room state payload is not a dict")
    version = state.get("version")
    if not isinstance(version, int):
        raise SoakFailure(f"state.version missing or invalid: {version!r}")

    if not payload.get("unchanged"):
        expected_scores = build_scores_payload(host, guest)
        if state.get("scores") != expected_scores:
            raise SoakFailure("observer scores diverged from local bot state")
        if state.get("turn") != match.turn:
            raise SoakFailure(f"observer turn mismatch: expected {match.turn}, got {state.get('turn')}")
        if bool(state.get("game_over")) != match.game_over:
            raise SoakFailure("observer game_over mismatch")
        if state.get("dice") != match.dice:
            raise SoakFailure(f"observer dice mismatch: expected {match.dice}, got {state.get('dice')}")
        if state.get("kept") != match.kept:
            raise SoakFailure(f"observer kept mismatch: expected {match.kept}, got {state.get('kept')}")
        if int(state.get("rolls_left")) != match.rolls_left:
            raise SoakFailure(
                f"observer rolls_left mismatch: expected {match.rolls_left}, got {state.get('rolls_left')}"
            )

    return version


def observer_poll(
    session: requests.Session,
    base_url: str,
    code: str,
    observer_name: str,
    host: PlayerState,
    guest: PlayerState,
    match: MatchState,
    stats: SoakStats,
    known_version: int | None,
) -> int:
    params: dict[str, Any] = {"u": observer_name}
    if known_version is not None:
        params["sv"] = known_version
    payload, elapsed_ms = api_request(session, "GET", base_url, f"/api/rooms/{code}", params=params)
    stats.get_ms.append(elapsed_ms)
    stats.observer_polls += 1
    if payload.get("unchanged"):
        if known_version is None:
            raise SoakFailure("observer returned unchanged before any known version was recorded")
        version = assert_room_snapshot(payload, code, observer_name, host, guest, match)
        if version != known_version:
            raise SoakFailure("unchanged response carried a different version")
        stats.unchanged_hits += 1
        return version

    version = assert_room_snapshot(payload, code, observer_name, host, guest, match)

    unchanged_payload, unchanged_ms = api_request(
        session,
        "GET",
        base_url,
        f"/api/rooms/{code}",
        params={"u": observer_name, "sv": version},
    )
    stats.get_ms.append(unchanged_ms)
    stats.observer_polls += 1
    if not unchanged_payload.get("unchanged"):
        raise SoakFailure("expected unchanged room payload on immediate observer re-poll")
    unchanged_version = assert_room_snapshot(unchanged_payload, code, observer_name, host, guest, match)
    if unchanged_version != version:
        raise SoakFailure("observer version changed during immediate unchanged re-poll")
    stats.unchanged_hits += 1
    return version


def heartbeat_client(
    session: requests.Session,
    base_url: str,
    code: str,
    username: str,
    token: str | None,
    stats: SoakStats,
) -> None:
    payload = {"username": username}
    if token:
        payload["player_token"] = token
    _, elapsed_ms = api_request(session, "POST", base_url, f"/api/rooms/{code}/heartbeat", json_body=payload)
    stats.heartbeat_ms.append(elapsed_ms)
    stats.heartbeats += 1


def request_recommendation(
    session: requests.Session,
    base_url: str,
    dice: list[int],
    rolls_left: int,
    scorecard: list[int | None],
    mode: str,
    stats: SoakStats,
) -> dict[str, Any]:
    payload, elapsed_ms = api_request(
        session,
        "POST",
        base_url,
        "/api/recommend",
        json_body={
            "dice": dice,
            "rolls_left": rolls_left,
            "scorecard": scorecard,
            "strategy_mode": mode,
        },
    )
    stats.recommend_ms.append(elapsed_ms)
    stats.recommends += 1
    return payload


def perform_roll(
    session: requests.Session,
    base_url: str,
    code: str,
    player: PlayerState,
    kept: list[int],
    stats: SoakStats,
) -> tuple[list[int], int]:
    payload, elapsed_ms = api_request(
        session,
        "POST",
        base_url,
        f"/api/rooms/{code}/roll",
        json_body={"username": player.username, "player_token": player.token, "kept": kept},
    )
    stats.roll_ms.append(elapsed_ms)
    stats.rolls += 1
    dice = payload.get("dice")
    rolls_left = payload.get("rolls_left")
    if not isinstance(dice, list) or len(dice) != 5:
        raise SoakFailure(f"roll returned invalid dice: {dice!r}")
    if not isinstance(rolls_left, int):
        raise SoakFailure(f"roll returned invalid rolls_left: {rolls_left!r}")
    return [int(value) for value in dice], rolls_left


def sync_state(
    session: requests.Session,
    base_url: str,
    code: str,
    player: PlayerState,
    host: PlayerState,
    guest: PlayerState,
    match: MatchState,
    stats: SoakStats,
) -> None:
    payload, elapsed_ms = api_request(
        session,
        "POST",
        base_url,
        f"/api/rooms/{code}/sync",
        json_body={
            "username": player.username,
            "player_token": player.token,
            "dice": match.dice,
            "kept": match.kept,
            "rolls_left": match.rolls_left,
            "scores": build_scores_payload(host, guest),
            "turn": match.turn,
            "game_over": match.game_over,
            "ai_rec": match.ai_rec,
            "winner": match.winner,
            "loser": match.loser,
            "end_reason": match.end_reason,
        },
    )
    stats.sync_ms.append(elapsed_ms)
    stats.syncs += 1
    state = payload.get("state") or {}
    if state.get("scores") != build_scores_payload(host, guest):
        raise SoakFailure("sync response scores did not round-trip")


def player_done(player: PlayerState) -> bool:
    return all(value is not None for value in player.scorecard)


def current_and_other_player(
    host: PlayerState,
    guest: PlayerState,
    turn_username: str,
) -> tuple[PlayerState, PlayerState]:
    if turn_username == host.username:
        return host, guest
    if turn_username == guest.username:
        return guest, host
    raise SoakFailure(f"unknown turn owner {turn_username!r}")


def run_single_game(
    session: requests.Session,
    base_url: str,
    game_index: int,
    host_mode: str,
    guest_mode: str,
    observer_poll_every: int,
    stats: SoakStats,
) -> dict[str, Any]:
    host_name = f"H{game_index:04d}"
    guest_name = f"G{game_index:04d}"
    observer_name = f"S{game_index:04d}"

    create_payload, _ = api_request(session, "POST", base_url, "/api/rooms", json_body={"username": host_name})
    code = str(create_payload["code"])
    host = PlayerState(host_name, str(create_payload["player_token"]), host_mode)

    join_payload, _ = api_request(
        session,
        "POST",
        base_url,
        f"/api/rooms/{code}/join",
        json_body={"username": guest_name},
    )
    guest = PlayerState(guest_name, str(join_payload["player_token"]), guest_mode)

    _, _ = api_request(
        session,
        "POST",
        base_url,
        f"/api/rooms/{code}/observe",
        json_body={"username": observer_name},
    )

    match = MatchState(turn=host.username)
    known_version = observer_poll(session, base_url, code, observer_name, host, guest, match, stats, None)
    action_counter = 0

    while not match.game_over:
        player, other = current_and_other_player(host, guest, match.turn)
        stats.turns += 1

        match.dice = [1] * 5
        match.kept = [0] * 5
        match.rolls_left = 3
        match.ai_rec = None

        while True:
            if match.rolls_left == 3:
                kept_mask = [0] * 5
            else:
                recommendation = request_recommendation(
                    session,
                    base_url,
                    match.dice,
                    match.rolls_left,
                    player.scorecard,
                    player.mode,
                    stats,
                )
                match.ai_rec = recommendation
                if should_stop_roll(recommendation):
                    break
                kept_mask = keep_indices_to_mask(recommendation.get("keep_indices") or [])
                match.kept = kept_mask[:]

            match.dice, match.rolls_left = perform_roll(session, base_url, code, player, kept_mask, stats)
            match.kept = kept_mask[:]
            action_counter += 1

            if observer_poll_every > 0 and action_counter % observer_poll_every == 0:
                known_version = observer_poll(
                    session, base_url, code, observer_name, host, guest, match, stats, known_version
                )

            if match.rolls_left == 0:
                break

        score_rec = request_recommendation(
            session,
            base_url,
            match.dice,
            0,
            player.scorecard,
            player.mode,
            stats,
        )
        match.ai_rec = score_rec
        category_idx = choose_category(score_rec, match.dice, player.scorecard, player.mode)
        apply_score(player.scorecard, match.dice, category_idx)
        stats.categories_written += 1

        next_turn = other.username
        match.dice = [1] * 5
        match.kept = [0] * 5
        match.rolls_left = 3

        if player_done(host) and player_done(guest):
            match.game_over = True
            match.end_reason = "score"
            host_total = calc_totals(host.scorecard)["total"]
            guest_total = calc_totals(guest.scorecard)["total"]
            if host_total > guest_total:
                match.winner = host.username
                match.loser = guest.username
            elif guest_total > host_total:
                match.winner = guest.username
                match.loser = host.username
            else:
                match.winner = None
                match.loser = None
        match.turn = next_turn

        sync_state(session, base_url, code, player, host, guest, match, stats)
        action_counter += 1
        known_version = observer_poll(session, base_url, code, observer_name, host, guest, match, stats, known_version)

        heartbeat_client(session, base_url, code, host.username, host.token, stats)
        heartbeat_client(session, base_url, code, guest.username, guest.token, stats)
        heartbeat_client(session, base_url, code, observer_name, None, stats)

    host_total = calc_totals(host.scorecard)["total"]
    guest_total = calc_totals(guest.scorecard)["total"]

    api_request(
        session,
        "POST",
        base_url,
        f"/api/rooms/{code}/leave",
        json_body={"username": observer_name},
    )
    api_request(
        session,
        "POST",
        base_url,
        f"/api/rooms/{code}/leave",
        json_body={"username": host.username, "player_token": host.token},
    )
    api_request(
        session,
        "POST",
        base_url,
        f"/api/rooms/{code}/leave",
        json_body={"username": guest.username, "player_token": guest.token},
    )

    stats.games += 1
    return {
        "code": code,
        "host_total": host_total,
        "guest_total": guest_total,
        "winner": match.winner,
        "draw": host_total == guest_total,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Target server base URL")
    parser.add_argument("--games", type=int, default=5, help="Number of full bot-vs-bot matches")
    parser.add_argument("--host-mode", default="focused", choices=["focused", "cover"], help="Host bot mode")
    parser.add_argument("--guest-mode", default="cover", choices=["focused", "cover"], help="Guest bot mode")
    parser.add_argument(
        "--observer-poll-every",
        type=int,
        default=2,
        help="Poll observer room state every N roll/sync actions (0 disables periodic polling)",
    )
    parser.add_argument("--report-every", type=int, default=1, help="Print progress every N games")
    parser.add_argument("--seed", type=int, default=20260412, help="Seed used only for any local tie shuffling")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    random.seed(args.seed)

    stats = SoakStats()
    started = time.perf_counter()
    session = requests.Session()
    session.headers.update({"User-Agent": "yacht-multiplayer-soak/1.0"})

    try:
        for game_index in range(1, args.games + 1):
            result = run_single_game(
                session,
                args.base_url,
                game_index,
                args.host_mode,
                args.guest_mode,
                args.observer_poll_every,
                stats,
            )
            if args.report_every > 0 and (game_index % args.report_every == 0 or game_index == args.games):
                print(
                    f"[multiplayer-soak] {game_index}/{args.games} "
                    f"room={result['code']} host={result['host_total']} guest={result['guest_total']} "
                    f"winner={result['winner'] or 'draw'}",
                    flush=True,
                )
    except Exception as exc:
        elapsed_s = time.perf_counter() - started
        print(f"[multiplayer-soak] FAILED after {elapsed_s:.2f}s: {exc}", file=sys.stderr, flush=True)
        return 1

    elapsed_s = time.perf_counter() - started
    print(f"[multiplayer-soak] completed games={stats.games} turns={stats.turns} rolls={stats.rolls}", flush=True)
    print(
        "[multiplayer-soak] "
        f"syncs={stats.syncs} recommends={stats.recommends} "
        f"heartbeats={stats.heartbeats} observer_polls={stats.observer_polls} "
        f"unchanged_hits={stats.unchanged_hits} categories={stats.categories_written}",
        flush=True,
    )
    print(f"[multiplayer-soak] recommend {summarize_ms(stats.recommend_ms)}", flush=True)
    print(f"[multiplayer-soak] roll       {summarize_ms(stats.roll_ms)}", flush=True)
    print(f"[multiplayer-soak] sync       {summarize_ms(stats.sync_ms)}", flush=True)
    print(f"[multiplayer-soak] room-get   {summarize_ms(stats.get_ms)}", flush=True)
    print(f"[multiplayer-soak] heartbeat  {summarize_ms(stats.heartbeat_ms)}", flush=True)
    print(f"[multiplayer-soak] elapsed={elapsed_s:.2f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
