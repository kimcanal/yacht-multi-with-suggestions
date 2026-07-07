"""Experimental learned scorecard value model lookup."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .value_model import VALUE_FEATURE_NAMES, encode_value_state


@dataclass(frozen=True)
class LinearScorecardValueModel:
    path: str
    model_id: str
    target: str
    validation_mae: float | None
    bias: float
    weights: tuple[float, ...]

    @classmethod
    def from_payload(cls, payload: dict, path: str = "<memory>") -> "LinearScorecardValueModel":
        feature_names = tuple(payload.get("feature_names", ()))
        if feature_names and feature_names != tuple(VALUE_FEATURE_NAMES):
            raise ValueError("value model feature_names do not match current encoder")
        metrics = payload.get("validation_metrics", {})
        validation_mae = metrics.get("mae")
        return cls(
            path=path,
            model_id=str(payload.get("model_id", "scorecard-value-linear")),
            target=str(payload.get("target", "target_remaining_score")),
            validation_mae=float(validation_mae) if validation_mae is not None else None,
            bias=float(payload.get("bias", 0.0)),
            weights=tuple(float(value) for value in payload.get("weights", [])),
        )

    def is_usable(self, max_validation_mae: float) -> bool:
        if self.target != "target_remaining_score":
            return False
        if len(self.weights) != len(VALUE_FEATURE_NAMES):
            return False
        if self.validation_mae is None:
            return False
        return self.validation_mae <= max_validation_mae

    def predict_remaining(self, scorecard, strategy_mode: str = "focused") -> float:
        features = encode_value_state(scorecard, strategy_mode)
        value = self.bias
        for weight, feature in zip(self.weights, features):
            value += weight * feature
        return max(0.0, min(350.0, float(value)))


@lru_cache(maxsize=8)
def load_linear_value_model(path: str) -> LinearScorecardValueModel:
    model_path = Path(path)
    with model_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return LinearScorecardValueModel.from_payload(payload, str(model_path))
