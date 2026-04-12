import itertools
from collections import Counter

from .constants import CATS


OUTCOMES_CACHE = {}
KEEP_OPTIONS_CACHE = {}
TRANSITION_DISTRIBUTION_CACHE = {}


def get_outcomes_probs(k):
    if k in OUTCOMES_CACHE:
        return OUTCOMES_CACHE[k]

    counts = Counter()
    for out in itertools.product(range(1, 7), repeat=k):
        counts[tuple(sorted(out))] += 1

    total = 6 ** k
    probs = tuple((out, cnt / total) for out, cnt in counts.items())
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


def get_transition_distribution(kept_tuple):
    kept_tuple = tuple(sorted(kept_tuple))
    cached = TRANSITION_DISTRIBUTION_CACHE.get(kept_tuple)
    if cached is not None:
        return cached

    reroll_count = 5 - len(kept_tuple)
    if reroll_count <= 0:
        transitions = ((kept_tuple, 1.0),)
    else:
        transitions = tuple(
            (tuple(sorted(kept_tuple + outcome)), prob)
            for outcome, prob in get_outcomes_probs(reroll_count)
        )

    TRANSITION_DISTRIBUTION_CACHE[kept_tuple] = transitions
    return transitions


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
    if not isinstance(scorecard, (list, tuple)) or len(scorecard) <= CATS["Yacht"]:
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


DICE_STATES = tuple(SCORE_TABLE.keys())
PRECOMPUTED_SUCCESS_CATEGORIES = (
    CATS["Yacht"],
    CATS["4 of a Kind"],
    CATS["Full House"],
    CATS["Large Straight"],
    CATS["Small Straight"],
)
PRECOMPUTED_SCORE_CATEGORIES = (
    CATS["4 of a Kind"],
)
TARGET_SUCCESS_TABLE = {category_idx: [{}, {}, {}] for category_idx in PRECOMPUTED_SUCCESS_CATEGORIES}
TARGET_SCORE_TABLE = {category_idx: [{}, {}, {}] for category_idx in PRECOMPUTED_SCORE_CATEGORIES}


def _build_precomputed_target_tables():
    for category_idx in PRECOMPUTED_SUCCESS_CATEGORIES:
        base = TARGET_SUCCESS_TABLE[category_idx][0]
        for dice in DICE_STATES:
            base[dice] = 1.0 if SCORE_TABLE[dice][category_idx] > 0 else 0.0

        for rerolls_remaining in (1, 2):
            prev = TARGET_SUCCESS_TABLE[category_idx][rerolls_remaining - 1]
            curr = TARGET_SUCCESS_TABLE[category_idx][rerolls_remaining]
            for dice in DICE_STATES:
                best_value = prev[dice]
                for kept_tuple in get_keep_options(dice):
                    value = 0.0
                    for next_dice, prob in get_transition_distribution(kept_tuple):
                        value += prob * prev[next_dice]
                    if value > best_value:
                        best_value = value
                curr[dice] = best_value

    for category_idx in PRECOMPUTED_SCORE_CATEGORIES:
        base = TARGET_SCORE_TABLE[category_idx][0]
        for dice in DICE_STATES:
            base[dice] = float(SCORE_TABLE[dice][category_idx])

        for rerolls_remaining in (1, 2):
            prev = TARGET_SCORE_TABLE[category_idx][rerolls_remaining - 1]
            curr = TARGET_SCORE_TABLE[category_idx][rerolls_remaining]
            for dice in DICE_STATES:
                best_value = prev[dice]
                for kept_tuple in get_keep_options(dice):
                    value = 0.0
                    for next_dice, prob in get_transition_distribution(kept_tuple):
                        value += prob * prev[next_dice]
                    if value > best_value:
                        best_value = value
                curr[dice] = best_value


def get_precomputed_target_success_value(state_dice, rerolls_remaining, category_idx):
    return TARGET_SUCCESS_TABLE[category_idx][rerolls_remaining][tuple(sorted(state_dice))]


def get_precomputed_target_score_value(state_dice, rerolls_remaining, category_idx):
    return TARGET_SCORE_TABLE[category_idx][rerolls_remaining][tuple(sorted(state_dice))]


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
    success_prob = 0.0
    for next_dice, prob in get_transition_distribution(kept_dice):
        if calc_score(next_dice, category_idx) > 0:
            success_prob += prob
    return success_prob


def get_category_expected_value(kept_dice, category_idx, num_reroll):
    if num_reroll == 0:
        return float(calc_score(kept_dice, category_idx))

    ev = 0.0
    kept_tuple = tuple(sorted(kept_dice))
    if num_reroll != 5 - len(kept_tuple):
        for outcome, prob in get_outcomes_probs(num_reroll):
            next_dice = tuple(sorted(kept_tuple + outcome))
            ev += prob * calc_score(next_dice, category_idx)
        return ev

    for next_dice, prob in get_transition_distribution(kept_tuple):
        ev += prob * calc_score(next_dice, category_idx)
    return ev


for reroll_count in range(6):
    get_outcomes_probs(reroll_count)

for dice in itertools.combinations_with_replacement(range(1, 7), 5):
    get_keep_options(dice)

for keep_size in range(6):
    for kept_tuple in itertools.combinations_with_replacement(range(1, 7), keep_size):
        get_transition_distribution(kept_tuple)

_build_precomputed_target_tables()
