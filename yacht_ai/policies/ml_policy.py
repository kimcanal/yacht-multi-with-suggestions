import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from yacht_core.constants import CATS, EPS
from yacht_core.scoring import (
    calc_score,
    can_cash_yacht_bonus,
    get_keep_options,
    get_precomputed_target_score_value,
    get_precomputed_target_success_value,
    get_transition_distribution,
    has_yacht_bonus,
)

from .advice import (
    build_reason,
    build_recommendation_context_row,
    build_score_stage_advice,
    build_summary,
    build_upper_roll_rows,
    cover_upgrade_rank,
    hand_score_hint,
    mode_rank,
    score_stage_category_advice,
)

CATEGORY_VALUE_SCALES = [
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


def _build_keep_count_classes():
    classes = []
    counts = [0] * 6

    def visit(face_idx, remaining):
        if face_idx == 5:
            counts[face_idx] = remaining
            classes.append(tuple(counts))
            return

        for value in range(remaining + 1):
            counts[face_idx] = value
            visit(face_idx + 1, remaining - value)

    for total in range(6):
        visit(0, total)
    return classes


KEEP_COUNT_CLASSES = _build_keep_count_classes()
KEEP_COUNT_TO_INDEX = {counts: idx for idx, counts in enumerate(KEEP_COUNT_CLASSES)}
HAND_CATS = ["Yacht", "4 of a Kind", "Full House", "Large Straight", "Small Straight"]
HAND_PRIORITY = {"Yacht": 5, "Large Straight": 4, "Full House": 3, "4 of a Kind": 2, "Small Straight": 1}

FEATURE_NAMES = (
    [f"dice_count_{face}" for face in range(1, 7)]
    + [f"rolls_left_{value}" for value in range(3)]
    + ["mode_cover"]
    + [f"open_cat_{idx}" for idx in range(12)]
    + [f"score_norm_{idx}" for idx in range(12)]
    + [
        "turns_completed",
        "open_count",
        "open_upper_count",
        "open_lower_count",
        "upper_score",
        "upper_gap",
        "yacht_bonus_active",
    ]
)


def normalize_scorecard(scorecard):
    base = [None] * 12
    if not isinstance(scorecard, list):
        return base
    for idx, value in enumerate(scorecard[:12]):
        if value is None:
            base[idx] = None
            continue
        try:
            base[idx] = float(value)
        except (TypeError, ValueError):
            base[idx] = None
    return base


def dice_to_counts(dice):
    counts = [0] * 6
    for value in dice:
        face = int(value)
        if 1 <= face <= 6:
            counts[face - 1] += 1
    return tuple(counts)


def keep_counts_to_values(keep_counts):
    values = []
    for face_idx, count in enumerate(keep_counts, start=1):
        values.extend([face_idx] * int(count))
    return values


def keep_counts_to_indices(dice, keep_counts):
    remaining = list(keep_counts)
    indices = []
    for idx, value in enumerate(dice):
        face_idx = int(value) - 1
        if 0 <= face_idx < 6 and remaining[face_idx] > 0:
            indices.append(idx)
            remaining[face_idx] -= 1
    return indices


def _run_indices(dice, values):
    required = set(values)
    indices = []
    for idx, value in enumerate(dice):
        if value in required:
            indices.append(idx)
            required.remove(value)
        if not required:
            return indices
    return []


def _made_hand_safety_action(dice, rolls_left, scorecard):
    if int(rolls_left) <= 0:
        return None

    scorecard = normalize_scorecard(scorecard)
    open_categories = {idx for idx, value in enumerate(scorecard) if value is None}
    dice_counts = dice_to_counts(dice)
    max_count = max(dice_counts)
    dominant_face = dice_counts.index(max_count) + 1

    keep_indices = None
    reason = None

    if max_count == 5 and (CATS["Yacht"] in open_categories or has_yacht_bonus(scorecard)):
        keep_indices = list(range(5))
        reason = "made_yacht"
    elif CATS["Full House"] in open_categories and sorted(dice_counts)[-2:] == [2, 3]:
        keep_indices = list(range(5))
        reason = "made_full_house"
    elif CATS["Large Straight"] in open_categories and sorted(dice) in ([1, 2, 3, 4, 5], [2, 3, 4, 5, 6]):
        keep_indices = list(range(5))
        reason = "made_large_straight"
    elif CATS["4 of a Kind"] in open_categories and max_count >= 4:
        keep_indices = [idx for idx, value in enumerate(dice) if value == dominant_face]
        reason = "made_four_kind"
    elif CATS["Small Straight"] in open_categories:
        for run in ([1, 2, 3, 4], [2, 3, 4, 5], [3, 4, 5, 6]):
            run_indices = _run_indices(dice, run)
            if run_indices:
                keep_indices = run_indices
                reason = "made_small_straight"
                break

    if not keep_indices:
        return None

    keep_counts = [0] * 6
    for idx in keep_indices:
        keep_counts[int(dice[idx]) - 1] += 1
    keep_counts = tuple(keep_counts)
    return {
        "keep_counts": keep_counts,
        "keep_indices": keep_indices,
        "keep_values": [dice[idx] for idx in keep_indices],
        "confidence": 1.0,
        "safety_override": reason,
    }


def _should_apply_safety_action(model_action, safety_action):
    if not model_action or not safety_action:
        return False
    model_counts = model_action.get("keep_counts", ())
    safety_counts = safety_action.get("keep_counts", ())
    return any(model_counts[idx] < safety_counts[idx] for idx in range(6))


def encode_roll_state(dice, rolls_left, strategy_mode, scorecard):
    scorecard = normalize_scorecard(scorecard)
    dice_counts = dice_to_counts(dice)
    open_flags = [1.0 if value is None else 0.0 for value in scorecard]
    open_count = sum(open_flags)
    open_upper_count = sum(open_flags[:6])
    open_lower_count = sum(open_flags[6:])
    upper_score = sum((value or 0.0) for value in scorecard[:6])
    yacht_value = scorecard[11]
    yacht_bonus_active = 1.0 if yacht_value is not None and yacht_value >= 50 else 0.0
    turns_completed = (12 - open_count) / 12.0

    features = []
    features.extend(count / 5.0 for count in dice_counts)
    for expected in range(3):
        features.append(1.0 if int(rolls_left) == expected else 0.0)
    features.append(1.0 if strategy_mode == "cover" else 0.0)
    features.extend(open_flags)
    for idx, value in enumerate(scorecard):
        if value is None:
            features.append(0.0)
            continue
        scale = CATEGORY_VALUE_SCALES[idx]
        features.append(max(0.0, min(float(value) / scale, 3.0)))

    features.extend(
        [
            turns_completed,
            open_count / 12.0,
            open_upper_count / 6.0,
            open_lower_count / 6.0,
            min(upper_score / 63.0, 2.0),
            max(0.0, 63.0 - upper_score) / 63.0,
            yacht_bonus_active,
        ]
    )
    return np.asarray(features, dtype=np.float32)


@lru_cache(maxsize=252)
def valid_keep_class_indices(dice_counts):
    valid = []
    for class_idx, keep_counts in enumerate(KEEP_COUNT_CLASSES):
        if all(keep_counts[face_idx] <= dice_counts[face_idx] for face_idx in range(6)):
            valid.append(class_idx)
    return tuple(valid)


def _softmax(logits):
    shifted = logits - np.max(logits)
    exp = np.exp(shifted)
    denom = np.sum(exp)
    if not np.isfinite(denom) or denom <= 0:
        return np.zeros_like(exp)
    return exp / denom


def _evaluate_keep_transition(kept_tuple, rerolls_remaining, state_solver):
    total = 0.0
    for next_dice, prob in get_transition_distribution(kept_tuple):
        total += prob * state_solver(next_dice, rerolls_remaining - 1)
    return total


def _format_keep_label(keep_values):
    return "모두 굴리기" if not keep_values else f"[{', '.join(map(str, keep_values))}] Keep"


def _fixed_keep_roll_explanation(dice, keep_indices, rolls_left, strategy_mode, scorecard):
    scorecard = normalize_scorecard(scorecard)
    open_categories = tuple(idx for idx, value in enumerate(scorecard) if value is None)
    dice_tuple = tuple(sorted(int(value) for value in dice))
    chosen_keep_tuple = tuple(sorted(int(dice[idx]) for idx in keep_indices))
    yacht_bonus_available = has_yacht_bonus(scorecard)

    @lru_cache(maxsize=None)
    def terminal_best_utility(state_dice):
        best_utility = float("-inf")
        for category_idx in open_categories:
            row = score_stage_category_advice(list(state_dice), scorecard, category_idx, strategy_mode)
            utility = row["utility"]
            if utility > best_utility:
                best_utility = utility
        return 0.0 if best_utility == float("-inf") else best_utility

    @lru_cache(maxsize=None)
    def exact_turn_value(state_dice, rerolls_remaining):
        stop_value = terminal_best_utility(state_dice)
        if rerolls_remaining == 0:
            return stop_value

        best_value = stop_value
        for kept_tuple in get_keep_options(state_dice):
            value = _evaluate_keep_transition(kept_tuple, rerolls_remaining, exact_turn_value)
            if value > best_value:
                best_value = value
        return 0.0 if best_value == float("-inf") else best_value

    @lru_cache(maxsize=None)
    def target_success_value(state_dice, rerolls_remaining, category_idx):
        yacht_bonus_target = category_idx == CATS["Yacht"] and yacht_bonus_available and CATS["Yacht"] not in open_categories
        if not yacht_bonus_target:
            return get_precomputed_target_success_value(state_dice, rerolls_remaining, category_idx)

        if yacht_bonus_target:
            stop_value = 1.0 if can_cash_yacht_bonus(state_dice, open_categories, scorecard) else 0.0
        else:
            stop_value = 1.0 if calc_score(state_dice, category_idx) > 0 else 0.0

        if rerolls_remaining == 0:
            return stop_value

        best_value = stop_value
        for kept_tuple in get_keep_options(state_dice):
            value = _evaluate_keep_transition(
                kept_tuple,
                rerolls_remaining,
                lambda next_dice, next_rolls: target_success_value(next_dice, next_rolls, category_idx),
            )
            if value > best_value:
                best_value = value
        return best_value

    @lru_cache(maxsize=None)
    def target_score_value(state_dice, rerolls_remaining, category_idx):
        return get_precomputed_target_score_value(state_dice, rerolls_remaining, category_idx)

    keep_values = [dice[idx] for idx in keep_indices]
    keep_label = _format_keep_label(keep_values)
    keep_action_values = []
    for kept_tuple in get_keep_options(dice_tuple):
        keep_action_values.append((kept_tuple, _evaluate_keep_transition(kept_tuple, rolls_left, exact_turn_value)))
    chosen_ev = next((value for kept_tuple, value in keep_action_values if kept_tuple == chosen_keep_tuple), 0.0)
    best_exact_keep_tuple, best_exact_ev = max(
        keep_action_values,
        key=lambda item: (item[1], len(item[0]), item[0]),
    )
    optimality_gap = max(0.0, best_exact_ev - chosen_ev)
    alternative_values = [
        value for kept_tuple, value in keep_action_values if kept_tuple != chosen_keep_tuple
    ]
    alternative_gap = chosen_ev - max(alternative_values) if alternative_values else None
    all_dice_kept = len(keep_indices) == 5
    stop_now_advice = build_score_stage_advice(dice, scorecard, open_categories, strategy_mode)

    def format_keep_tuple(kept_tuple):
        keep_values_local = list(kept_tuple)
        if len(keep_values_local) == 5:
            return "지금 기록"
        if not keep_values_local:
            return "모두 굴리기"
        return f"[{', '.join(map(str, keep_values_local))}] Keep"

    def build_decision_rows():
        rows = []
        stop_now_value = float(stop_now_advice.get("expected_value", 0.0))
        stop_now_target = stop_now_advice.get("primary_target") or stop_now_advice.get("message")
        stop_gain = None

        if not all_dice_kept:
            stop_gain = chosen_ev - stop_now_value
            stop_keep_str = (
                f"{stop_now_target}로 바로 기록하는 것보다 한 번 더 보는 편이 유리합니다"
                if stop_gain >= 0
                else f"{stop_now_target}로 바로 기록하는 편이 더 유리합니다"
            )
            rows.append(
                {
                    "name": "지금 멈추기 비교",
                    "prob": 0.0,
                    "meter": min(1.0, max(0.1, abs(stop_gain) / 12.0)),
                    "val_str": f"평가 {stop_gain:+.2f}",
                    "type": "decision",
                    "keep_str": stop_keep_str,
                    "keep_indices": keep_indices,
                    "reason": stop_now_advice.get("summary", ""),
                }
            )

        alternative_actions = sorted(
            ((kept_tuple, value) for kept_tuple, value in keep_action_values if kept_tuple != chosen_keep_tuple),
            key=lambda item: (item[1], len(item[0]), item[0]),
            reverse=True,
        )
        if alternative_actions:
            alt_keep_tuple, alt_value = alternative_actions[0]
            alt_gap = chosen_ev - alt_value
            alt_keep_label = format_keep_tuple(alt_keep_tuple)
            alt_keep_str = (
                f"{alt_keep_label} 대비 현재 추천 우세"
                if alt_gap >= 0
                else f"{alt_keep_label} 쪽이 조금 더 유리"
            )
            alt_reason = (
                f"차선책보다 평가값이 {alt_gap:.2f}점 높습니다."
                if alt_gap >= 0
                else f"{alt_keep_label} 쪽이 평가값 {abs(alt_gap):.2f}점만큼 더 높습니다."
            )
            rows.append(
                {
                    "name": "차선책 비교",
                    "prob": 0.0,
                    "meter": min(1.0, max(0.1, abs(alt_gap) / 10.0)),
                    "val_str": f"평가 {alt_gap:+.2f}",
                    "type": "decision",
                    "keep_str": alt_keep_str,
                    "keep_indices": keep_indices,
                    "reason": alt_reason,
                }
            )
        return rows[:2], stop_now_target, stop_gain

    def build_focused_breakdown():
        hand_rows = []
        for cat_name in HAND_CATS:
            cat_idx = CATS[cat_name]
            yacht_bonus_target = cat_name == "Yacht" and yacht_bonus_available and cat_idx not in open_categories
            if cat_idx not in open_categories and not yacht_bonus_target:
                continue

            display_name = "Yacht Bonus" if yacht_bonus_target else cat_name
            prob = _evaluate_keep_transition(
                chosen_keep_tuple,
                rolls_left,
                lambda next_dice, next_rolls: target_success_value(next_dice, next_rolls, cat_idx),
            )
            if prob <= EPS:
                continue

            conditional_ev = 0.0
            if cat_name == "4 of a Kind":
                expected_score = _evaluate_keep_transition(
                    chosen_keep_tuple,
                    rolls_left,
                    lambda next_dice, next_rolls: target_score_value(next_dice, next_rolls, cat_idx),
                )
                conditional_ev = expected_score / max(prob, EPS)

            if cat_name == "4 of a Kind":
                keep_str = f"{keep_label} → 성공시 평균 {round(conditional_ev, 1)}점"
            elif cat_name == "Yacht":
                score_str = "Yacht Bonus +100 발동" if yacht_bonus_target else "50점 (확정)"
                keep_str = f"{keep_label} → {score_str}"
            elif cat_name == "Large Straight":
                keep_str = f"{keep_label} → 30점 (확정)"
            elif cat_name == "Small Straight":
                keep_str = f"{keep_label} → 15점 (확정)"
            else:
                keep_str = f"{keep_label} → 합계 점수"

            hand_rows.append(
                {
                    "name": display_name,
                    "prob": prob,
                    "meter": prob,
                    "val_str": f"{prob * 100:.2f}%",
                    "type": "hand",
                    "keep_str": keep_str,
                    "keep_indices": keep_indices,
                    "reason": build_reason(display_name, prob, strategy_mode),
                    "priority": HAND_PRIORITY[cat_name],
                    "conditional_ev": conditional_ev,
                }
            )

        hand_rows.sort(
            key=lambda row: mode_rank(
                {
                    "name": row["name"],
                    "prob": row["prob"],
                    "priority": row["priority"],
                    "conditional_ev": row.get("conditional_ev", 0.0),
                    "tie_values": keep_values,
                },
                strategy_mode,
            ),
            reverse=True,
        )

        upper_rows = [
            row
            for row in build_upper_roll_rows(dice, scorecard, open_categories, strategy_mode, {chosen_keep_tuple: chosen_ev})
            if row.get("keep_indices") == keep_indices
        ]
        best_row = None
        if upper_rows and (upper_rows[0].get("bonus_delta") or sum((value or 0.0) for value in scorecard[:6]) >= 42):
            best_row = upper_rows[0]
        elif hand_rows:
            best_row = hand_rows[0]
        elif upper_rows:
            best_row = upper_rows[0]

        straight_upgrade = None
        if best_row and best_row.get("name") == "Small Straight" and CATS["Large Straight"] in open_categories:
            small_prob_for_keep = _evaluate_keep_transition(
                chosen_keep_tuple,
                rolls_left,
                lambda next_dice, next_rolls: target_success_value(next_dice, next_rolls, CATS["Small Straight"]),
            )
            large_prob_for_keep = _evaluate_keep_transition(
                chosen_keep_tuple,
                rolls_left,
                lambda next_dice, next_rolls: target_success_value(next_dice, next_rolls, CATS["Large Straight"]),
            )
            if small_prob_for_keep >= 1.0 - EPS and large_prob_for_keep > EPS:
                straight_upgrade = {
                    "name": "Large Straight 업그레이드",
                    "prob": large_prob_for_keep,
                    "meter": large_prob_for_keep,
                    "val_str": f"{large_prob_for_keep * 100:.2f}%",
                    "type": "hand",
                    "keep_str": f"{keep_label} → 실패해도 Small Straight 유지",
                    "keep_indices": keep_indices,
                    "reason": f"Large Straight {large_prob_for_keep * 100:.1f}%를 노리되, 실패해도 Small Straight는 유지됩니다.",
                }

        breakdown = []
        if straight_upgrade:
            breakdown.append(straight_upgrade)
        if upper_rows:
            for row in upper_rows[:2]:
                if row.get("name") not in {item.get("name") for item in breakdown}:
                    breakdown.append(row)
        for row in hand_rows:
            if len(breakdown) >= 5:
                break
            if row.get("name") not in {item.get("name") for item in breakdown}:
                breakdown.append(row)

        summary_row = straight_upgrade or best_row
        if summary_row and not all_dice_kept:
            featured_rows = [summary_row]
            seen_featured = {row.get("name") for row in featured_rows}
            breakdown = featured_rows + [row for row in breakdown if row.get("name") not in seen_featured]

        decision_rows, stop_now_target, stop_gain = build_decision_rows()
        recommendation_context_row = build_recommendation_context_row(
            strategy_mode,
            chosen_ev,
            alternative_gap,
            summary_row,
            straight_upgrade,
            keep_indices,
            stop_now_target,
            stop_gain,
        )
        if recommendation_context_row:
            breakdown = breakdown[:1] + [recommendation_context_row] + breakdown[1:]
        if decision_rows:
            breakdown = breakdown[:3] + decision_rows + breakdown[3:]

        summary = build_summary(summary_row, strategy_mode) if summary_row else f"집중 공략 추천: {keep_label}, 평가값 {chosen_ev:.2f}"
        if straight_upgrade:
            summary = f"집중 공략 추천: Large Straight {straight_upgrade['val_str']}, 실패해도 Small Straight 유지"
            primary_target = "Large Straight"
            message = f"{keep_label} (Large Straight 업그레이드)"
        else:
            primary_target = best_row["name"] if best_row else None
            message = "지금 기록 추천" if all_dice_kept else keep_label
            if primary_target and primary_target not in ("핸드 하나 이상 성공",) and not all_dice_kept:
                message = f"{keep_label} ({primary_target} 노리기)"
            elif primary_target and all_dice_kept:
                message = f"지금 기록 추천 ({primary_target})"
        if all_dice_kept and not straight_upgrade:
            summary = stop_now_advice.get("summary", f"집중 공략 추천: 지금 기록하는 편이 평가값 {chosen_ev:.2f}로 가장 좋습니다")
            primary_target = stop_now_advice.get("primary_target")
            breakdown = stop_now_advice.get("breakdown", [])[:3] + decision_rows + stop_now_advice.get("breakdown", [])[3:]

        return {
            "keep_indices": keep_indices,
            "expected_value": round(chosen_ev, 2),
            "message": message,
            "breakdown": breakdown,
            "primary_target": primary_target,
            "summary": summary,
            "optimality_gap": round(optimality_gap, 6),
            "alternative_gap": None if alternative_gap is None else round(alternative_gap, 2),
        }

    def build_cover_breakdown():
        hand_targets = []
        for cat_name in HAND_CATS:
            cat_idx = CATS[cat_name]
            yacht_bonus_target = cat_name == "Yacht" and yacht_bonus_available and cat_idx not in open_categories
            if cat_idx not in open_categories and not yacht_bonus_target:
                continue
            hand_targets.append(
                {
                    "name": "Yacht Bonus" if yacht_bonus_target else cat_name,
                    "internal_name": cat_name,
                    "category_idx": cat_idx,
                    "bonus_active": yacht_bonus_target,
                    "priority": HAND_PRIORITY[cat_name],
                }
            )

        if not hand_targets:
            return build_focused_breakdown()

        def terminal_target_hit(state_dice, category_idx):
            if category_idx == CATS["Yacht"] and yacht_bonus_available and CATS["Yacht"] not in open_categories:
                return can_cash_yacht_bonus(state_dice, open_categories, scorecard)
            return calc_score(state_dice, category_idx) > 0

        def terminal_cover_hit(state_dice):
            return any(terminal_target_hit(state_dice, target["category_idx"]) for target in hand_targets)

        @lru_cache(maxsize=None)
        def cover_target_bias(state_dice, rerolls_remaining, kept_tuple):
            rows = []
            for target in hand_targets:
                prob = _evaluate_keep_transition(
                    kept_tuple,
                    rerolls_remaining,
                    lambda next_dice, next_rolls, idx=target["category_idx"]: target_success_value(next_dice, next_rolls, idx),
                )
                if prob <= EPS:
                    continue
                rows.append(
                    {
                        "name": target["name"],
                        "prob": prob,
                        "priority": target["priority"],
                    }
                )
            return cover_upgrade_rank(rows)

        @lru_cache(maxsize=None)
        def cover_success_value(state_dice, rerolls_remaining):
            stop_value = 1.0 if terminal_cover_hit(state_dice) else 0.0
            if rerolls_remaining == 0:
                return stop_value
            return max(stop_value, cover_best_action(state_dice, rerolls_remaining)[1])

        @lru_cache(maxsize=None)
        def cover_best_action(state_dice, rerolls_remaining):
            if rerolls_remaining == 0:
                return ((), 1.0 if terminal_cover_hit(state_dice) else 0.0)

            best_value = float("-inf")
            tied_keeps = []
            for kept_tuple in get_keep_options(state_dice):
                value = _evaluate_keep_transition(kept_tuple, rerolls_remaining, cover_success_value)
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
                    tuple(sorted(kept_tuple, reverse=True)),
                ),
            )
            return (best_keep, best_value)

        @lru_cache(maxsize=None)
        def cover_policy_target_prob(state_dice, rerolls_remaining, category_idx):
            if terminal_cover_hit(state_dice):
                return 1.0 if terminal_target_hit(state_dice, category_idx) else 0.0
            if rerolls_remaining == 0:
                return 1.0 if terminal_target_hit(state_dice, category_idx) else 0.0
            kept_tuple, _ = cover_best_action(state_dice, rerolls_remaining)
            return _evaluate_keep_transition(
                kept_tuple,
                rerolls_remaining,
                lambda next_dice, next_rolls: cover_policy_target_prob(next_dice, next_rolls, category_idx),
            )

        cover_success_prob = _evaluate_keep_transition(chosen_keep_tuple, rolls_left, cover_success_value)
        cover_fail_prob = max(0.0, 1.0 - cover_success_prob)

        cover_target_rows = []
        for target in hand_targets:
            prob = _evaluate_keep_transition(
                chosen_keep_tuple,
                rolls_left,
                lambda next_dice, next_rolls, idx=target["category_idx"]: cover_policy_target_prob(next_dice, next_rolls, idx),
            )
            if prob <= EPS:
                continue
            cover_target_rows.append(
                {
                    "name": target["name"],
                    "prob": prob,
                    "priority": target["priority"],
                }
            )

        cover_target_rows.sort(
            key=lambda row: (row["prob"], row["priority"], hand_score_hint(row["name"], row)),
            reverse=True,
        )

        breakdown = [
            {
                "name": "핸드 하나 이상 성공",
                "prob": cover_success_prob,
                "meter": cover_success_prob,
                "val_str": f"{cover_success_prob * 100:.2f}%",
                "type": "cover",
                "keep_str": f"{keep_label} → 열린 하단 족보 중 하나 이상",
                "keep_indices": keep_indices,
                "reason": "이 keep을 고른 뒤 남은 reroll에서 커버 경로를 exact하게 계산한 확률입니다.",
            },
            {
                "name": "전부 실패",
                "prob": cover_fail_prob,
                "meter": cover_fail_prob,
                "val_str": f"{cover_fail_prob * 100:.2f}%",
                "type": "risk",
                "keep_str": f"{keep_label} → 이번 턴에 하단 족보를 하나도 못 먹는 확률",
                "keep_indices": keep_indices,
                "reason": "독립 가정이 아니라 exact union의 여집합으로 계산했습니다.",
            },
        ]

        for row in cover_target_rows[:3]:
            breakdown.append(
                {
                    "name": row["name"],
                    "prob": row["prob"],
                    "meter": row["prob"],
                    "val_str": f"{row['prob'] * 100:.2f}%",
                    "type": "hand",
                    "keep_str": f"{keep_label} → 커버 경로에서 함께 열리는 후보",
                    "keep_indices": keep_indices,
                    "reason": build_reason(row["name"], row["prob"], strategy_mode),
                }
            )

        decision_rows, _stop_now_target, _stop_gain = build_decision_rows()
        if decision_rows:
            breakdown = breakdown[:3] + decision_rows + breakdown[3:]
        if all_dice_kept:
            breakdown = stop_now_advice.get("breakdown", [])[:3] + decision_rows + stop_now_advice.get("breakdown", [])[3:]

        return {
            "keep_indices": keep_indices,
            "expected_value": round(chosen_ev, 2),
            "message": "지금 기록 추천 (커버 플레이)" if all_dice_kept else (f"{keep_label} (커버 플레이)" if keep_indices else "모두 굴리기 (커버 플레이)"),
            "breakdown": breakdown,
            "primary_target": stop_now_advice.get("primary_target") if all_dice_kept else "핸드 하나 이상 성공",
            "summary": (
                stop_now_advice.get("summary", f"커버 플레이 추천: 지금 기록하는 편이 평가값 {chosen_ev:.2f}로 가장 좋습니다")
                if all_dice_kept
                else f"커버 플레이: 핸드 하나 이상 {cover_success_prob * 100:.2f}%, 전부 실패 {cover_fail_prob * 100:.2f}%"
            ),
            "optimality_gap": round(optimality_gap, 6),
        }

    if strategy_mode == "cover":
        return build_cover_breakdown()
    return build_focused_breakdown()


