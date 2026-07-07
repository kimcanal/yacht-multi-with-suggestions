from .constants import CATS, CATEGORY_NAMES


VALUE_CATEGORY_SCALES = [
    5.0,
    10.0,
    15.0,
    20.0,
    25.0,
    30.0,
    30.0,
    30.0,
    30.0,
    15.0,
    30.0,
    350.0,
]

VALUE_FEATURE_NAMES = (
    ["mode_cover"]
    + [f"open_cat_{idx}" for idx in range(12)]
    + [f"score_norm_{idx}" for idx in range(12)]
    + [
        "turns_completed",
        "open_count",
        "open_upper_count",
        "open_lower_count",
        "upper_score",
        "upper_gap",
        "upper_bonus_obtained",
        "upper_bonus_live",
        "upper_bonus_locked_out",
        "open_high_upper_count",
        "open_upper_face_value",
        "lower_score",
        "current_total",
        "yacht_bonus_active",
        "yacht_open",
        "choice_open",
        "open_hand_count",
        "yacht_bonus_cash_slots",
        "zero_category_count",
    ]
)


def normalize_scorecard(scorecard):
    base = [None] * 12
    if not isinstance(scorecard, (list, tuple)):
        return base
    for idx, value in enumerate(scorecard[:12]):
        if value is None:
            base[idx] = None
            continue
        try:
            base[idx] = int(value)
        except (TypeError, ValueError):
            base[idx] = None
    return base


def scorecard_totals(scorecard):
    scorecard = normalize_scorecard(scorecard)
    upper_score = sum((value or 0) for value in scorecard[:6])
    lower_score = sum((value or 0) for value in scorecard[6:])
    upper_bonus = 35 if upper_score >= 63 else 0
    return {
        "upper_score": upper_score,
        "lower_score": lower_score,
        "upper_bonus": upper_bonus,
        "total_score": upper_score + lower_score + upper_bonus,
    }


def open_mask(scorecard):
    scorecard = normalize_scorecard(scorecard)
    mask = 0
    for idx, value in enumerate(scorecard):
        if value is None:
            mask |= 1 << idx
    return mask


def closed_mask(scorecard):
    return ((1 << 12) - 1) ^ open_mask(scorecard)


def encode_value_state(scorecard, strategy_mode="focused"):
    scorecard = normalize_scorecard(scorecard)
    open_flags = [1.0 if value is None else 0.0 for value in scorecard]
    open_count = sum(open_flags)
    open_upper_count = sum(open_flags[:6])
    open_lower_count = sum(open_flags[6:])
    totals = scorecard_totals(scorecard)
    upper_score = totals["upper_score"]
    current_total = totals["total_score"]
    yacht_value = scorecard[CATS["Yacht"]]
    open_high_upper_count = sum(open_flags[3:6])
    open_upper_face_value = sum((idx + 1) for idx, value in enumerate(scorecard[:6]) if value is None)
    yacht_bonus_active = isinstance(yacht_value, (int, float)) and yacht_value >= 50
    zero_category_count = sum(1 for value in scorecard if value == 0)
    open_hand_count = sum(
        open_flags[idx]
        for idx in (
            CATS["4 of a Kind"],
            CATS["Full House"],
            CATS["Small Straight"],
            CATS["Large Straight"],
            CATS["Yacht"],
        )
    )

    features = [1.0 if strategy_mode == "cover" else 0.0]
    features.extend(open_flags)
    for idx, value in enumerate(scorecard):
        if value is None:
            features.append(0.0)
            continue
        scale = VALUE_CATEGORY_SCALES[idx]
        features.append(max(0.0, min(float(value) / scale, 3.0)))

    features.extend(
        [
            (12.0 - open_count) / 12.0,
            open_count / 12.0,
            open_upper_count / 6.0,
            open_lower_count / 6.0,
            min(float(upper_score) / 63.0, 2.0),
            max(0.0, 63.0 - float(upper_score)) / 63.0,
            1.0 if upper_score >= 63 else 0.0,
            1.0 if upper_score < 63 and open_upper_count > 0 else 0.0,
            1.0 if upper_score < 63 and open_upper_count == 0 else 0.0,
            open_high_upper_count / 3.0,
            open_upper_face_value / 21.0,
            min(float(totals["lower_score"]) / 250.0, 2.0),
            min(float(current_total) / 350.0, 2.0),
            1.0 if yacht_bonus_active else 0.0,
            open_flags[CATS["Yacht"]],
            open_flags[CATS["Choice"]],
            open_hand_count / 5.0,
            (sum(open_flags) - open_flags[CATS["Yacht"]]) / 11.0 if yacht_bonus_active else 0.0,
            zero_category_count / 12.0,
        ]
    )
    return features


def value_state_payload(scorecard, strategy_mode="focused"):
    scorecard = normalize_scorecard(scorecard)
    totals = scorecard_totals(scorecard)
    mask = open_mask(scorecard)
    open_categories = [idx for idx, value in enumerate(scorecard) if value is None]
    return {
        "strategy_mode": strategy_mode,
        "scorecard": list(scorecard),
        "turns_completed": 12 - len(open_categories),
        "open_categories": open_categories,
        "open_category_names": [CATEGORY_NAMES[idx] for idx in open_categories],
        "open_mask": mask,
        "closed_mask": ((1 << 12) - 1) ^ mask,
        "upper_score": totals["upper_score"],
        "upper_gap": max(0, 63 - totals["upper_score"]),
        "upper_bonus_obtained": totals["upper_bonus"] > 0,
        "lower_score": totals["lower_score"],
        "current_total": totals["total_score"],
        "yacht_value": scorecard[CATS["Yacht"]],
        "yacht_bonus_active": bool(
            isinstance(scorecard[CATS["Yacht"]], (int, float))
            and scorecard[CATS["Yacht"]] >= 50
        ),
        "feature_names": list(VALUE_FEATURE_NAMES),
        "feature_values": encode_value_state(scorecard, strategy_mode),
    }
