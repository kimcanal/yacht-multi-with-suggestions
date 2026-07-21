"""Deterministic dice helpers shared by runtime and experiment CLIs."""

from __future__ import annotations

import random

from .constants import CATS
from .scoring import calc_score

UINT64_MASK = (1 << 64) - 1


def total_score(scorecard: list[int | None]) -> int:
    upper = sum((value or 0) for value in scorecard[:6])
    lower = sum((value or 0) for value in scorecard[6:])
    return int(upper + lower + (35 if upper >= 63 else 0))


def splitmix64(value: int) -> int:
    value = (value + 0x9E3779B97F4A7C15) & UINT64_MASK
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & UINT64_MASK
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & UINT64_MASK
    return (value ^ (value >> 31)) & UINT64_MASK


def indexed_die(seed: int, turn_index: int, roll_step: int, die_index: int) -> int:
    mixed = int(seed) & UINT64_MASK
    mixed ^= ((turn_index + 1) * 0x9E3779B97F4A7C15) & UINT64_MASK
    mixed ^= ((roll_step + 1) * 0xBF58476D1CE4E5B9) & UINT64_MASK
    mixed ^= ((die_index + 1) * 0x94D049BB133111EB) & UINT64_MASK
    return int(splitmix64(mixed) % 6) + 1


def initial_dice(
    rng: random.Random,
    seed: int,
    turn_index: int,
    random_source: str,
) -> list[int]:
    if random_source == "indexed":
        return [indexed_die(seed, turn_index, 0, idx) for idx in range(5)]
    return [rng.randint(1, 6) for _ in range(5)]


def reroll_from_keep(
    rng: random.Random,
    dice: list[int],
    keep_indices: list[int],
    *,
    seed: int,
    turn_index: int,
    roll_step: int,
    random_source: str,
) -> list[int]:
    keep = set(keep_indices)
    if random_source == "indexed":
        return [
            value if idx in keep else indexed_die(seed, turn_index, roll_step, idx)
            for idx, value in enumerate(dice)
        ]
    return [value if idx in keep else rng.randint(1, 6) for idx, value in enumerate(dice)]


def apply_score(
    dice: list[int], scorecard: list[int | None], category_idx: int
) -> tuple[int, int]:
    """Record a category score and return ``(score, yacht_bonus)``.

    This is the single mutation point for the repeated-Yacht rule used by the
    web app, simulations, and training-data generators.
    """
    score = calc_score(dice, category_idx)
    yacht_bonus = 0
    yacht_idx = CATS["Yacht"]
    if (
        calc_score(dice, yacht_idx) == 50
        and isinstance(scorecard[yacht_idx], (int, float))
        and scorecard[yacht_idx] >= 50
        and category_idx != yacht_idx
        and score > 0
    ):
        scorecard[yacht_idx] += 100
        yacht_bonus = 100
    scorecard[category_idx] = score
    return score, yacht_bonus
