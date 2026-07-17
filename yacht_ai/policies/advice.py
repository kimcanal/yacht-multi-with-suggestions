from functools import lru_cache

from yacht_core.constants import (
    CATEGORY_CLOSING_COST,
    CATEGORY_NAMES,
    CATS,
    CHOICE_HIGH_SCORE_THRESHOLD,
    CHOICE_REBALANCE_BASE_PENALTY,
    CHOICE_REBALANCE_PER_POINT,
    CHOICE_REBALANCE_SCORE_GAP,
    CHOICE_REBALANCE_UTILITY_GAP,
    CHOICE_UTILITY_BONUS_HIGH_COVER,
    CHOICE_UTILITY_BONUS_HIGH_FOCUSED,
    CHOICE_UTILITY_BONUS_LOW,
    DECISION_ROW_EV_SCALE,
    DECISION_ROW_METER_FLOOR,
    EPS,
    FOCUSED_HAND_PRIORITY,
    FOUR_KIND_UTILITY_BONUS_COVER,
    FOUR_KIND_UTILITY_BONUS_FOCUSED,
    FOUR_KIND_UTILITY_PENALTY,
    FRESH_TURN_CATEGORY_EV,
    FRESH_TURN_CATEGORY_HIT_RATE,
    FULL_HOUSE_UTILITY_BONUS_COVER,
    FULL_HOUSE_UTILITY_BONUS_FOCUSED,
    FULL_HOUSE_UTILITY_PENALTY,
    FUTURE_CATEGORY_WEIGHT,
    HAND_FIXED_SCORES,
    LARGE_STRAIGHT_UTILITY_BONUS,
    LONG_TERM_PRESSURE_SAVED_THRESHOLD,
    LONG_TERM_PRESSURE_THRESHOLD,
    LONG_TERM_QUALITY_GAP_HIGH,
    PRESSURE_INCREMENT_CHOICE,
    PRESSURE_INCREMENT_FOUR_KIND,
    PRESSURE_INCREMENT_FULL_HOUSE,
    PRESSURE_INCREMENT_LARGE_STRAIGHT,
    PRESSURE_INCREMENT_SMALL_STRAIGHT,
    PRESSURE_INCREMENT_YACHT,
    PRESSURE_UPPER_DONE_MULT,
    PRESSURE_YACHT_BONUS_CHOICE_MULT,
    PRESSURE_YACHT_BONUS_OTHER_MULT,
    QUALITY_BONUS_MAX,
    QUALITY_BONUS_MIN,
    QUALITY_GAP_METER_SCALE,
    SACRIFICE_BONUS_DROP_THRESHOLD,
    SACRIFICE_PRIORITY,
    SCORE_ROW_UTILITY_SCALE,
    SCORE_STAGE_COMPLETED_HAND_GUARD_MARGIN,
    SCORE_STAGE_COMPLETED_HAND_THRESHOLDS,
    SCORE_STAGE_LOW_POSITIVE_SACRIFICE_MARGIN,
    SCORE_STAGE_LOW_POSITIVE_SACRIFICE_MAX_SCORE,
    SCORE_STAGE_PRESSURE_RELIEF,
    SCORE_STAGE_QUALITY_WEIGHT,
    SCORE_STAGE_UPPER_DUMP_MAX_COST,
    SCORE_STAGE_UPPER_DUMP_MIN_FACE,
    SCORE_STAGE_UPPER_DUMP_SACRIFICE_COST,
    SCORE_STAGE_UPPER_DUMP_SPECIALTY_MARGIN,
    SCORE_STAGE_UPPER_DUMP_TARGET_COUNT,
    SMALL_STRAIGHT_UTILITY_BONUS,
    STRAIGHT_UTILITY_PENALTY,
    UPPER_BONUS_FACE2_MULT_COVER,
    UPPER_BONUS_FACE2_MULT_FOCUSED,
    UPPER_BONUS_FACE_MULT_COVER,
    UPPER_BONUS_FACE_MULT_FOCUSED,
    UPPER_BONUS_PROGRESS_WEIGHT,
    UPPER_BONUS_VALUE,
    UPPER_CAT_NAMES,
    UPPER_FRESH_COUNT_PROBS,
    YACHT_BONUS_CASH_IN,
    YACHT_UTILITY_BONUS,
    YACHT_UTILITY_PENALTY,
)
from yacht_core.scoring import calc_score, has_yacht_bonus


def normalize_strategy_mode(strategy_mode):
    if strategy_mode in ("focused", "cover"):
        return strategy_mode
    if strategy_mode in ("safe", "aggressive"):
        return "focused"
    return "focused"


def _straight_keep_rank(kept_tuple):
    return (-len(kept_tuple), tuple(sorted(kept_tuple, reverse=True)))


def _default_keep_rank(kept_tuple):
    return (len(kept_tuple), tuple(sorted(kept_tuple, reverse=True)))


def choose_target_keep(cat_name, kept_tuples):
    if not kept_tuples:
        return ()
    if cat_name in ("Small Straight", "Large Straight"):
        return max(kept_tuples, key=_straight_keep_rank)
    if cat_name == "Full House" and () in kept_tuples:
        return ()
    return max(kept_tuples, key=_default_keep_rank)


def choose_general_keep(kept_tuples):
    if not kept_tuples:
        return ()
    return max(kept_tuples, key=_default_keep_rank)


def hand_score_hint(cat_name, move):
    if cat_name in HAND_FIXED_SCORES:
        return HAND_FIXED_SCORES[cat_name]
    if cat_name == "Full House":
        return 22
    if cat_name == "4 of a Kind":
        return int(round(move.get("conditional_ev", 20)))
    return 0


