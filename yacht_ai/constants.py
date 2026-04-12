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
