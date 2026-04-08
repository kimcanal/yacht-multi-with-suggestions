import itertools
from copy import deepcopy
from collections import Counter
from functools import lru_cache

CATS = {
    'Ones': 0, 'Twos': 1, 'Threes': 2, 'Fours': 3, 'Fives': 4, 'Sixes': 5,
    'Choice': 6, '4 of a Kind': 7, 'Full House': 8, 'Small Straight': 9, 'Large Straight': 10, 'Yacht': 11
}
HAND_FIXED_SCORES = {
    'Yacht': 50,
    'Yacht Bonus': 115,
    'Large Straight': 30,
    'Small Straight': 15,
}
UPPER_CAT_NAMES = ['Ones', 'Twos', 'Threes', 'Fours', 'Fives', 'Sixes']
SACRIFICE_PRIORITY = {
    'Ones': 0,
    'Twos': 1,
    'Yacht': 2,
    'Threes': 3,
    'Small Straight': 4,
    'Large Straight': 5,
    'Full House': 6,
    '4 of a Kind': 7,
    'Choice': 8,
    'Fours': 9,
    'Fives': 10,
    'Sixes': 11,
}

OUTCOMES_CACHE = {}
KEEP_OPTIONS_CACHE = {}
EPS = 1e-12
FOCUSED_HAND_PRIORITY = {
    'Full House': 5,
    'Small Straight': 4,
    'Large Straight': 3,
    '4 of a Kind': 2,
    'Yacht Bonus': 1,
    'Yacht': 0,
}

def _normalize_strategy_mode(strategy_mode):
    if strategy_mode in ('focused', 'cover'):
        return strategy_mode
    if strategy_mode in ('safe', 'aggressive'):
        return 'focused'
    return 'focused'

def get_outcomes_probs(k):
    if k in OUTCOMES_CACHE: return OUTCOMES_CACHE[k]
    counts = Counter()
    for out in itertools.product(range(1, 7), repeat=k):
        counts[tuple(sorted(out))] += 1
    total = 6**k
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

def _kept_tuple_to_indices(dice, kept_tuple):
    needed = Counter(kept_tuple)
    indices = []
    for idx, value in enumerate(dice):
        if needed[value] > 0:
            indices.append(idx)
            needed[value] -= 1
    return indices

def _keep_values_desc(kept_tuple):
    return tuple(sorted(kept_tuple, reverse=True))

def _has_yacht_bonus(scorecard):
    if not isinstance(scorecard, list) or len(scorecard) <= CATS['Yacht']:
        return False
    value = scorecard[CATS['Yacht']]
    return isinstance(value, (int, float)) and value >= 50

def _can_cash_yacht_bonus(dice, open_categories, scorecard):
    if not _has_yacht_bonus(scorecard):
        return False
    if calc_score(dice, CATS['Yacht']) != 50:
        return False
    for category_idx in open_categories:
        if category_idx == CATS['Yacht']:
            continue
        if calc_score(dice, category_idx) > 0:
            return True
    return False

def _straight_keep_rank(kept_tuple):
    return (-len(kept_tuple), _keep_values_desc(kept_tuple))

def _default_keep_rank(kept_tuple):
    return (len(kept_tuple), _keep_values_desc(kept_tuple))

def _choose_target_keep(cat_name, kept_tuples):
    if not kept_tuples:
        return ()
    if cat_name in ('Small Straight', 'Large Straight'):
        return max(kept_tuples, key=_straight_keep_rank)
    if cat_name == 'Full House' and () in kept_tuples:
        return ()
    return max(kept_tuples, key=_default_keep_rank)

def _choose_general_keep(kept_tuples):
    if not kept_tuples:
        return ()
    return max(kept_tuples, key=_default_keep_rank)

# --- 점수 계산 최적화 (Pre-calculation) ---
def _calc_score_internal(dice, category_idx):
    counts = Counter(dice)
    
    if 0 <= category_idx <= 5: # 1~6
        return counts[category_idx + 1] * (category_idx + 1)
    
    if category_idx == CATS['Choice']:
        return sum(dice)

    if category_idx == CATS['4 of a Kind']:
        # 4개 이상 동일하면 5개 전체 합산
        most_common = counts.most_common(1)[0]
        if most_common[1] >= 4:
            return sum(dice)
        return 0
    
    if category_idx == CATS['Full House']:
        # 5개 전체 합산 (3+2 조합일 때만)
        if len(counts) == 2 and 3 in counts.values() and 2 in counts.values():
            return sum(dice)
        # 5 of a kind도 Full House로 인정
        if len(counts) == 1 and len(dice) == 5:
            return sum(dice)
        return 0
    
    if category_idx == CATS['Small Straight']:
        # 연속 4개: 1-2-3-4, 2-3-4-5, 3-4-5-6 중 하나, 15점 고정
        s_dice = set(dice)
        straights = [{1,2,3,4}, {2,3,4,5}, {3,4,5,6}]
        if any(s.issubset(s_dice) for s in straights):
            return 15
        return 0
        
    if category_idx == CATS['Large Straight']:
        # 연속 5개: 1-2-3-4-5 또는 2-3-4-5-6, 30점 고정
        s_dice = set(dice)
        if {1,2,3,4,5}.issubset(s_dice) or {2,3,4,5,6}.issubset(s_dice):
            return 30
        return 0

    if category_idx == CATS['Yacht']:
        if len(counts) == 1: return 50
        return 0
        
    return 0