def build_reason(cat_name, prob, mode):
    pct = f"{prob * 100:.1f}%"
    if mode == "cover":
        return f"커버 참고: {cat_name}까지 이어질 확률 {pct}"
    if prob >= 0.75:
        return f"집중 공략: {cat_name} 성공 확률 {pct}"
    if prob >= 0.35:
        return f"집중 공략: {cat_name} 완성 확률 {pct}"
    return f"집중 공략: {cat_name} 도달 확률 {pct}"


def build_summary(best_item, mode):
    if not best_item:
        return "추천 없음: 다시 굴리며 다음 기회를 보는 편이 좋습니다."
    if best_item.get("summary_text"):
        return best_item["summary_text"]
    style_label = "집중 공략" if mode != "cover" else "커버 플레이"
    if best_item.get("type") == "upper":
        return f"{style_label} 추천: {best_item['name']} {best_item['val_str']}"
    return f"{style_label} 추천: {best_item['name']} 확률 {best_item['val_str']}"


def build_recommendation_context_row(mode, chosen_ev, explaining_row, straight_upgrade, keep_indices, stop_now_target, stop_gain):
    if not keep_indices or not explaining_row:
        return None

    reason = "현재 턴 점수와 남은 점수판 가치를 함께 반영한 추천입니다."
    if straight_upgrade:
        reason = (
            f"Large Straight {straight_upgrade['val_str']}를 노리면서 실패해도 Small Straight를 유지합니다."
        )
    elif explaining_row.get("type") == "upper":
        reason = f"{explaining_row['name']} 쪽이 Upper Bonus 페이스를 가장 좋게 끌어올립니다."
    elif mode == "focused" and explaining_row.get("type") == "hand":
        reason = (
            f"focused 모드에서는 {explaining_row['name']} 완성 경로를 더 높게 두고, "
            "이 keep이 그 확률을 가장 잘 살립니다."
        )
    elif explaining_row.get("name"):
        reason = f"{explaining_row['name']} 쪽이 이번 턴 기준으로 가장 납득되는 선택입니다."

    if stop_now_target and stop_gain is not None:
        if stop_gain >= 0:
            reason += f" 지금 {stop_now_target}로 바로 적는 선택보다도 평가가 {stop_gain:.2f}점 높습니다."
        else:
            reason += f" 다만 지금 {stop_now_target}로 적는 쪽이 평가는 {abs(stop_gain):.2f}점 높습니다."

    return {
        "name": "추천 근거",
        "prob": 0.0,
        "meter": min(1.0, max(DECISION_ROW_METER_FLOOR, abs(chosen_ev) / DECISION_ROW_EV_SCALE)),
        "val_str": f"평가 {chosen_ev:.2f}",
        "type": "decision",
        "keep_str": "현재 턴 점수 + 남은 칸 가치 함께 반영",
        "keep_indices": keep_indices,
        "reason": reason,
    }


def mode_rank(move, mode):
    score_hint = hand_score_hint(move["name"], move)
    prob = move.get("prob", 0)
    focused_name = move.get("name")
    focused_priority = FOCUSED_HAND_PRIORITY.get(focused_name, move.get("priority", 0))
    return (prob, score_hint, focused_priority, move.get("tie_values", []))


def cover_upgrade_rank(target_rows):
    if not target_rows:
        return (0.0, 0.0, 0.0)

    weighted_prob = 0.0
    best_prob = 0.0
    best_hint = 0.0
    for row in target_rows:
        hint = hand_score_hint(row["name"], row)
        prob = row.get("prob", 0.0)
        weighted_prob += hint * prob
        if prob > best_prob or (abs(prob - best_prob) <= EPS and hint > best_hint):
            best_prob = prob
            best_hint = hint
    return (weighted_prob, best_prob, best_hint)


def normalize_scorecard(scorecard):
    base = [None] * 12
    if isinstance(scorecard, tuple) and len(scorecard) == 12:
        return list(scorecard)
    if not isinstance(scorecard, list):
        return base
    for idx, value in enumerate(scorecard[:12]):
        base[idx] = value
    return base


def scorecard_to_tuple(scorecard):
    if isinstance(scorecard, tuple) and len(scorecard) == 12:
        return scorecard
    return tuple(normalize_scorecard(scorecard))


def score_stage_upper_bonus_push(face, count, current_upper, score, mode):
    projected_upper = current_upper + score
    bonus_delta = 35 if current_upper < 63 <= projected_upper else 0
    bonus_push = 0.0

    if current_upper < 63:
        progress = max(0, min(score, 63 - current_upper))
        bonus_push += progress * UPPER_BONUS_PROGRESS_WEIGHT
        if count >= 3:
            bonus_push += face * (UPPER_BONUS_FACE_MULT_FOCUSED if mode == "focused" else UPPER_BONUS_FACE_MULT_COVER)
        elif count == 2 and face >= 5:
            bonus_push += face * (UPPER_BONUS_FACE2_MULT_FOCUSED if mode == "focused" else UPPER_BONUS_FACE2_MULT_COVER)

    return bonus_push + bonus_delta, bonus_delta


def _upper_open_tuple(scorecard):
    return tuple(idx + 1 for idx, value in enumerate(scorecard[:6]) if value is None)


@lru_cache(maxsize=2048)
def _upper_bonus_probability(current_upper, open_faces):
    capped_upper = max(0, min(int(current_upper), 63))
    if capped_upper >= 63:
        return 1.0
    if not open_faces:
        return 0.0

    dist = {capped_upper: 1.0}
    for face in open_faces:
        next_dist = {}
        for subtotal, subtotal_prob in dist.items():
            for count, count_prob in UPPER_FRESH_COUNT_PROBS.items():
                next_total = min(63, subtotal + face * count)
                next_dist[next_total] = next_dist.get(next_total, 0.0) + (subtotal_prob * count_prob)
        dist = next_dist

    return sum(prob for total, prob in dist.items() if total >= 63)


