"""Shared labels for how clearly one action beats its nearest alternative."""


def classify_alternative_gap(value):
    """Return a UI- and dataset-safe band for an expected-value action gap.

    The gap is expressed in expected final-score points.  It is not a model
    probability: a small gap means that a player can safely prefer a nearby
    alternative, while a negative gap records a deliberate focused-mode
    trade-off against the generic EV-best action.
    """

    try:
        gap = float(value)
    except (TypeError, ValueError):
        return {
            "key": "unknown",
            "label": "차선책 비교 없음",
            "description": "이 추천에는 비교 가능한 차선책 점수가 없습니다.",
            "gap": None,
        }

    rounded_gap = round(gap, 2)
    if gap < -0.01:
        return {
            "key": "strategy_tradeoff",
            "label": "목표 우선 선택",
            "description": "현재 목표를 위해 일반 기대값이 더 높은 대안을 일부 양보한 선택입니다.",
            "gap": rounded_gap,
        }
    if gap <= 0.15:
        return {
            "key": "near_tie",
            "label": "대안도 거의 비슷함",
            "description": "차선책과 기대값 차이가 작아 선호하는 비슷한 선택을 해도 됩니다.",
            "gap": rounded_gap,
        }
    if gap <= 1.0:
        return {
            "key": "slight_edge",
            "label": "추천이 조금 우세",
            "description": "추천이 차선책보다 낫지만, 판세를 뒤집을 만큼 큰 차이는 아닙니다.",
            "gap": rounded_gap,
        }
    return {
        "key": "clear_edge",
        "label": "추천이 뚜렷하게 우세",
        "description": "추천과 차선책의 기대값 차이가 커서 추천을 따를 가치가 큽니다.",
        "gap": rounded_gap,
    }


def recommendation_strength(value):
    """Return a player-facing 10-point cue from the nearest-action gap.

    It is a recommendation-strength label, never a probability or projected
    game score. A clear edge is 9/10 rather than 10/10 because dice outcomes
    remain uncertain.
    """
    band = classify_alternative_gap(value)
    points_by_key = {
        "strategy_tradeoff": 5,
        "near_tie": 5,
        "slight_edge": 7,
        "clear_edge": 9,
    }
    points = points_by_key.get(band["key"])
    if points is None:
        return {
            "points": None,
            "label": "비교 불가",
            "description": band["description"],
        }
    return {
        "points": points,
        "label": f"추천 정도 {points}/10",
        "description": band["description"],
    }