SCORE_TABLE = {}
# 모든 주사위 조합(252가지)에 대한 점수를 미리 계산하여 캐싱
for d in itertools.combinations_with_replacement(range(1, 7), 5):
    SCORE_TABLE[d] = {}
    for cat_idx in CATS.values():
        SCORE_TABLE[d][cat_idx] = _calc_score_internal(d, cat_idx)

def calc_score(dice, category_idx):
    return SCORE_TABLE[tuple(sorted(dice))][category_idx]

def get_success_probability(kept_dice, category_idx):
    num_reroll = 5 - len(kept_dice)
    if num_reroll == 0:
        return 1.0 if calc_score(kept_dice, category_idx) > 0 else 0.0
    
    success_prob = 0
    for outcome, prob in get_outcomes_probs(num_reroll):
        next_dice = kept_dice + outcome
        if calc_score(next_dice, category_idx) > 0:
            success_prob += prob
    return success_prob

def get_category_expected_value(kept_dice, category_idx, num_reroll):
    """특정 카테고리에 대한 기대값 계산"""
    if num_reroll == 0:
        return float(calc_score(kept_dice, category_idx))
    
    ev = 0
    for outcome, prob in get_outcomes_probs(num_reroll):
        next_dice = kept_dice + outcome
        score = calc_score(next_dice, category_idx)
        ev += prob * score
    return ev

def _hand_score_hint(cat_name, move):
    if cat_name in HAND_FIXED_SCORES:
        return HAND_FIXED_SCORES[cat_name]
    if cat_name == 'Full House':
        return 22
    if cat_name == '4 of a Kind':
        return int(round(move.get('conditional_ev', 20)))
    return 0

def _build_reason(cat_name, prob, mode):
    pct = f"{prob * 100:.1f}%"
    if mode == 'cover':
        return f"커버 참고: {cat_name}까지 이어질 확률 {pct}"
    if prob >= 0.75:
        return f"집중 공략: {cat_name} 성공 확률 {pct}"
    if prob >= 0.35:
        return f"집중 공략: {cat_name} 완성 확률 {pct}"
    return f"집중 공략: {cat_name} 도달 확률 {pct}"

def _build_summary(best_item, mode):
    if not best_item:
        return "추천 없음: 다시 굴리며 다음 기회를 보는 편이 좋습니다."
    style_label = "집중 공략" if mode != 'cover' else "커버 플레이"
    return f"{style_label} 추천: {best_item['name']} 확률 {best_item['val_str']}"

def _mode_rank(move, mode):
    score_hint = _hand_score_hint(move['name'], move)
    prob = move.get('prob', 0)
    focused_name = move.get('name')
    focused_priority = FOCUSED_HAND_PRIORITY.get(focused_name, move.get('priority', 0))
    return (prob, score_hint, focused_priority, move.get('tie_values', []))

def _cover_upgrade_rank(target_rows):
    if not target_rows:
        return (0.0, 0.0, 0.0)
    weighted_prob = 0.0
    best_prob = 0.0
    best_hint = 0.0
    for row in target_rows:
        hint = _hand_score_hint(row["name"], row)
        prob = row.get("prob", 0.0)
        weighted_prob += hint * prob
        if prob > best_prob or (abs(prob - best_prob) <= EPS and hint > best_hint):
            best_prob = prob
            best_hint = hint
    return (weighted_prob, best_prob, best_hint)

def _normalize_scorecard(scorecard):
    base = [None] * 12
    if not isinstance(scorecard, list):
        return base
    for idx, value in enumerate(scorecard[:12]):
        base[idx] = value
    return base

def _scorecard_to_tuple(scorecard):
    return tuple(_normalize_scorecard(scorecard))

def _score_stage_upper_bonus_push(face, count, current_upper, score, mode):
    projected_upper = current_upper + score
    bonus_delta = 35 if current_upper < 63 <= projected_upper else 0
    bonus_push = 0.0

    if current_upper < 63:
        progress = max(0, min(score, 63 - current_upper))
        bonus_push += progress * 0.35
        if count >= 3:
            bonus_push += face * (2.4 if mode == 'focused' else 2.0)
        elif count == 2 and face >= 5:
            bonus_push += face * (1.2 if mode == 'focused' else 0.8)

    return bonus_push + bonus_delta, bonus_delta