@lru_cache(maxsize=4096)
def _upper_bonus_outlook_cached(scorecard_tuple):
    current_upper = sum((value or 0) for value in scorecard_tuple[:6])
    open_faces = _upper_open_tuple(scorecard_tuple)
    return (current_upper, open_faces, _upper_bonus_probability(current_upper, open_faces))


def upper_bonus_outlook(scorecard):
    current_upper, open_faces, bonus_prob = _upper_bonus_outlook_cached(scorecard_to_tuple(scorecard))
    return {
        "current_upper": current_upper,
        "open_faces": open_faces,
        "bonus_prob": bonus_prob,
    }


def projected_scorecard(scorecard, category_idx, score):
    next_scorecard = list(scorecard_to_tuple(scorecard))
    next_scorecard[category_idx] = score
    return tuple(next_scorecard)


@lru_cache(maxsize=4096)
def _scorecard_phase_weight_cached(scorecard_tuple):
    open_count = sum(1 for value in scorecard_tuple if value is None)
    if open_count <= 0:
        return 0.0
    return (open_count / 12.0) ** 0.85


def scorecard_phase_weight(scorecard):
    return _scorecard_phase_weight_cached(scorecard_to_tuple(scorecard))


@lru_cache(maxsize=4096)
def _remaining_state_value_cached(scorecard_tuple):
    phase_weight = _scorecard_phase_weight_cached(scorecard_tuple)
    open_names = [CATEGORY_NAMES[idx] for idx, value in enumerate(scorecard_tuple) if value is None]
    closing_value = sum(CATEGORY_CLOSING_COST.get(name, 0.0) for name in open_names) * phase_weight
    upper_value = UPPER_BONUS_VALUE * _upper_bonus_outlook_cached(scorecard_tuple)[2]
    return closing_value + upper_value


def remaining_state_value(scorecard):
    return _remaining_state_value_cached(scorecard_to_tuple(scorecard))


def score_stage_reference_score(category_idx, future_ev):
    if category_idx < 6 or category_idx == CATS["Choice"]:
        return max(1.0, future_ev)
    if category_idx == CATS["4 of a Kind"]:
        return 20.0
    if category_idx == CATS["Full House"]:
        return 20.0
    if category_idx == CATS["Small Straight"]:
        return 15.0
    if category_idx == CATS["Large Straight"]:
        return 30.0
    if category_idx == CATS["Yacht"]:
        return 50.0
    return max(1.0, future_ev)


@lru_cache(maxsize=8192)
def _score_stage_future_pressure_cached(scorecard_tuple, category_idx):
    name = CATEGORY_NAMES[category_idx]
    closing_cost = CATEGORY_CLOSING_COST.get(name, FRESH_TURN_CATEGORY_EV.get(name, 0.0))
    hit_rate = FRESH_TURN_CATEGORY_HIT_RATE.get(name, 0.0)
    open_count = sum(1 for value in scorecard_tuple if value is None)
    phase_weight = (open_count / 12.0) ** 0.85 if open_count > 0 else 0.0
    pressure = closing_cost * phase_weight * FUTURE_CATEGORY_WEIGHT

    if category_idx == CATS["Choice"]:
        pressure += PRESSURE_INCREMENT_CHOICE
    elif category_idx == CATS["Small Straight"]:
        pressure += PRESSURE_INCREMENT_SMALL_STRAIGHT
    elif category_idx == CATS["Large Straight"]:
        pressure += PRESSURE_INCREMENT_LARGE_STRAIGHT
    elif category_idx == CATS["Full House"]:
        pressure += PRESSURE_INCREMENT_FULL_HOUSE
    elif category_idx == CATS["4 of a Kind"]:
        pressure += PRESSURE_INCREMENT_FOUR_KIND
    elif category_idx == CATS["Yacht"]:
        pressure += PRESSURE_INCREMENT_YACHT

    if category_idx < 6:
        current_upper = sum((value or 0) for value in scorecard_tuple[:6])
        if current_upper >= 63:
            pressure *= PRESSURE_UPPER_DONE_MULT

    if has_yacht_bonus(scorecard_tuple) and category_idx != CATS["Yacht"]:
        pressure += hit_rate * (PRESSURE_YACHT_BONUS_CHOICE_MULT if category_idx == CATS["Choice"] else PRESSURE_YACHT_BONUS_OTHER_MULT)

    return max(0.0, pressure)


def score_stage_future_pressure(scorecard, category_idx):
    return _score_stage_future_pressure_cached(scorecard_to_tuple(scorecard), category_idx)


@lru_cache(maxsize=4096)
def _scorecard_context_cached(scorecard_tuple):
    upper_current, _open_faces, upper_bonus_prob = _upper_bonus_outlook_cached(scorecard_tuple)
    return {
        "current_upper": upper_current,
        "current_state_value": _remaining_state_value_cached(scorecard_tuple),
        "upper_bonus_prob": upper_bonus_prob,
        "yacht_bonus_available": has_yacht_bonus(scorecard_tuple),
        "future_pressures": tuple(
            _score_stage_future_pressure_cached(scorecard_tuple, category_idx) for category_idx in range(12)
        ),
    }


@lru_cache(maxsize=16384)
def _scorecard_transition_context_cached(scorecard_tuple, category_idx, score):
    next_scorecard = list(scorecard_tuple)
    next_scorecard[category_idx] = score
    next_scorecard = tuple(next_scorecard)
    upper_after_prob = _upper_bonus_outlook_cached(next_scorecard)[2]
    next_state_value = _remaining_state_value_cached(next_scorecard)
    return next_scorecard, next_state_value, upper_after_prob