@dataclass
class RollPolicyModel:
    feature_mean: np.ndarray
    feature_std: np.ndarray
    w1: np.ndarray
    b1: np.ndarray
    w2: np.ndarray
    b2: np.ndarray
    metadata: dict

    @classmethod
    def load(cls, path):
        model_path = Path(path)
        with model_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        return cls(
            feature_mean=np.asarray(payload["feature_mean"], dtype=np.float32),
            feature_std=np.asarray(payload["feature_std"], dtype=np.float32),
            w1=np.asarray(payload["w1"], dtype=np.float32),
            b1=np.asarray(payload["b1"], dtype=np.float32),
            w2=np.asarray(payload["w2"], dtype=np.float32),
            b2=np.asarray(payload["b2"], dtype=np.float32),
            metadata=payload.get("metadata", {}),
        )

    def predict_logits(self, feature_vector):
        normalized = (feature_vector - self.feature_mean) / self.feature_std
        hidden = np.maximum(normalized @ self.w1 + self.b1, 0.0)
        return hidden @ self.w2 + self.b2

    def predict_valid_actions(self, dice, rolls_left, strategy_mode, scorecard, top_k=3):
        if not isinstance(dice, list) or len(dice) != 5:
            return None

        feature_vector = encode_roll_state(dice, rolls_left, strategy_mode, scorecard)
        logits = self.predict_logits(feature_vector)
        probs = _softmax(logits)
        dice_counts = dice_to_counts(dice)
        valid_indices = valid_keep_class_indices(dice_counts)
        if not valid_indices:
            return None

        valid_probs = probs[list(valid_indices)]
        if valid_probs.size == 0:
            return None

        valid_total = float(np.sum(valid_probs))
        if not np.isfinite(valid_total) or valid_total <= 0:
            return None

        valid_probs = valid_probs / valid_total
        ranked_positions = np.argsort(valid_probs)[::-1][: max(1, int(top_k))]
        actions = []
        for position in ranked_positions:
            class_idx = valid_indices[int(position)]
            keep_counts = KEEP_COUNT_CLASSES[class_idx]
            keep_indices = keep_counts_to_indices(dice, keep_counts)
            actions.append(
                {
                    "keep_counts": keep_counts,
                    "keep_indices": keep_indices,
                    "keep_values": [dice[idx] for idx in keep_indices],
                    "confidence": float(valid_probs[int(position)]),
                }
            )
        safety_action = _made_hand_safety_action(dice, rolls_left, scorecard)
        if _should_apply_safety_action(actions[0], safety_action):
            actions = [safety_action] + [
                action for action in actions if action.get("keep_counts") != safety_action["keep_counts"]
            ]
            actions = actions[: max(1, int(top_k))]
        return actions

    def recommend_roll(self, dice, rolls_left, strategy_mode, scorecard, min_confidence=0.0):
        actions = self.predict_valid_actions(dice, rolls_left, strategy_mode, scorecard, top_k=3)
        if not actions:
            return None

        best_action = actions[0]
        if best_action["confidence"] < float(min_confidence):
            return None

        explanation = _fixed_keep_roll_explanation(
            dice,
            best_action["keep_indices"],
            int(rolls_left),
            strategy_mode,
            scorecard,
        )
        if explanation.get("optimality_gap", 0.0) > 0.25:
            return None
        dice_recommendations = []
        best_keep_indices = set(best_action["keep_indices"])
        for idx in range(5):
            dice_recommendations.append(
                {
                    "index": idx,
                    "value": dice[idx],
                    "action": "keep" if idx in best_keep_indices else "reroll",
                    "confidence": int(round(best_action["confidence"] * 100)),
                }
            )

        return {
            "keep_indices": explanation["keep_indices"],
            "expected_value": explanation["expected_value"],
            "policy_confidence": round(best_action["confidence"], 6),
            "dice_recommendations": dice_recommendations,
            "message": explanation["message"],
            "breakdown": explanation["breakdown"],
            "strategy_mode": strategy_mode,
            "primary_target": explanation["primary_target"],
            "summary": explanation["summary"],
            "stage": "roll",
            "policy_source": "learned_roll_policy",
        }
