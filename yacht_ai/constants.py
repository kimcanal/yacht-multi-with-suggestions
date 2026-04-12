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