def score_stage_long_term_profile(scorecard, category_idx, score, future_ev, base_future_pressure):
    phase_weight = scorecard_phase_weight(scorecard)
    reference_score = score_stage_reference_score(category_idx, future_ev)
    realization_ratio = 0.0
    if reference_score > EPS:
        realization_ratio = max(0.0, min(score / reference_score, 1.0))

    quality_gap = score - future_ev
    quality_bonus = quality_gap * phase_weight * SCORE_STAGE_QUALITY_WEIGHT
    quality_bonus = max(QUALITY_BONUS_MIN, min(QUALITY_BONUS_MAX, quality_bonus))

    future_pressure = max(0.0, base_future_pressure * (1.0 - (SCORE_STAGE_PRESSURE_RELIEF * realization_ratio)))
    future_pressure_saved = max(0.0, base_future_pressure - future_pressure)

    return {
        "reference_score": reference_score,
        "realization_ratio": realization_ratio,
        "quality_gap": quality_gap,
        "quality_bonus": quality_bonus,
        "future_pressure": future_pressure,
        "future_pressure_saved": future_pressure_saved,
        "long_term_delta": quality_bonus - future_pressure,
    }


def score_stage_long_term_note(row):
    score = row.get("score", 0.0)
    future_ev = row.get("future_ev", 0.0)
    quality_gap = row.get("quality_gap", 0.0)
    future_pressure = row.get("future_pressure", 0.0)
    future_pressure_saved = row.get("future_pressure_saved", 0.0)

    if score <= 0:
        if future_pressure >= LONG_TERM_PRESSURE_THRESHOLD:
            return f"지금 비우면 남은 점수판 가치 손실이 {future_pressure:.1f}점 수준이라 부담이 큽니다"
        return ""

    if quality_gap >= LONG_TERM_QUALITY_GAP_HIGH:
        return f"이 칸은 새 턴 기준 평균 {future_ev:.1f}점 안팎인데, 이번에 크게 잘 떠서 바로 확정하는 편이 좋습니다"
    if quality_gap <= -LONG_TERM_QUALITY_GAP_HIGH:
        return f"평균적으로는 {future_ev:.1f}점 정도 기대되는 칸이라 낮은 기록이지만, 다른 열린 칸 손실이 더 큽니다"
    if future_pressure_saved >= LONG_TERM_PRESSURE_SAVED_THRESHOLD:
        return f"이번 기록이 좋아 이 칸을 닫는 장기 부담도 {future_pressure_saved:.1f}점 정도 줄었습니다"
    return ""


def score_stage_sacrifice_reason(row):
    name = row["name"]
    closing_cost = row.get("closing_cost", row.get("future_ev", 0.0))
    category_idx = row.get("category_idx")
    before_bonus_prob = row.get("before_bonus_prob")
    after_bonus_prob = row.get("after_bonus_prob")
    bonus_drop = row.get("bonus_prob_drop", 0.0)

    if category_idx is not None and category_idx < 6 and bonus_drop >= SACRIFICE_BONUS_DROP_THRESHOLD:
        return (
            f"{name}를 비우면 Upper Bonus 가능성이 "
            f"{before_bonus_prob * 100:.1f}% → {after_bonus_prob * 100:.1f}%로 내려갑니다"
        )
    if name in ("Ones", "Twos"):
        return f"{name}는 장기 손실 추정이 {closing_cost:.1f}점 수준이라 희생 부담이 가장 낮은 편입니다"
    if name == "Yacht":
        return f"Yacht는 장기 손실 추정이 {closing_cost:.1f}점 수준이라 마지막 수단용 희생 후보입니다"
    if category_idx == CATS["Choice"]:
        return "Choice는 범용 칸이라 아깝지만, 이번 상태에선 다른 칸 손실이 더 커 보입니다"
    if category_idx in (CATS["Large Straight"], CATS["Small Straight"]):
        return f"{name}는 이번엔 포기지만, 다른 열린 칸 대비 손실이 덜한 편입니다"
    return f"현재 점수판 기준 {name}의 장기 손실 추정이 낮은 편이라 희생 후보로 둘 수 있습니다"