def _score_stage_category_advice(dice, scorecard, category_idx, mode):
    name = list(CATS.keys())[category_idx]
    score = calc_score(dice, category_idx)
    utility = float(score)
    reason = f"즉시 {score}점"
    yacht_bonus_active = (
        category_idx != CATS['Yacht']
        and score > 0
        and _has_yacht_bonus(scorecard)
        and calc_score(dice, CATS['Yacht']) == 50
    )

    if category_idx < 6:
        face = category_idx + 1
        count = dice.count(face)
        current_upper = sum((value or 0) for value in scorecard[:6])
        bonus_push, bonus_delta = _score_stage_upper_bonus_push(face, count, current_upper, score, mode)
        utility += bonus_push
        if bonus_delta:
            reason = f"이번 기록으로 Upper Bonus +35를 바로 확보합니다"
        elif count >= 3 and face >= 4:
            reason = f"{name} {score}점으로 상단 보너스 페이스를 강하게 유지합니다"
        elif count >= 3:
            reason = f"{name} {score}점으로 상단 점수를 안정적으로 쌓습니다"
        elif score > 0:
            reason = f"{name} {score}점으로 손실 없이 턴을 정리합니다"
        else:
            reason = f"{name}에 기록하면 0점 처리입니다"
    elif category_idx == CATS['Choice']:
        if score >= 20:
            utility += 3.0 if mode == 'cover' else 1.5
            reason = f"즉시 {score}점으로 무난하게 착지할 수 있습니다"
        elif score > 0:
            utility += 1.0
            reason = f"Choice {score}점으로 이번 턴 손실을 줄입니다"
        else:
            reason = "Choice도 이번 턴엔 점수가 나지 않습니다"
    elif category_idx == CATS['4 of a Kind']:
        if score > 0:
            utility += 6.0 if mode == 'focused' else 4.0
            reason = f"4 of a Kind {score}점으로 하단 고점을 확보합니다"
        else:
            utility -= 1.5
            reason = "4 of a Kind에 적으면 0점입니다"
    elif category_idx == CATS['Full House']:
        if score > 0:
            utility += 4.5 if mode == 'focused' else 3.0
            reason = f"Full House {score}점으로 점수 효율이 좋습니다"
        else:
            utility -= 1.5
            reason = "Full House에 적으면 0점입니다"
    elif category_idx == CATS['Small Straight']:
        if score > 0:
            utility += 2.5
            reason = "Small Straight 15점을 바로 확보합니다"
        else:
            utility -= 1.0
            reason = "Small Straight에 적으면 0점입니다"
    elif category_idx == CATS['Large Straight']:
        if score > 0:
            utility += 6.0
            reason = "Large Straight 30점은 바로 챙길 가치가 큽니다"
        else:
            utility -= 1.0
            reason = "Large Straight에 적으면 0점입니다"
    elif category_idx == CATS['Yacht']:
        if score > 0:
            utility += 40.0
            reason = "Yacht 50점은 바로 확정하는 편이 가장 좋습니다"
        else:
            utility -= 4.0
            reason = "Yacht는 이번 턴을 비우는 희생 칸 후보로만 보세요"

    if yacht_bonus_active:
        utility += 100.0
        reason = f"Yacht Bonus +100과 함께 {name} {score}점을 기록할 수 있습니다"

    return {
        "name": name,
        "score": score,
        "utility": utility,
        "reason": reason,
    }

def _score_stage_sacrifice_key(row):
    return (
        row["score"],
        SACRIFICE_PRIORITY.get(row["name"], 99),
    )

def _build_score_stage_advice(dice, scorecard, open_categories, mode):
    scorecard = _normalize_scorecard(scorecard)
    rows = [_score_stage_category_advice(dice, scorecard, idx, mode) for idx in open_categories]
    positive_rows = [row for row in rows if row["score"] > 0]
    positive_rows.sort(key=lambda row: (row["utility"], row["score"]), reverse=True)

    sacrifice_rows = [row for row in rows if row["score"] == 0]
    if not sacrifice_rows:
        sacrifice_rows = sorted(rows, key=_score_stage_sacrifice_key)[:2]
    else:
        sacrifice_rows.sort(key=_score_stage_sacrifice_key)

    display_rows = []
    for row in positive_rows[:3]:
        display_rows.append({
            "name": row["name"],
            "prob": 0.0,
            "meter": min(1.0, max(0.15, row["utility"] / 50.0)),
            "val_str": f"{row['score']}점",
            "type": "score",
            "keep_str": "지금 기록 추천",
            "keep_indices": [],
            "reason": row["reason"],
        })

    for row in sacrifice_rows:
        if any(existing["name"] == row["name"] for existing in display_rows):
            continue
        display_rows.append({
            "name": row["name"],
            "prob": 0.0,
            "meter": 0.18,
            "val_str": f"{row['score']}점",
            "type": "sacrifice",
            "keep_str": "망한 턴 정리용 희생 후보",
            "keep_indices": [],
            "reason": "이번 턴을 넘겨야 하면 손실이 작은 칸부터 비우는 편이 좋습니다" if row["name"] != "Yacht" else "Yacht는 마지막 수단용 희생 칸 후보로만 보세요",
        })
        if len(display_rows) >= 5:
            break

    if positive_rows:
        best_row = positive_rows[0]
        summary = f"점수 기록 추천: {best_row['name']} {best_row['score']}점"
        primary_target = best_row["name"]
    else:
        best_row = None
        summary = "점수가 잘 안 나오는 턴입니다. 희생 칸으로 정리하는 편이 낫습니다."
        primary_target = None

    return {
        "keep_indices": [],
        "expected_value": round(best_row["utility"], 2) if best_row else 0.0,
        "dice_recommendations": [],
        "message": primary_target or "점수 기록 단계",
        "breakdown": display_rows,
        "strategy_mode": mode,
        "primary_target": primary_target,
        "summary": summary,
        "stage": "score",
    }

