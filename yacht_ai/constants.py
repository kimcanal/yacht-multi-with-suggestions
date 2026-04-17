CATS = {
    "Ones": 0,
    "Twos": 1,
    "Threes": 2,
    "Fours": 3,
    "Fives": 4,
    "Sixes": 5,
    "Choice": 6,
    "4 of a Kind": 7,
    "Full House": 8,
    "Small Straight": 9,
    "Large Straight": 10,
    "Yacht": 11,
}

CATEGORY_NAMES = list(CATS.keys())

HAND_FIXED_SCORES = {
    "Yacht": 50,
    "Yacht Bonus": 115,
    "Large Straight": 30,
    "Small Straight": 15,
}

UPPER_CAT_NAMES = ["Ones", "Twos", "Threes", "Fours", "Fives", "Sixes"]

SACRIFICE_PRIORITY = {
    "Ones": 0,
    "Twos": 1,
    "Yacht": 2,
    "Threes": 3,
    "Small Straight": 4,
    "Large Straight": 5,
    "Full House": 6,
    "4 of a Kind": 7,
    "Choice": 8,
    "Fours": 9,
    "Fives": 10,
    "Sixes": 11,
}

EPS = 1e-12

FOCUSED_HAND_PRIORITY = {
    "Full House": 5,
    "Small Straight": 4,
    "Large Straight": 3,
    "4 of a Kind": 2,
    "Yacht Bonus": 1,
    "Yacht": 0,
}

# Exact single-turn baselines from a fresh turn:
# initial roll + up to two rerolls, optimized for one target category.
FRESH_TURN_CATEGORY_EV = {
    "Ones": 2.1065,
    "Twos": 4.2130,
    "Threes": 6.3194,
    "Fours": 8.4259,
    "Fives": 10.5324,
    "Sixes": 12.6389,
    "Choice": 23.3333,
    "4 of a Kind": 5.6113,
    "Full House": 7.0136,
    "Small Straight": 9.2316,
    "Large Straight": 7.8329,
    "Yacht": 2.3014,
}

FRESH_TURN_CATEGORY_HIT_RATE = {
    "Ones": 0.9351,
    "Twos": 0.9351,
    "Threes": 0.9351,
    "Fours": 0.9351,
    "Fives": 0.9351,
    "Sixes": 0.9351,
    "Choice": 1.0,
    "4 of a Kind": 0.2908,
    "Full House": 0.3661,
    "Small Straight": 0.6154,
    "Large Straight": 0.2611,
    "Yacht": 0.0460,
}

FUTURE_CATEGORY_WEIGHT = 0.22
SCORE_STAGE_QUALITY_WEIGHT = 0.14
SCORE_STAGE_PRESSURE_RELIEF = 0.50

# Fresh-turn optimal count distribution for Ones~Sixes.
# Scores for each upper category are just face * count, so one distribution
# can be reused across all six upper slots.
UPPER_FRESH_COUNT_PROBS = {
    0: 0.06490547,
    1: 0.23625592,
    2: 0.34398861,
    3: 0.25042371,
    4: 0.09115423,
    5: 0.01327206,
}

# ── Upper bonus push weights ─────────────────────────────────────────────────
UPPER_BONUS_VALUE = 35.0
UPPER_BONUS_PROGRESS_WEIGHT = 0.35
UPPER_BONUS_FACE_MULT_FOCUSED = 2.4
UPPER_BONUS_FACE_MULT_COVER = 2.0
UPPER_BONUS_FACE2_MULT_FOCUSED = 1.2
UPPER_BONUS_FACE2_MULT_COVER = 0.8

# ── Category utility bonuses / penalties (score_stage) ───────────────────────
CHOICE_HIGH_SCORE_THRESHOLD = 20
CHOICE_UTILITY_BONUS_HIGH_COVER = 3.0
CHOICE_UTILITY_BONUS_HIGH_FOCUSED = 1.5
CHOICE_UTILITY_BONUS_LOW = 1.0
FOUR_KIND_UTILITY_BONUS_FOCUSED = 6.0
FOUR_KIND_UTILITY_BONUS_COVER = 4.0
FOUR_KIND_UTILITY_PENALTY = 1.5
FULL_HOUSE_UTILITY_BONUS_FOCUSED = 4.5
FULL_HOUSE_UTILITY_BONUS_COVER = 3.0
FULL_HOUSE_UTILITY_PENALTY = 1.5
SMALL_STRAIGHT_UTILITY_BONUS = 2.5
STRAIGHT_UTILITY_PENALTY = 1.0
LARGE_STRAIGHT_UTILITY_BONUS = 6.0
YACHT_UTILITY_BONUS = 40.0
YACHT_UTILITY_PENALTY = 4.0
YACHT_BONUS_CASH_IN = 100.0

# ── Future pressure category increments ──────────────────────────────────────
PRESSURE_INCREMENT_CHOICE = 0.25
PRESSURE_INCREMENT_SMALL_STRAIGHT = 0.20
PRESSURE_INCREMENT_LARGE_STRAIGHT = 0.35
PRESSURE_INCREMENT_FULL_HOUSE = 0.15
PRESSURE_INCREMENT_FOUR_KIND = 0.10
PRESSURE_INCREMENT_YACHT = 0.10
PRESSURE_UPPER_DONE_MULT = 0.55
PRESSURE_YACHT_BONUS_CHOICE_MULT = 0.90
PRESSURE_YACHT_BONUS_OTHER_MULT = 0.45

# ── Long-term quality / pressure thresholds ──────────────────────────────────
QUALITY_BONUS_MIN = -3.0
QUALITY_BONUS_MAX = 4.0
LONG_TERM_PRESSURE_THRESHOLD = 2.5
LONG_TERM_QUALITY_GAP_HIGH = 6.0
LONG_TERM_PRESSURE_SAVED_THRESHOLD = 0.8
SACRIFICE_BONUS_DROP_THRESHOLD = 0.03

# ── Choice rebalancing ────────────────────────────────────────────────────────
CHOICE_REBALANCE_UTILITY_GAP = 2.0
CHOICE_REBALANCE_SCORE_GAP = 5
CHOICE_REBALANCE_BASE_PENALTY = 2.6
CHOICE_REBALANCE_PER_POINT = 0.35

# ── Display meter scales ──────────────────────────────────────────────────────
DECISION_ROW_EV_SCALE = 30.0
DECISION_ROW_METER_FLOOR = 0.15
SCORE_ROW_UTILITY_SCALE = 50.0
QUALITY_GAP_METER_SCALE = 12.0

# Monte Carlo estimate of long-run score loss when each category is pre-closed at 0
# from an empty scorecard using the current policy stack.
CATEGORY_CLOSING_COST = {
    "Ones": 8.75,
    "Twos": 8.42,
    "Threes": 5.75,
    "Fours": 22.75,
    "Fives": 9.17,
    "Sixes": 14.83,
    "Choice": 10.50,
    "4 of a Kind": 11.42,
    "Full House": 18.92,
    "Small Straight": 12.75,
    "Large Straight": 29.58,
    "Yacht": 1.50,
}