def score_stage_category_advice(
    dice,
    scorecard,
    category_idx,
    mode,
    score_value_mode="heuristic",
    endgame_value_table=None,
    learned_value_model=None,
    learned_value_max_mae=25.0,
    learned_value_min_turns=5,
):
    scorecard = scorecard_to_tuple(scorecard)
    scorecard_context = _scorecard_context_cached(scorecard)
    name = CATEGORY_NAMES[category_idx]
    score = calc_score(dice, category_idx)
    next_scorecard, next_state_value, upper_after_prob = _scorecard_transition_context_cached(scorecard, category_idx, score)
    current_state_value = scorecard_context["current_state_value"]
    utility = float(score)
    reason = f"즉시 {score}점"
    future_ev = FRESH_TURN_CATEGORY_EV.get(name, 0.0)
    closing_cost = CATEGORY_CLOSING_COST.get(name, future_ev)
    base_future_pressure = scorecard_context["future_pressures"][category_idx]
    long_term_profile = score_stage_long_term_profile(scorecard, category_idx, score, future_ev, base_future_pressure)
    future_pressure = long_term_profile["future_pressure"]
    upper_before_prob = scorecard_context["upper_bonus_prob"]
    bonus_prob_delta = upper_after_prob - upper_before_prob
    yacht_bonus_active = (
        category_idx != CATS["Yacht"]
        and score > 0
        and scorecard_context["yacht_bonus_available"]
        and calc_score(dice, CATS["Yacht"]) == 50
    )
    immediate_gain = float(score)
    if category_idx < 6 and scorecard_context["current_upper"] < 63 <= scorecard_context["current_upper"] + score:
        immediate_gain += UPPER_BONUS_VALUE
    if yacht_bonus_active:
        immediate_gain += YACHT_BONUS_CASH_IN

    exact_next_state_value = None
    exact_next_state_key = None
    if score_value_mode in ("value", "hybrid") and endgame_value_table is not None:
        exact_next_state_value, exact_next_state_key = endgame_value_table.lookup_scorecard(next_scorecard)
    learned_next_state_value = None
    if (
        score_value_mode == "hybrid"
        and exact_next_state_value is None
        and learned_value_model is not None
        and learned_value_model.is_usable(float(learned_value_max_mae))
        and sum(1 for value in next_scorecard if value is not None) >= int(learned_value_min_turns)
    ):
        learned_next_state_value = learned_value_model.predict_remaining(next_scorecard, mode)

    if category_idx < 6:
        face = category_idx + 1
        count = dice.count(face)
        current_upper = scorecard_context["current_upper"]
        bonus_push, bonus_delta = score_stage_upper_bonus_push(face, count, current_upper, score, mode)
        utility += bonus_push
        if bonus_delta:
            reason = "이번 기록으로 Upper Bonus +35를 바로 확보합니다"
        elif bonus_prob_delta >= 0.12:
            reason = (
                f"{name} {score}점으로 Upper Bonus 가능성이 "
                f"{upper_before_prob * 100:.1f}% → {upper_after_prob * 100:.1f}%로 올라갑니다"
            )
        elif count >= 3 and face >= 4:
            reason = f"{name} {score}점으로 상단 보너스 페이스를 강하게 유지합니다"
        elif count >= 3:
            reason = f"{name} {score}점으로 상단 점수를 안정적으로 쌓습니다"
        elif score > 0:
            reason = f"{name} {score}점으로 손실 없이 턴을 정리합니다"
        else:
            reason = f"{name}에 기록하면 0점 처리입니다"
    elif category_idx == CATS["Choice"]:
        if score >= CHOICE_HIGH_SCORE_THRESHOLD:
            utility += CHOICE_UTILITY_BONUS_HIGH_COVER if mode == "cover" else CHOICE_UTILITY_BONUS_HIGH_FOCUSED
            reason = f"즉시 {score}점으로 무난하게 착지할 수 있습니다"
        elif score > 0:
            utility += CHOICE_UTILITY_BONUS_LOW
            reason = f"Choice {score}점으로 이번 턴 손실을 줄입니다"
        else:
            reason = "Choice도 이번 턴엔 점수가 나지 않습니다"
    elif category_idx == CATS["4 of a Kind"]:
        if score > 0:
            utility += FOUR_KIND_UTILITY_BONUS_FOCUSED if mode == "focused" else FOUR_KIND_UTILITY_BONUS_COVER
            reason = f"4 of a Kind {score}점으로 하단 고점을 확보합니다"
        else:
            utility -= FOUR_KIND_UTILITY_PENALTY
            reason = "4 of a Kind에 적으면 0점입니다"
    elif category_idx == CATS["Full House"]:
        if score > 0:
            utility += FULL_HOUSE_UTILITY_BONUS_FOCUSED if mode == "focused" else FULL_HOUSE_UTILITY_BONUS_COVER
            reason = f"Full House {score}점으로 점수 효율이 좋습니다"
        else:
            utility -= FULL_HOUSE_UTILITY_PENALTY
            reason = "Full House에 적으면 0점입니다"
    elif category_idx == CATS["Small Straight"]:
        if score > 0:
            utility += SMALL_STRAIGHT_UTILITY_BONUS
            reason = "Small Straight 15점을 바로 확보합니다"
        else:
            utility -= STRAIGHT_UTILITY_PENALTY
            reason = "Small Straight에 적으면 0점입니다"
    elif category_idx == CATS["Large Straight"]:
        if score > 0:
            utility += LARGE_STRAIGHT_UTILITY_BONUS
            reason = "Large Straight 30점은 바로 챙길 가치가 큽니다"
        else:
            utility -= STRAIGHT_UTILITY_PENALTY
            reason = "Large Straight에 적으면 0점입니다"
    elif category_idx == CATS["Yacht"]:
        if score > 0:
            utility += YACHT_UTILITY_BONUS
            reason = "Yacht 50점은 바로 확정하는 편이 가장 좋습니다"
        else:
            utility -= YACHT_UTILITY_PENALTY
            reason = "Yacht는 이번 턴을 비우는 희생 칸 후보로만 보세요"

    if yacht_bonus_active:
        utility += YACHT_BONUS_CASH_IN
        reason = f"Yacht Bonus +100과 함께 {name} {score}점을 기록할 수 있습니다"

    utility += long_term_profile["quality_bonus"]
    utility += UPPER_BONUS_VALUE * bonus_prob_delta
    utility -= future_pressure
    utility_mode = "heuristic"
    if score_value_mode in ("value", "hybrid"):
        utility_mode = "heuristic_fallback"
    if exact_next_state_value is not None:
        utility = immediate_gain + exact_next_state_value
        utility_mode = "endgame_value"
    elif learned_next_state_value is not None:
        utility = immediate_gain + learned_next_state_value
        utility_mode = "learned_value"

    long_term_note = score_stage_long_term_note(
        {
            "score": score,
            "future_ev": future_ev,
            "quality_gap": long_term_profile["quality_gap"],
            "future_pressure": future_pressure,
            "future_pressure_saved": long_term_profile["future_pressure_saved"],
        }
    )

    return {
        "name": name,
        "category_idx": category_idx,
        "score": score,
        "utility": utility,
        "reason": reason,
        "future_ev": future_ev,
        "closing_cost": closing_cost,
        "base_future_pressure": base_future_pressure,
        "future_pressure": future_pressure,
        "future_pressure_saved": long_term_profile["future_pressure_saved"],
        "quality_gap": long_term_profile["quality_gap"],
        "quality_bonus": long_term_profile["quality_bonus"],
        "reference_score": long_term_profile["reference_score"],
        "realization_ratio": long_term_profile["realization_ratio"],
        "long_term_delta": long_term_profile["long_term_delta"],
        "long_term_note": long_term_note,
        "current_state_value": current_state_value,
        "next_state_value": next_state_value,
        "state_value_delta": next_state_value - current_state_value,
        "immediate_gain": immediate_gain,
        "utility_mode": utility_mode,
        "exact_next_state_value": exact_next_state_value,
        "exact_next_state_key": exact_next_state_key,
        "learned_next_state_value": learned_next_state_value,
        "learned_model_id": getattr(learned_value_model, "model_id", None),
        "learned_validation_mae": getattr(learned_value_model, "validation_mae", None),
        "before_bonus_prob": upper_before_prob,
        "after_bonus_prob": upper_after_prob,
        "bonus_prob_drop": max(0.0, upper_before_prob - upper_after_prob),
        "bonus_prob_delta": bonus_prob_delta,
    }