@lru_cache(maxsize=4096)
def _solve_best_move_cached(dice_key, rolls_left, open_categories, mode, scorecard_tuple):
    dice = list(dice_key)
    scorecard = list(scorecard_tuple)
    open_categories = tuple(sorted(set(open_categories)))
    dice_tuple = tuple(sorted(dice))
    yacht_bonus_available = _has_yacht_bonus(scorecard)

    if rolls_left == 0:
        return _build_score_stage_advice(dice, scorecard, open_categories, mode)

    def evaluate_keep_transition(kept_tuple, rerolls_remaining, state_solver):
        reroll_count = 5 - len(kept_tuple)
        total = 0.0
        for outcome, prob in get_outcomes_probs(reroll_count):
            next_dice = tuple(sorted(kept_tuple + tuple(outcome)))
            total += prob * state_solver(next_dice, rerolls_remaining - 1)
        return total

    @lru_cache(maxsize=None)
    def terminal_best_utility(state_dice):
        best_key = None
        best_utility = float('-inf')
        for category_idx in open_categories:
            row = _score_stage_category_advice(list(state_dice), scorecard, category_idx, mode)
            row_key = (
                row["utility"],
                row["score"],
                -SACRIFICE_PRIORITY.get(row["name"], 99),
            )
            if best_key is None or row_key > best_key:
                best_key = row_key
                best_utility = row["utility"]
        return best_utility

    @lru_cache(maxsize=None)
    def exact_turn_value(state_dice, rerolls_remaining):
        if rerolls_remaining == 0:
            return terminal_best_utility(state_dice)

        best_value = float('-inf')
        for kept_tuple in get_keep_options(state_dice):
            value = evaluate_keep_transition(kept_tuple, rerolls_remaining, exact_turn_value)
            if value > best_value:
                best_value = value
        return best_value

    @lru_cache(maxsize=None)
    def target_success_value(state_dice, rerolls_remaining, category_idx):
        if rerolls_remaining == 0:
            if category_idx == CATS['Yacht'] and yacht_bonus_available and CATS['Yacht'] not in open_categories:
                return 1.0 if _can_cash_yacht_bonus(state_dice, open_categories, scorecard) else 0.0
            return 1.0 if calc_score(state_dice, category_idx) > 0 else 0.0

        best_value = 0.0
        for kept_tuple in get_keep_options(state_dice):
            value = evaluate_keep_transition(
                kept_tuple,
                rerolls_remaining,
                lambda next_dice, next_rolls: target_success_value(next_dice, next_rolls, category_idx),
            )
            if value > best_value:
                best_value = value
        return best_value

    @lru_cache(maxsize=None)
    def target_score_value(state_dice, rerolls_remaining, category_idx):
        if rerolls_remaining == 0:
            return float(calc_score(state_dice, category_idx))

        best_value = 0.0
        for kept_tuple in get_keep_options(state_dice):
            value = evaluate_keep_transition(
                kept_tuple,
                rerolls_remaining,
                lambda next_dice, next_rolls: target_score_value(next_dice, next_rolls, category_idx),
            )
            if value > best_value:
                best_value = value
        return best_value

    def _terminal_target_hit(state_dice, category_idx):
        if category_idx == CATS['Yacht'] and yacht_bonus_available and CATS['Yacht'] not in open_categories:
            return _can_cash_yacht_bonus(state_dice, open_categories, scorecard)
        return calc_score(state_dice, category_idx) > 0

    keep_action_values = []
    keep_ev_map = {}
    best_ev = float('-inf')
    for kept_tuple in get_keep_options(dice_tuple):
        value = evaluate_keep_transition(kept_tuple, rolls_left, exact_turn_value)
        keep_action_values.append((kept_tuple, value))
        keep_ev_map[kept_tuple] = value
        if value > best_ev:
            best_ev = value

    hand_cats = ['Yacht', '4 of a Kind', 'Full House', 'Large Straight', 'Small Straight']
    hand_priority = {'Yacht': 5, 'Large Straight': 4, 'Full House': 3, '4 of a Kind': 2, 'Small Straight': 1}
    hand_targets = []
    best_hand_moves = []

    for cat_name in hand_cats:
        cat_idx = CATS[cat_name]
        yacht_bonus_target = cat_name == 'Yacht' and yacht_bonus_available and cat_idx not in open_categories
        if cat_idx not in open_categories and not yacht_bonus_target:
            continue
        display_name = 'Yacht Bonus' if yacht_bonus_target else cat_name
        hand_targets.append({
            "name": display_name,
            "internal_name": cat_name,
            "category_idx": cat_idx,
            "bonus_active": yacht_bonus_target,
            "priority": hand_priority[cat_name],
        })

        action_rows = []
        for kept_tuple in get_keep_options(dice_tuple):
            success_prob = evaluate_keep_transition(
                kept_tuple,
                rolls_left,
                lambda next_dice, next_rolls: target_success_value(next_dice, next_rolls, cat_idx),
            )
            expected_score = 0.0
            if cat_name == '4 of a Kind':
                expected_score = evaluate_keep_transition(
                    kept_tuple,
                    rolls_left,
                    lambda next_dice, next_rolls: target_score_value(next_dice, next_rolls, cat_idx),
                )
            action_rows.append({
                "kept_tuple": kept_tuple,
                "prob": success_prob,
                "expected_score": expected_score,
            })

        max_prob = max((row["prob"] for row in action_rows), default=0.0)
        if max_prob <= EPS:
            continue

        tie_rows = [row for row in action_rows if abs(row["prob"] - max_prob) <= EPS]
        best_keep_for_cat = _choose_target_keep(cat_name, [row["kept_tuple"] for row in tie_rows])
        selected_row = next(row for row in tie_rows if row["kept_tuple"] == best_keep_for_cat)
        conditional_ev = selected_row["expected_score"] / max_prob if cat_name == '4 of a Kind' and max_prob > EPS else 0.0

        best_hand_moves.append({
            "name": display_name,
            "internal_name": cat_name,
            "bonus_active": yacht_bonus_target,
            "category_idx": cat_idx,
            "prob": max_prob,
            "kept_tuple": best_keep_for_cat,
            "keep_indices": _kept_tuple_to_indices(dice, best_keep_for_cat),
            "priority": hand_priority[cat_name],
            "tie_values": list(_keep_values_desc(best_keep_for_cat)),
            "tie_keeps": [
                {
                    "keep_indices": _kept_tuple_to_indices(dice, row["kept_tuple"]),
                    "values": list(_keep_values_desc(row["kept_tuple"])),
                }
                for row in tie_rows
            ],
            "conditional_ev": conditional_ev,
        })

    cover_success_prob = None
    cover_fail_prob = None
    cover_target_rows = []
    cover_fallback = mode == 'cover' and not hand_targets

    if mode == 'cover' and hand_targets:
        @lru_cache(maxsize=None)
        def cover_target_bias(state_dice, rerolls_remaining, kept_tuple):
            rows = []
            for target in hand_targets:
                prob = evaluate_keep_transition(
                    kept_tuple,
                    rerolls_remaining,
                    lambda next_dice, next_rolls, idx=target["category_idx"]: target_success_value(next_dice, next_rolls, idx),
                )
                if prob <= EPS:
                    continue
                rows.append({
                    "name": target["name"],
                    "prob": prob,
                    "priority": target["priority"],
                })
            return _cover_upgrade_rank(rows)

        def terminal_cover_hit(state_dice):
            return any(_terminal_target_hit(state_dice, target["category_idx"]) for target in hand_targets)

        @lru_cache(maxsize=None)
        def cover_success_value(state_dice, rerolls_remaining):
            if rerolls_remaining == 0:
                return 1.0 if terminal_cover_hit(state_dice) else 0.0
            return cover_best_action(state_dice, rerolls_remaining)[1]

        @lru_cache(maxsize=None)
        def cover_best_action(state_dice, rerolls_remaining):
            if rerolls_remaining == 0:
                return ((), 1.0 if terminal_cover_hit(state_dice) else 0.0)

            best_value = float('-inf')
            tied_keeps = []
            for kept_tuple in get_keep_options(state_dice):
                value = evaluate_keep_transition(kept_tuple, rerolls_remaining, cover_success_value)
                if value > best_value + EPS:
                    best_value = value
                    tied_keeps = [kept_tuple]
                elif abs(value - best_value) <= EPS:
                    tied_keeps.append(kept_tuple)

            best_keep = max(
                tied_keeps,
                key=lambda kept_tuple: (
                    cover_target_bias(state_dice, rerolls_remaining, kept_tuple),
                    len(kept_tuple),
                    _keep_values_desc(kept_tuple),
                ),
            )
            return (best_keep, best_value)

        @lru_cache(maxsize=None)
        def cover_policy_target_prob(state_dice, rerolls_remaining, category_idx):
            if rerolls_remaining == 0:
                return 1.0 if _terminal_target_hit(state_dice, category_idx) else 0.0
            kept_tuple, _ = cover_best_action(state_dice, rerolls_remaining)
            return evaluate_keep_transition(
                kept_tuple,
                rerolls_remaining,
                lambda next_dice, next_rolls: cover_policy_target_prob(next_dice, next_rolls, category_idx),
            )

        best_keep_tuple, cover_success_prob = cover_best_action(dice_tuple, rolls_left)
        cover_fail_prob = max(0.0, 1.0 - cover_success_prob)

        for target in hand_targets:
            prob = cover_policy_target_prob(dice_tuple, rolls_left, target["category_idx"])
            if prob <= EPS:
                continue
            cover_target_rows.append({
                "name": target["name"],
                "internal_name": target["internal_name"],
                "bonus_active": target["bonus_active"],
                "prob": prob,
                "priority": target["priority"],
            })

        cover_target_rows.sort(
            key=lambda row: (row["prob"], row["priority"], _hand_score_hint(row["name"], row)),
            reverse=True,
        )
    elif best_hand_moves:
        best_focus_move = max(best_hand_moves, key=lambda move: _mode_rank(move, mode))
        best_keep_tuple = best_focus_move["kept_tuple"]
    else:
        best_general_keeps = [kept for kept, value in keep_action_values if abs(value - best_ev) <= EPS]
        best_keep_tuple = _choose_general_keep(best_general_keeps)

    chosen_ev = keep_ev_map.get(best_keep_tuple, best_ev)
    best_keep_indices = _kept_tuple_to_indices(dice, best_keep_tuple)

    if mode == 'cover' and hand_targets:
        kept_vals = [str(dice[i]) for i in sorted(best_keep_indices)]
        keep_label = f"[{', '.join(kept_vals)}] keep" if kept_vals else "모두 굴리기"
        covered_names = [row["name"] for row in cover_target_rows[:3]]
        covered_str = " / ".join(covered_names) if covered_names else "열린 하단 족보"
        breakdown = [
            {
                "name": "핸드 하나 이상 성공",
                "prob": cover_success_prob,
                "meter": cover_success_prob,
                "val_str": f"{cover_success_prob * 100:.2f}%",
                "type": "cover",
                "keep_str": f"{keep_label} → {covered_str} 중 하나 이상",
                "keep_indices": best_keep_indices,
                "reason": f"겹치는 족보까지 한 번에 계산한 exact union 확률입니다.",
            },
            {
                "name": "전부 실패",
                "prob": cover_fail_prob,
                "meter": cover_fail_prob,
                "val_str": f"{cover_fail_prob * 100:.2f}%",
                "type": "risk",
                "keep_str": f"{keep_label} → 이번 턴에 하단 족보를 하나도 못 먹는 확률",
                "keep_indices": best_keep_indices,
                "reason": "독립 가정이 아니라 위 확률의 여집합으로 계산했습니다.",
            },
        ]

        for row in cover_target_rows[:3]:
            breakdown.append({
                "name": row["name"],
                "prob": row["prob"],
                "meter": row["prob"],
                "val_str": f"{row['prob'] * 100:.2f}%",
                "type": "hand",
                "keep_str": f"{keep_label} → 커버 경로에서 함께 열리는 후보",
                "keep_indices": best_keep_indices,
                "reason": _build_reason(row["name"], row["prob"], mode),
            })

        dice_recommendations = []
        for idx in range(5):
            action = "keep" if idx in best_keep_indices else "reroll"
            dice_recommendations.append({
                "index": idx,
                "value": dice[idx],
                "action": action,
                "confidence": 100
            })

        rec_msg = "모두 굴리기" if not best_keep_indices else f"[{', '.join(kept_vals)}] Keep (커버 플레이)"
        summary = f"커버 플레이: 핸드 하나 이상 {cover_success_prob * 100:.2f}%, 전부 실패 {cover_fail_prob * 100:.2f}%"

        return {
            "keep_indices": best_keep_indices,
            "expected_value": round(chosen_ev, 2),
            "dice_recommendations": dice_recommendations,
            "message": rec_msg,
            "breakdown": breakdown,
            "strategy_mode": mode,
            "primary_target": "핸드 하나 이상 성공",
            "summary": summary,
            "stage": "roll",
            "cover_success_prob": round(cover_success_prob, 6),
            "cover_fail_prob": round(cover_fail_prob, 6),
        }

    breakdown = []
    hand_cats_display = ['4 of a Kind', 'Full House', 'Small Straight', 'Large Straight', 'Yacht']

    for cat_name in hand_cats_display:
        cat_idx = CATS[cat_name]
        yacht_bonus_target = cat_name == 'Yacht' and yacht_bonus_available and cat_idx not in open_categories
        if cat_idx not in open_categories and not yacht_bonus_target:
            continue

        same_cat_moves = [move for move in best_hand_moves if move.get("internal_name") == cat_name]
        if not same_cat_moves:
            keep_str = "Keep 후보 없음: 다시 돌리기" if len(set(dice)) == 5 and cat_name in ('Yacht', '4 of a Kind', 'Full House') else "불가능"
            breakdown.append({
                "name": "Yacht Bonus" if yacht_bonus_target else cat_name,
                "prob": 0.0,
                "val_str": "",
                "type": "hand",
                "keep_str": keep_str,
                "keep_indices": [],
                "reason": "현재 턴에는 이 족보를 현실적으로 노리기 어렵습니다."
            })
            continue

        move = same_cat_moves[0]
        if move["prob"] == 0:
            breakdown.append({
                "name": move["name"],
                "prob": 0.0,
                "val_str": "",
                "type": "hand",
                "keep_str": "불가능",
                "keep_indices": [],
                "reason": "이번 상태에선 완성 경로가 없습니다."
            })
            continue

        if cat_name == '4 of a Kind':
            keep_vals = [str(dice[i]) for i in sorted(move["keep_indices"])]
            keep_str = f"[{', '.join(keep_vals)}]" if keep_vals else "모두 굴리기"
            keep_str = f"{keep_str} keep → 성공시 평균 {round(move.get('conditional_ev', 0), 1)}점"
            breakdown.append({
                "name": move["name"],
                "prob": move["prob"],
                "val_str": f"{move['prob'] * 100:.2f}%",
                "type": "hand",
                "keep_str": keep_str,
                "keep_indices": move["keep_indices"],
                "reason": _build_reason(move["name"], move["prob"], mode)
            })
            continue

        tie_keeps = move.get("tie_keeps") or []
        if cat_name == 'Yacht':
            keep_vals = [str(dice[i]) for i in sorted(move["keep_indices"])]
            keep_str = f"[{', '.join(keep_vals)}]" if keep_vals else "모두 굴리기"
            final_keep = keep_str if keep_str == "모두 굴리기" else f"{keep_str} keep"
            score_str = "Yacht Bonus +100 발동" if move.get("bonus_active") else "50점 (확정)"
            breakdown.append({
                "name": move["name"],
                "prob": move["prob"],
                "val_str": f"{move['prob'] * 100:.2f}%",
                "type": "hand",
                "keep_str": f"{final_keep} → {score_str}",
                "keep_indices": move["keep_indices"],
                "reason": _build_reason(move["name"], move["prob"], mode)
            })
            continue

        if len(tie_keeps) > 1:
            normalized = []
            for candidate in tie_keeps:
                values = [dice[i] for i in sorted(candidate["keep_indices"])]
                normalized.append((tuple(sorted(values, reverse=True)), len(values)))

            unique_values = {}
            for values, value_len in normalized:
                if values not in unique_values:
                    unique_values[values] = value_len

            if cat_name in ('Small Straight', 'Large Straight'):
                min_len = min((value_len for (_, value_len) in unique_values.items()), default=0)
                display = [values for values, value_len in unique_values.items() if value_len == min_len]
                display.sort(reverse=True)
                display = display[:1]
            elif cat_name == 'Full House' and tuple() in unique_values:
                display = [tuple()]
            else:
                display = sorted(unique_values.keys(), reverse=True)[:3]

            keep_labels = [f"[{', '.join(map(str, values))}]" if values else "모두 굴리기" for values in display]
            keep_str = keep_labels[0] if len(keep_labels) == 1 else f"Keep 후보: {', '.join(keep_labels)}"
        else:
            keep_vals = [str(dice[i]) for i in sorted(move["keep_indices"])]
            keep_str = f"[{', '.join(keep_vals)}]" if keep_vals else "모두 굴리기"

        if cat_name == 'Large Straight':
            score_str = "30점 (확정)"
        elif cat_name == 'Small Straight':
            score_str = "15점 (확정)"
        else:
            score_str = "합계 점수"

        keep_prefix = keep_str if keep_str in ("모두 굴리기",) or "Keep 후보" in keep_str else f"{keep_str} keep"
        breakdown.append({
            "name": move["name"],
            "prob": move["prob"],
            "val_str": f"{move['prob'] * 100:.2f}%",
            "type": "hand",
            "keep_str": f"{keep_prefix} → {score_str}",
            "keep_indices": move["keep_indices"],
            "reason": _build_reason(move["name"], move["prob"], mode)
        })

    hand_rows = [row for row in breakdown if row.get("type") == "hand"]
    all_hands_filled = (
        all(CATS[name] not in open_categories for name in ['4 of a Kind', 'Full House', 'Small Straight', 'Large Straight'])
        and (CATS['Yacht'] not in open_categories and not yacht_bonus_available)
    )

    if (hand_rows and all(row.get("prob") == 0 for row in hand_rows)) or all_hands_filled:
        upper_cats = [CATS['Ones'], CATS['Twos'], CATS['Threes'], CATS['Fours'], CATS['Fives'], CATS['Sixes']]
        upper_names = ['Ones', 'Twos', 'Threes', 'Fours', 'Fives', 'Sixes']

        for idx, (cat_val, cat_name) in enumerate(zip(upper_cats, upper_names)):
            if cat_val not in open_categories:
                continue

            target_val = idx + 1
            current_count = dice.count(target_val)
            reroll_count = 5 - current_count
            prob_get_more = 1.0 if reroll_count == 0 else 1.0 - ((5.0 / 6.0) ** reroll_count)
            josa = "이" if target_val in [1, 3, 6] else "가"

            breakdown.append({
                "name": cat_name,
                "prob": prob_get_more,
                "val_str": f"{prob_get_more * 100:.2f}%",
                "type": "upper",
                "keep_str": f"현재 나온 {target_val}들을 모두 Keep → {target_val}{josa} 적어도 하나 더 뜰 확률",
                "keep_indices": [i for i, value in enumerate(dice) if value == target_val],
                "reason": f"안전하게 상단 점수를 쌓을 수 있는 확률 {prob_get_more * 100:.1f}%"
            })

    matching_rows = [
        row for row in breakdown
        if row.get("keep_indices") == best_keep_indices and row.get("keep_indices")
    ]

    best_row = None
    if matching_rows:
        hand_matches = [row for row in matching_rows if row.get("type") == "hand"]
        if hand_matches:
            best_row = max(
                hand_matches,
                key=lambda row: _mode_rank({
                    "name": row["name"],
                    "prob": row.get("prob", 0),
                    "priority": hand_priority.get(row["name"], 0),
                    "tie_values": _keep_values_desc(tuple(dice[i] for i in row.get("keep_indices", []))),
                }, mode)
            )
        else:
            best_row = max(matching_rows, key=lambda row: (row.get("prob", 0), row.get("name", "")))

    straight_upgrade = None
    if mode == 'focused' and best_row and best_row.get("name") == "Small Straight" and CATS['Large Straight'] in open_categories:
        small_prob_for_keep = evaluate_keep_transition(
            best_keep_tuple,
            rolls_left,
            lambda next_dice, next_rolls: target_success_value(next_dice, next_rolls, CATS['Small Straight']),
        )
        large_prob_for_keep = evaluate_keep_transition(
            best_keep_tuple,
            rolls_left,
            lambda next_dice, next_rolls: target_success_value(next_dice, next_rolls, CATS['Large Straight']),
        )
        if small_prob_for_keep >= 1.0 - EPS and large_prob_for_keep > EPS:
            straight_upgrade = {
                "name": "Large Straight",
                "prob": large_prob_for_keep,
                "val_str": f"{large_prob_for_keep * 100:.2f}%",
                "keep_indices": best_keep_indices,
                "reason": f"Large Straight {large_prob_for_keep * 100:.1f}%를 노리되, 실패해도 Small Straight는 유지됩니다.",
            }
    explaining_row = straight_upgrade or (best_row if best_row and (mode == 'focused' or best_row.get("prob", 0) >= 0.05) else None)
    kept_vals = [str(dice[i]) for i in sorted(best_keep_indices)]
    rec_msg = "모두 굴리기"
    if best_keep_indices:
        rec_msg = f"[{', '.join(kept_vals)}] Keep"
        if straight_upgrade:
            rec_msg += " (Large Straight 업그레이드)"
        elif explaining_row and explaining_row.get("name") and not cover_fallback:
            rec_msg += f" ({explaining_row['name']} 노리기)"

    style_label = "집중 공략" if mode != 'cover' else "커버 플레이"
    if cover_fallback and best_keep_indices:
        summary = f"{style_label}: 커버 대상이 없어 일반 추천으로 전환, [{', '.join(kept_vals)}] keep, 기대값 {chosen_ev:.2f}"
    elif cover_fallback:
        summary = f"{style_label}: 커버 대상이 없어 일반 추천으로 전환, 기대값 {chosen_ev:.2f}"
    elif straight_upgrade:
        summary = f"{style_label} 추천: Large Straight {straight_upgrade['val_str']}, 실패해도 Small Straight 유지"
    elif explaining_row:
        summary = _build_summary(explaining_row, mode)
    elif best_keep_indices:
        summary = f"{style_label} 추천: [{', '.join(kept_vals)}] keep, 기대값 {chosen_ev:.2f}"
    else:
        summary = f"{style_label} 추천: 모두 굴리기, 기대값 {chosen_ev:.2f}"

    dice_recommendations = []
    for idx in range(5):
        action = "keep" if idx in best_keep_indices else "reroll"
        dice_recommendations.append({
            "index": idx,
            "value": dice[idx],
            "action": action,
            "confidence": 100
        })

    return {
        "keep_indices": best_keep_indices,
        "expected_value": round(chosen_ev, 2),
        "dice_recommendations": dice_recommendations,
        "message": rec_msg,
        "breakdown": breakdown,
        "strategy_mode": mode,
        "primary_target": explaining_row["name"] if explaining_row else None,
        "summary": summary,
        "stage": "roll",
    }

def solve_best_move(dice, rolls_left, open_categories, strategy_mode='focused', scorecard=None):
    mode = _normalize_strategy_mode(strategy_mode)
    dice_key = tuple(int(v) for v in dice)
    try:
        rolls_left = int(rolls_left)
    except (TypeError, ValueError):
        rolls_left = 0
    normalized_open_categories = []
    for idx in open_categories:
        try:
            cat_idx = int(idx)
        except (TypeError, ValueError):
            continue
        if 0 <= cat_idx < 12:
            normalized_open_categories.append(cat_idx)
    result = _solve_best_move_cached(
        dice_key,
        rolls_left,
        tuple(sorted(set(normalized_open_categories))),
        mode,
        _scorecard_to_tuple(scorecard),
    )
    return deepcopy(result)

def get_solver_cache_info():
    return _solve_best_move_cached.cache_info()

def clear_solver_cache():
    _solve_best_move_cached.cache_clear()
