"""Offline exact endgame value table lookup helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from .constants import CATS, CATEGORY_NAMES


DEFAULT_ENDGAME_VALUE_TABLE_PATH = "artifacts/value/endgame-value-table-open12.npz"


def encode_endgame_state(mask: int, upper_total: int, yacht_bonus_available: bool) -> str:
    return f"{int(mask)}:{max(0, min(63, int(upper_total)))}:{1 if yacht_bonus_available else 0}"


def closed_mask_from_scorecard(scorecard) -> int:
    mask = 0
    for idx, value in enumerate(tuple(scorecard)[: len(CATEGORY_NAMES)]):
        if value is not None:
            mask |= 1 << idx
    return mask


def capped_upper_total(scorecard) -> int:
    return max(0, min(63, int(sum((value or 0) for value in tuple(scorecard)[:6]))))


def yacht_bonus_available(scorecard) -> bool:
    values = tuple(scorecard)
    if len(values) <= CATS["Yacht"]:
        return False
    value = values[CATS["Yacht"]]
    return isinstance(value, (int, float)) and value >= 50


def state_key_from_scorecard(scorecard) -> str:
    return encode_endgame_state(
        closed_mask_from_scorecard(scorecard),
        capped_upper_total(scorecard),
        yacht_bonus_available(scorecard),
    )


@dataclass(frozen=True)
class EndgameValueTable:
    path: str
    max_open_count: int
    values: dict[str, float]
    dense_values: np.ndarray | None = None

    @classmethod
    def from_payload(cls, payload: dict, path: str = "<memory>") -> "EndgameValueTable":
        raw_values = payload.get("values", {})
        return cls(
            path=path,
            max_open_count=int(payload.get("batch_open_count", payload.get("max_exact_open", 0))),
            values={str(key): float(value) for key, value in raw_values.items()},
        )

    @classmethod
    def from_npz(cls, path: str) -> "EndgameValueTable":
        with np.load(path, allow_pickle=False) as payload:
            dense_values = np.asarray(payload["values"], dtype=np.float32)
            max_open_count = int(payload["max_open_count"])
        return cls(
            path=path,
            max_open_count=max_open_count,
            values={},
            dense_values=dense_values,
        )

    def lookup_state(self, mask: int, upper_total: int, yacht_bonus_available: bool) -> float | None:
        if self.dense_values is not None:
            if not (0 <= int(mask) < self.dense_values.shape[0]):
                return None
            capped_upper = max(0, min(63, int(upper_total)))
            bonus_idx = 1 if yacht_bonus_available else 0
            value = float(self.dense_values[int(mask), capped_upper, bonus_idx])
            if not np.isfinite(value):
                return None
            return value
        return self.values.get(encode_endgame_state(mask, upper_total, yacht_bonus_available))

    def lookup_key(self, key: str) -> float | None:
        if self.dense_values is None:
            return self.values.get(key)
        try:
            mask_text, upper_text, bonus_text = key.split(":")
            return self.lookup_state(int(mask_text), int(upper_text), bonus_text == "1")
        except (TypeError, ValueError):
            return None

    def lookup_scorecard(self, scorecard) -> tuple[float | None, str]:
        key = state_key_from_scorecard(scorecard)
        return self.lookup_key(key), key


@lru_cache(maxsize=8)
def load_endgame_value_table(path: str) -> EndgameValueTable:
    table_path = Path(path)
    if table_path.suffix == ".npz":
        return EndgameValueTable.from_npz(str(table_path))
    with table_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return EndgameValueTable.from_payload(payload, str(table_path))