def _score_stage_sacrifice_key(row):
    sacrifice_pressure = row.get("future_pressure", 0.0) + (
        UPPER_BONUS_VALUE * row.get("bonus_prob_drop", 0.0)
    )
    return (
        row["score"],
        sacrifice_pressure,
        SACRIFICE_PRIORITY.get(row["name"], 99),
    )


def _rebalance_choice_score_stage(rows):
    choice_idx = CATS["Choice"]
    choice_row = next((row for row in rows if row["category_idx"] == choice_idx and row["score"] > 0), None)
    if not choice_row or choice_row["score"] >= 20:
        return

    specialty_thresholds = {
        CATS["4 of a Kind"]: 18,
        CATS["Full House"]: 16,
        CATS["Small Straight"]: 15,
        CATS["Large Straight"]: 30,
        CATS["Yacht"]: 50,
    }
    specialty_rows = [
        row
        for row in rows
        if row["category_idx"] in specialty_thresholds
        and row["score"] >= specialty_thresholds[row["category_idx"]]
    ]
    if not specialty_rows:
        return

    best_specialty = max(specialty_rows, key=lambda row: (row["utility"], row["score"]))
    choice_gap = choice_row["score"] - best_specialty["score"]
    if best_specialty["utility"] + CHOICE_REBALANCE_UTILITY_GAP < choice_row["utility"] and choice_gap >= CHOICE_REBALANCE_SCORE_GAP:
        return

    penalty = CHOICE_REBALANCE_BASE_PENALTY + max(0.0, (CHOICE_HIGH_SCORE_THRESHOLD - choice_row["score"]) * CHOICE_REBALANCE_PER_POINT)
    choice_row["utility"] -= penalty
    choice_row["reason"] = (
        f"Choice {choice_row['score']}점으로 손실은 줄이지만, "
        f"{best_specialty['name']}처럼 다시 만들기 어려운 족보를 우선 보는 편이 낫습니다"
    )


def _guard_completed_hand_score_stage(rows):
    completed_rows = [
        row
        for row in rows
        if row["category_idx"] in SCORE_STAGE_COMPLETED_HAND_THRESHOLDS
        and row["score"] >= SCORE_STAGE_COMPLETED_HAND_THRESHOLDS[row["category_idx"]]
    ]
    if not completed_rows:
        return

    best_completed = max(completed_rows, key=lambda row: (row["score"], row["utility"]))
    protected_utility = best_completed["utility"] - SCORE_STAGE_COMPLETED_HAND_GUARD_MARGIN
    for row in rows:
        if row["category_idx"] >= 6 or row["utility"] <= protected_utility:
            continue
        row["utility"] = protected_utility
        row["reason"] = (
            f"{row['reason']} 다만 {best_completed['name']} {best_completed['score']}점 확정이 떠 있어 "
            "상단 보너스 가산은 보정했습니다"
        )


def _low_positive_sacrifice_override(positive_rows, sacrifice_rows):
    if not positive_rows or not sacrifice_rows:
        return None

    best_positive = positive_rows[0]
    best_sacrifice = sacrifice_rows[0]
    if best_positive["score"] > SCORE_STAGE_LOW_POSITIVE_SACRIFICE_MAX_SCORE:
        return None
    if best_sacrifice["utility"] <= best_positive["utility"] + SCORE_STAGE_LOW_POSITIVE_SACRIFICE_MARGIN:
        return None
    return best_sacrifice


def _is_low_high_upper_score(row):
    category_idx = row.get("category_idx")
    if category_idx is None or category_idx >= 6:
        return False
    face = category_idx + 1
    if face < SCORE_STAGE_UPPER_DUMP_MIN_FACE or row["score"] <= 0:
        return False
    if row.get("immediate_gain", row["score"]) > row["score"]:
        return False
    if row.get("bonus_prob_drop", 0.0) < SACRIFICE_BONUS_DROP_THRESHOLD:
        return False
    return (row["score"] / face) < SCORE_STAGE_UPPER_DUMP_TARGET_COUNT


def _is_cheap_positive_dump(row):
    category_idx = row.get("category_idx")
    return category_idx is not None and category_idx <= CATS["Threes"] and row["score"] > 0


def _score_stage_dump_cost(row):
    cost = row.get("future_pressure", 0.0) + (
        UPPER_BONUS_VALUE * row.get("bonus_prob_drop", 0.0)
    ) - row["score"]
    if row["score"] <= 0:
        cost += SCORE_STAGE_UPPER_DUMP_SACRIFICE_COST
    return cost


def _has_competing_specialty_score(rows, low_upper_row):
    specialty_thresholds = {
        CATS["4 of a Kind"]: 18,
        CATS["Full House"]: 16,
        CATS["Small Straight"]: 15,
        CATS["Large Straight"]: 30,
        CATS["Yacht"]: 50,
    }
    protected_utility = low_upper_row["utility"] - SCORE_STAGE_UPPER_DUMP_SPECIALTY_MARGIN
    return any(
        row["category_idx"] in specialty_thresholds
        and row["score"] >= specialty_thresholds[row["category_idx"]]
        and row["utility"] >= protected_utility
        for row in rows
    )


