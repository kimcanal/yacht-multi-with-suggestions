import itertools
from collections import Counter

from .constants import CATS


OUTCOMES_CACHE = {}
KEEP_OPTIONS_CACHE = {}


def get_outcomes_probs(k):
    if k in OUTCOMES_CACHE:
        return OUTCOMES_CACHE[k]

    counts = Counter()
    for out in itertools.product(range(1, 7), repeat=k):
        counts[tuple(sorted(out))] += 1

    total = 6 ** k
    probs = [(list(out), cnt / total) for out, cnt in counts.items()]
    OUTCOMES_CACHE[k] = probs
    return probs


def get_keep_options(dice):
    dice_tuple = tuple(sorted(dice))
    cached = KEEP_OPTIONS_CACHE.get(dice_tuple)
    if cached is not None:
        return cached

    seen = set()
    options = []
    for mask in range(32):
        kept = tuple(dice_tuple[idx] for idx in range(5) if (mask >> idx) & 1)
        if kept in seen:
            continue
        seen.add(kept)
        options.append(kept)

    KEEP_OPTIONS_CACHE[dice_tuple] = options
    return options


def kept_tuple_to_indices(dice, kept_tuple):
    needed = Counter(kept_tuple)
    indices = []
    for idx, value in enumerate(dice):
        if needed[value] > 0:
            indices.append(idx)
            needed[value] -= 1
    return indices


def keep_values_desc(kept_tuple):
    return tuple(sorted(kept_tuple, reverse=True))


def has_yacht_bonus(scorecard):
    if not isinstance(scorecard, list) or len(scorecard) <= CATS["Yacht"]:
        return False
    value = scorecard[CATS["Yacht"]]
    return isinstance(value, (int, float)) and value >= 50


def _calc_score_internal(dice, category_idx):
    counts = Counter(dice)

    if 0 <= category_idx <= 5:
        return counts[category_idx + 1] * (category_idx + 1)

    if category_idx == CATS["Choice"]:
        return sum(dice)

    if category_idx == CATS["4 of a Kind"]:
        most_common = counts.most_common(1)[0]
        if most_common[1] >= 4:
            return sum(dice)
        return 0

    if category_idx == CATS["Full House"]:
        if len(counts) == 2 and 3 in counts.values() and 2 in counts.values():
            return sum(dice)
        if len(counts) == 1 and len(dice) == 5:
            return sum(dice)
        return 0

    if category_idx == CATS["Small Straight"]:
        s_dice = set(dice)
        straights = [{1, 2, 3, 4}, {2, 3, 4, 5}, {3, 4, 5, 6}]
        if any(straight.issubset(s_dice) for straight in straights):
            return 15
        return 0

    if category_idx == CATS["Large Straight"]:
        s_dice = set(dice)
        if {1, 2, 3, 4, 5}.issubset(s_dice) or {2, 3, 4, 5, 6}.issubset(s_dice):
            return 30
        return 0

    if category_idx == CATS["Yacht"]:
        if len(counts) == 1:
            return 50
        return 0

    return 0


SCORE_TABLE = {}
for dice in itertools.combinations_with_replacement(range(1, 7), 5):
    SCORE_TABLE[dice] = {}
    for cat_idx in CATS.values():
        SCORE_TABLE[dice][cat_idx] = _calc_score_internal(dice, cat_idx)


def calc_score(dice, category_idx):
    return SCORE_TABLE[tuple(sorted(dice))][category_idx]


def can_cash_yacht_bonus(dice, open_categories, scorecard):
    if not has_yacht_bonus(scorecard):
        return False
    if calc_score(dice, CATS["Yacht"]) != 50:
        return False
    for category_idx in open_categories:
        if category_idx == CATS["Yacht"]:
            continue
        if calc_score(dice, category_idx) > 0:
            return True
    return False


def get_success_probability(kept_dice, category_idx):
    num_reroll = 5 - len(kept_dice)
    if num_reroll == 0:
        return 1.0 if calc_score(kept_dice, category_idx) > 0 else 0.0

    success_prob = 0.0
    for outcome, prob in get_outcomes_probs(num_reroll):
        next_dice = kept_dice + outcome
        if calc_score(next_dice, category_idx) > 0:
            success_prob += prob
    return success_prob


def get_category_expected_value(kept_dice, category_idx, num_reroll):
    if num_reroll == 0:
        return float(calc_score(kept_dice, category_idx))

    ev = 0.0
    for outcome, prob in get_outcomes_probs(num_reroll):
        next_dice = kept_dice + outcome
        ev += prob * calc_score(next_dice, category_idx)
    return ev
