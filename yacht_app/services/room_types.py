"""Typed shapes used by multiplayer room services.

Room data is persisted as JSON-compatible dictionaries.  Keeping the public
shape here makes service boundaries explicit without forcing a migration of
the existing Redis/in-memory stores.
"""

from __future__ import annotations

from typing import NotRequired, TypedDict


class RoomState(TypedDict, total=False):
    dice: list[int]
    kept: list[int]
    rolls_left: int
    scores: dict[str, list[int | None]]
    player_dice: dict[str, list[int]]
    player_kept: dict[str, list[int]]
    player_rolls_left: dict[str, int]
    players: list[str]
    turn: str | None
    turn_start_time: float | None
    game_over: bool
    version: int
    updated_by: str | None
    winner: str | None
    loser: str | None
    end_reason: str | None
    timeout_event: NotRequired[dict]


class Room(TypedDict, total=False):
    host: str
    players: list[str]
    observers: list[str]
    state: RoomState
    started_full: bool
    last_update: float