def _low_high_upper_dump_override(positive_rows, sacrifice_rows):
    if not positive_rows:
        return None

    low_upper_row = positive_rows[0]
    if not _is_low_high_upper_score(low_upper_row):
        return None
    if _has_competing_specialty_score(positive_rows, low_upper_row):
        return None

    candidates = [
        row
        for row in positive_rows[1:]
        if _is_cheap_positive_dump(row)
    ] + list(sacrifice_rows)
    if not candidates:
        return None

    dump_row = min(
        candidates,
        key=lambda row: (
            _score_stage_dump_cost(row),
            SACRIFICE_PRIORITY.get(row["name"], 99),
        ),
    )
    if _score_stage_dump_cost(dump_row) > SCORE_STAGE_UPPER_DUMP_MAX_COST:
        return None

    dump_row["reason"] = (
        f"{dump_row['reason']} {low_upper_row['name']} {low_upper_row['score']}점은 아직 낮은 기록이라 "
        "더 싼 칸으로 턴을 정리해 고가치 상단 칸을 남깁니다"
    )
    return dump_row


def build_score_stage_advice(
    dice,
    scorecard,
    open_categories,
    mode,
    score_value_mode="heuristic",
    endgame_value_table=None,
    learned_value_model=None,
    learned_value_max_mae=25.0,
    learned_value_min_turns=5,
):
    scorecard = scorecard_to_tuple(scorecard)
    rows = [
        score_stage_category_advice(
            dice,
            scorecard,
            idx,
            mode,
            score_value_mode=score_value_mode,
            endgame_value_table=endgame_value_table,
            learned_value_model=learned_value_model,
            learned_value_max_mae=learned_value_max_mae,
            learned_value_min_turns=learned_value_min_turns,
        )
        for idx in open_categories
    ]
    value_hits = any(row.get("utility_mode") in ("endgame_value", "learned_value") for row in rows)
    if not value_hits:
        _rebalance_choice_score_stage(rows)
        _guard_completed_hand_score_stage(rows)
    ranked_rows = sorted(rows, key=lambda row: (row["utility"], row["score"]), reverse=True)
    positive_rows = [row for row in rows if row["score"] > 0]
    positive_rows.sort(key=lambda row: (row["utility"], row["score"]), reverse=True)

    sacrifice_rows = [row for row in rows if row["score"] == 0]
    if not sacrifice_rows:
        sacrifice_rows = sorted(rows, key=_score_stage_sacrifice_key)[:2]
    else:
        sacrifice_rows.sort(key=_score_stage_sacrifice_key)

    dump_override = None if value_hits else _low_high_upper_dump_override(positive_rows, sacrifice_rows)
    sacrifice_override = None
    if not value_hits and not dump_override:
        sacrifice_override = _low_positive_sacrifice_override(positive_rows, sacrifice_rows)

    display_rows = []
    if value_hits:
        score_display_rows = ranked_rows[:3]
    elif dump_override:
        score_display_rows = [dump_override] + [
            row for row in positive_rows[:2] if row is not dump_override
        ]
    elif sacrifice_override:
        score_display_rows = [sacrifice_override] + positive_rows[:2]
    else:
        score_display_rows = positive_rows[:3]
    for row in score_display_rows:
        reason = row["reason"]
        if row.get("long_term_note"):
            reason = f"{reason} {row['long_term_note']}"
        if row.get("utility_mode") == "endgame_value":
            reason = (
                f"{reason} 즉시 획득 {row.get('immediate_gain', row['score']):.1f}점 + "
                f"후속 exact V {row.get('exact_next_state_value', 0.0):.1f}점 기준입니다."
            )
        elif row.get("utility_mode") == "learned_value":
            reason = (
                f"{reason} 즉시 획득 {row.get('immediate_gain', row['score']):.1f}점 + "
                f"학습 V {row.get('learned_next_state_value', 0.0):.1f}점 기준입니다."
            )
        display_rows.append(
            {
                "name": row["name"],
                "prob": 0.0,
                "meter": min(1.0, max(DECISION_ROW_METER_FLOOR, row["utility"] / SCORE_ROW_UTILITY_SCALE)),
                "val_str": f"{row['score']}점",
                "type": "score" if row["score"] > 0 else "sacrifice",
                "keep_str": "지금 기록 추천" if row["score"] > 0 else "망한 턴 정리용 희생 후보",
                "keep_indices": [],
                "reason": reason,
            }
        )

    if value_hits:
        best_row = ranked_rows[0] if ranked_rows else None
    elif dump_override:
        best_row = dump_override
    elif sacrifice_override:
        best_row = sacrifice_override
    elif positive_rows:
        best_row = positive_rows[0]
    else:
        best_row = None

    if best_row:
        if best_row.get("utility_mode") == "endgame_value":
            display_rows.insert(
                1,
                {
                    "name": "Endgame V",
                    "prob": 0.0,
                    "meter": min(1.0, max(DECISION_ROW_METER_FLOOR, best_row["utility"] / SCORE_ROW_UTILITY_SCALE)),
                    "val_str": f"V {best_row.get('exact_next_state_value', 0.0):.1f}",
                    "type": "decision",
                    "keep_str": "즉시 점수 + exact V(next_state)",
                    "keep_indices": [],
                    "reason": f"후반 value table에서 `{best_row.get('exact_next_state_key')}` 상태를 조회했습니다.",
                }
            )
        elif best_row.get("utility_mode") == "learned_value":
            display_rows.insert(
                1,
                {
                    "name": "Learned V",
                    "prob": 0.0,
                    "meter": min(1.0, max(DECISION_ROW_METER_FLOOR, best_row["utility"] / SCORE_ROW_UTILITY_SCALE)),
                    "val_str": f"V {best_row.get('learned_next_state_value', 0.0):.1f}",
                    "type": "decision",
                    "keep_str": "즉시 점수 + guarded learned V(next_state)",
                    "keep_indices": [],
                    "reason": (
                        f"{best_row.get('learned_model_id')} 모델을 사용했습니다. "
                        f"validation MAE {best_row.get('learned_validation_mae')}"
                    ),
                }
            )
        elif best_row.get("long_term_note"):
            display_rows.insert(
                1,
                {
                    "name": "장기 가치",
                    "prob": 0.0,
                    "meter": min(1.0, max(DECISION_ROW_METER_FLOOR, abs(best_row.get("quality_gap", 0.0)) / QUALITY_GAP_METER_SCALE)),
                    "val_str": f"평균대비 {best_row.get('quality_gap', 0.0):+.1f}",
                    "type": "decision",
                    "keep_str": "이번 점수 + 남은 칸 가치까지 반영",
                    "keep_indices": [],
                    "reason": best_row["long_term_note"],
                }
            )

    for row in sacrifice_rows:
        if any(existing["name"] == row["name"] for existing in display_rows):
            continue
        is_zero_score = row["score"] <= 0
        display_rows.append(
            {
                "name": row["name"],
                "prob": 0.0,
                "meter": 0.18,
                "val_str": f"{row['score']}점",
                "type": "sacrifice" if is_zero_score else "score",
                "keep_str": "망한 턴 정리용 희생 후보" if is_zero_score else "낮은 점수 정리 후보",
                "keep_indices": [],
                "reason": score_stage_sacrifice_reason(row) if is_zero_score else row["reason"],
            }
        )
        if len(display_rows) >= 5:
            break

    if best_row:
        summary = f"점수 기록 추천: {best_row['name']} {best_row['score']}점. {best_row['reason']}"
        primary_target = best_row["name"]
    else:
        best_sacrifice = sacrifice_rows[0] if sacrifice_rows else None
        if best_sacrifice:
            summary = (
                f"점수가 잘 안 나오는 턴입니다. "
                f"{best_sacrifice['name']}는 장기 손실 추정 {best_sacrifice.get('closing_cost', 0.0):.1f}점 수준이라 먼저 비우는 편이 낫습니다."
            )
        else:
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


def build_upper_roll_rows(dice, scorecard, open_categories, mode, keep_ev_map):
    scorecard = scorecard_to_tuple(scorecard)
    current_upper = sum((value or 0) for value in scorecard[:6])
    if current_upper >= 63:
        return []

    before_bonus_prob = upper_bonus_outlook(scorecard)["bonus_prob"]
    rows = []
    for cat_name in UPPER_CAT_NAMES:
        cat_idx = CATS[cat_name]
        if cat_idx not in open_categories:
            continue

        face = cat_idx + 1
        keep_indices = [idx for idx, value in enumerate(dice) if value == face]
        if not keep_indices:
            continue

        kept_tuple = tuple(sorted(dice[idx] for idx in keep_indices))
        current_score = calc_score(dice, cat_idx)
        bonus_push, bonus_delta = score_stage_upper_bonus_push(
            face,
            len(keep_indices),
            current_upper,
            current_score,
            mode,
        )
        after_bonus_prob = upper_bonus_outlook(projected_scorecard(scorecard, cat_idx, current_score))["bonus_prob"]
        keep_ev = keep_ev_map.get(kept_tuple, 0.0)
        reroll_count = 5 - len(keep_indices)
        prob_get_more = 1.0 if reroll_count == 0 else 1.0 - ((5.0 / 6.0) ** reroll_count)
        remaining_after_score = max(0, 63 - (current_upper + current_score))
        keep_vals = [str(dice[idx]) for idx in sorted(keep_indices)]
        keep_label = f"[{', '.join(keep_vals)}] keep"

        if bonus_delta:
            reason = f"지금 {cat_name}에 적으면 Upper Bonus +35를 바로 확보할 수 있습니다."
            summary_text = f"상단 보너스 추천: {cat_name} 평가 {keep_ev:.1f}, 이번 턴 보너스 마감권"
        elif current_score > 0 and after_bonus_prob >= before_bonus_prob + 0.05:
            reason = (
                f"현재 상단 {current_upper}/63. {cat_name} {current_score}점이면 "
                f"Upper Bonus 가능성이 {before_bonus_prob * 100:.1f}% → {after_bonus_prob * 100:.1f}%로 올라갑니다."
            )
            summary_text = f"상단 보너스 추천: {cat_name} 평가 {keep_ev:.1f}, 보너스 확률 {after_bonus_prob * 100:.0f}%"
        elif current_score > 0:
            reason = f"현재 상단 {current_upper}/63. {cat_name} {current_score}점이면 목표까지 {remaining_after_score}점 남습니다."
            summary_text = f"상단 보너스 추천: {cat_name} 평가 {keep_ev:.1f}"
        else:
            reason = f"{cat_name}를 모아 상단 보너스 페이스를 이어갈 수 있습니다."
            summary_text = f"상단 보너스 추천: {cat_name} 평가 {keep_ev:.1f}"

        rows.append(
            {
                "name": cat_name,
                "prob": prob_get_more,
                "meter": min(1.0, max(prob_get_more, keep_ev / 60.0)),
                "val_str": f"평가 {keep_ev:.1f}",
                "type": "upper",
                "keep_str": f"{keep_label} → Upper Bonus 페이스",
                "keep_indices": keep_indices,
                "reason": reason,
                "summary_text": summary_text,
                "ev": keep_ev,
                "bonus_delta": bonus_delta,
                "bonus_push": bonus_push,
            }
        )

    rows.sort(
        key=lambda row: (
            row.get("bonus_delta", 0),
            row.get("bonus_push", 0.0),
            row.get("ev", 0.0),
            row.get("prob", 0.0),
            row.get("name", ""),
        ),
        reverse=True,
    )
    return rows
