from copy import deepcopy
from functools import lru_cache
import os

from .advice import (
    build_reason,
    build_recommendation_context_row,
    build_score_stage_advice,
    build_summary,
    build_upper_roll_rows,
    choose_general_keep,
    choose_target_keep,
    cover_upgrade_rank,
    hand_score_hint,
    mode_rank,
    normalize_strategy_mode,
    score_stage_category_advice,
    scorecard_to_tuple,
)
from .constants import (
    CATS,
    CATEGORY_NAMES,
    EPS,
    FOCUSED_EV_GUARD_POINTS,
    SACRIFICE_PRIORITY,
    UPPER_BONUS_VALUE,
    YACHT_BONUS_CASH_IN,
)
from .endgame_value import DEFAULT_ENDGAME_VALUE_TABLE_PATH, load_endgame_value_table
from .learned_value import load_linear_value_model
from .scoring import (
    calc_score,
    can_cash_yacht_bonus,
    get_keep_options,
    get_precomputed_target_score_value,
    get_precomputed_target_success_value,
    get_transition_distribution,
    has_yacht_bonus,
    keep_values_desc,
    kept_tuple_to_indices,
)

# ---------------------------------------------------------------------------
# 내부 헬퍼: 각 모드 계산을 주 함수에서 분리
# ---------------------------------------------------------------------------

def _compute_hand_targets(
    dice, dice_tuple, rolls_left, open_categories,
    hand_cats, hand_priority, yacht_bonus_available,
    evaluate_keep_fn, target_success_fn, target_score_fn,
):
    """열린 하단 족보별 최적 keep과 성공 확률을 계산해 반환."""
    hand_targets = []
    best_hand_moves = []

    for cat_name in hand_cats:
        cat_idx = CATS[cat_name]
        yacht_bonus_target = (
            cat_name == "Yacht" and yacht_bonus_available and cat_idx not in open_categories
        )
        if cat_idx not in open_categories and not yacht_bonus_target:
            continue

        display_name = "Yacht Bonus" if yacht_bonus_target else cat_name
        hand_targets.append({
            "name": display_name,
            "internal_name": cat_name,
            "category_idx": cat_idx,
            "bonus_active": yacht_bonus_target,
            "priority": hand_priority[cat_name],
        })

        action_rows = []
        for kept_tuple in get_keep_options(dice_tuple):
            success_prob = evaluate_keep_fn(
                kept_tuple, rolls_left,
                lambda nd, nr, idx=cat_idx: target_success_fn(nd, nr, idx),
            )
            expected_score = 0.0
            if cat_name == "4 of a Kind":
                expected_score = evaluate_keep_fn(
                    kept_tuple, rolls_left,
                    lambda nd, nr, idx=cat_idx: target_score_fn(nd, nr, idx),
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
        best_keep = choose_target_keep(cat_name, [row["kept_tuple"] for row in tie_rows])
        selected = next(row for row in tie_rows if row["kept_tuple"] == best_keep)
        cond_ev = (
            selected["expected_score"] / max_prob
            if cat_name == "4 of a Kind" and max_prob > EPS else 0.0
        )

        best_hand_moves.append({
            "name": display_name,
            "internal_name": cat_name,
            "bonus_active": yacht_bonus_target,
            "category_idx": cat_idx,
            "prob": max_prob,
            "kept_tuple": best_keep,
            "keep_indices": kept_tuple_to_indices(dice, best_keep),
            "priority": hand_priority[cat_name],
            "tie_values": list(keep_values_desc(best_keep)),
            "tie_keeps": [
                {
                    "keep_indices": kept_tuple_to_indices(dice, row["kept_tuple"]),
                    "values": list(keep_values_desc(row["kept_tuple"])),
                }
                for row in tie_rows
            ],
            "conditional_ev": cond_ev,
        })

    return hand_targets, best_hand_moves


def _build_cover_mode_result(
    dice, dice_tuple, rolls_left, hand_targets, keep_ev_map,
    evaluate_keep_fn, target_success_fn, terminal_target_hit_fn,
):
    """Cover 모드 전용 계산. exact union probability로 keep을 결정하고 결과 dict 반환."""

    @lru_cache(maxsize=None)
    def cover_target_bias(state_dice, rerolls_remaining, kept_tuple):
        rows = []
        for target in hand_targets:
            prob = evaluate_keep_fn(
                kept_tuple, rerolls_remaining,
                lambda nd, nr, idx=target["category_idx"]: target_success_fn(nd, nr, idx),
            )
            if prob <= EPS:
                continue
            rows.append({"name": target["name"], "prob": prob, "priority": target["priority"]})
        return cover_upgrade_rank(rows)

    def terminal_cover_hit(state_dice):
        return any(terminal_target_hit_fn(state_dice, t["category_idx"]) for t in hand_targets)

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
            value = evaluate_keep_fn(kept_tuple, rerolls_remaining, cover_success_value)
            if value > best_value + EPS:
                best_value = value
                tied_keeps = [kept_tuple]
            elif abs(value - best_value) <= EPS:
                tied_keeps.append(kept_tuple)

        best_keep = max(
            tied_keeps,
            key=lambda kt: (
                cover_target_bias(state_dice, rerolls_remaining, kt),
                len(kt),
                keep_values_desc(kt),
            ),
        )
        return (best_keep, best_value)

    @lru_cache(maxsize=None)
    def cover_policy_target_prob(state_dice, rerolls_remaining, category_idx):
        if terminal_cover_hit(state_dice):
            return 1.0 if terminal_target_hit_fn(state_dice, category_idx) else 0.0
        if rerolls_remaining == 0:
            return 1.0 if terminal_target_hit_fn(state_dice, category_idx) else 0.0
        kept_tuple, _ = cover_best_action(state_dice, rerolls_remaining)
        return evaluate_keep_fn(
            kept_tuple, rerolls_remaining,
            lambda nd, nr: cover_policy_target_prob(nd, nr, category_idx),
        )

    best_keep_tuple, cover_success_prob = cover_best_action(dice_tuple, rolls_left)
    cover_fail_prob = max(0.0, 1.0 - cover_success_prob)

    cover_target_rows = []
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
        key=lambda r: (r["prob"], r["priority"], hand_score_hint(r["name"], r)),
        reverse=True,
    )

    best_keep_indices = kept_tuple_to_indices(dice, best_keep_tuple)
    kept_vals = [str(dice[i]) for i in sorted(best_keep_indices)]
    keep_label = f"[{', '.join(kept_vals)}] keep" if kept_vals else "모두 굴리기"
    covered_names = [r["name"] for r in cover_target_rows[:3]]
    covered_str = " / ".join(covered_names) if covered_names else "열린 하단 족보"
    chosen_ev = keep_ev_map.get(best_keep_tuple, float("-inf"))

    breakdown = [
        {
            "name": "핸드 하나 이상 성공",
            "prob": cover_success_prob,
            "meter": cover_success_prob,
            "val_str": f"{cover_success_prob * 100:.2f}%",
            "type": "cover",
            "keep_str": f"{keep_label} → {covered_str} 중 하나 이상",
            "keep_indices": best_keep_indices,
            "reason": "겹치는 족보까지 한 번에 계산한 exact union 확률입니다.",
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
            "reason": build_reason(row["name"], row["prob"], "cover"),
        })

    dice_recommendations = [
        {"index": i, "value": dice[i], "action": "keep" if i in best_keep_indices else "reroll", "confidence": 100}
        for i in range(5)
    ]
    rec_msg = "모두 굴리기" if not best_keep_indices else f"[{', '.join(kept_vals)}] Keep (커버 플레이)"
    summary = (
        f"커버 플레이: 핸드 하나 이상 {cover_success_prob * 100:.2f}%, "
        f"전부 실패 {cover_fail_prob * 100:.2f}%"
    )
    return {
        "keep_indices": best_keep_indices,
        "expected_value": round(chosen_ev, 2),
        "dice_recommendations": dice_recommendations,
        "message": rec_msg,
        "breakdown": breakdown,
        "strategy_mode": "cover",
        "primary_target": "핸드 하나 이상 성공",
        "summary": summary,
        "stage": "roll",
        "cover_success_prob": round(cover_success_prob, 6),
        "cover_fail_prob": round(cover_fail_prob, 6),
    }


def _build_focused_breakdown_rows(
    dice, rolls_left, best_hand_moves, open_categories,
    yacht_bonus_available, hand_priority, evaluate_keep_fn, target_success_fn,
):
    """Focused 모드에서 하단 족보별 breakdown row 목록을 반환."""
    dice_tuple = tuple(sorted(dice))
    hand_cats_display = ["4 of a Kind", "Full House", "Small Straight", "Large Straight", "Yacht"]
    breakdown = []

    for cat_name in hand_cats_display:
        cat_idx = CATS[cat_name]
        yacht_bonus_target = (
            cat_name == "Yacht" and yacht_bonus_available and cat_idx not in open_categories
        )
        if cat_idx not in open_categories and not yacht_bonus_target:
            continue

        same_cat_moves = [m for m in best_hand_moves if m.get("internal_name") == cat_name]
        if not same_cat_moves:
            keep_str = (
                "Keep 후보 없음: 다시 돌리기"
                if len(set(dice)) == 5 and cat_name in ("Yacht", "4 of a Kind", "Full House")
                else "불가능"
            )
            breakdown.append({
                "name": "Yacht Bonus" if yacht_bonus_target else cat_name,
                "prob": 0.0, "val_str": "", "type": "hand",
                "keep_str": keep_str, "keep_indices": [],
                "reason": "현재 턴에는 이 족보를 현실적으로 노리기 어렵습니다.",
            })
            continue

        move = same_cat_moves[0]
        if move["prob"] == 0:
            breakdown.append({
                "name": move["name"], "prob": 0.0, "val_str": "", "type": "hand",
                "keep_str": "불가능", "keep_indices": [],
                "reason": "이번 상태에선 완성 경로가 없습니다.",
            })
            continue

        if cat_name == "4 of a Kind":
            keep_vals = [str(dice[i]) for i in sorted(move["keep_indices"])]
            keep_str = f"[{', '.join(keep_vals)}]" if keep_vals else "모두 굴리기"
            keep_str = f"{keep_str} keep → 성공시 평균 {round(move.get('conditional_ev', 0), 1)}점"
            breakdown.append({
                "name": move["name"], "prob": move["prob"],
                "val_str": f"{move['prob'] * 100:.2f}%", "type": "hand",
                "keep_str": keep_str, "keep_indices": move["keep_indices"],
                "reason": build_reason(move["name"], move["prob"], "focused"),
            })
            continue

        if cat_name == "Yacht":
            keep_vals = [str(dice[i]) for i in sorted(move["keep_indices"])]
            keep_str = f"[{', '.join(keep_vals)}]" if keep_vals else "모두 굴리기"
            final_keep = keep_str if keep_str == "모두 굴리기" else f"{keep_str} keep"
            score_str = "Yacht Bonus +100 발동" if move.get("bonus_active") else "50점 (확정)"
            breakdown.append({
                "name": move["name"], "prob": move["prob"],
                "val_str": f"{move['prob'] * 100:.2f}%", "type": "hand",
                "keep_str": f"{final_keep} → {score_str}", "keep_indices": move["keep_indices"],
                "reason": build_reason(move["name"], move["prob"], "focused"),
            })
            continue

        # Small Straight / Large Straight / Full House — tie-keep 처리
        tie_keeps = move.get("tie_keeps") or []
        if len(tie_keeps) > 1:
            normalized = []
            for candidate in tie_keeps:
                values = [dice[i] for i in sorted(candidate["keep_indices"])]
                normalized.append((tuple(sorted(values, reverse=True)), len(values)))

            unique_values = {}
            for values, value_len in normalized:
                if values not in unique_values:
                    unique_values[values] = value_len

            if cat_name in ("Small Straight", "Large Straight"):
                min_len = min(unique_values.values(), default=0)
                display = sorted(
                    [v for v, l in unique_values.items() if l == min_len],
                    reverse=True,
                )[:1]
            elif cat_name == "Full House" and tuple() in unique_values:
                display = [tuple()]
            else:
                display = sorted(unique_values.keys(), reverse=True)[:3]

            keep_labels = [
                f"[{', '.join(map(str, v))}]" if v else "모두 굴리기" for v in display
            ]
            keep_str = keep_labels[0] if len(keep_labels) == 1 else f"Keep 후보: {', '.join(keep_labels)}"
        else:
            keep_vals = [str(dice[i]) for i in sorted(move["keep_indices"])]
            keep_str = f"[{', '.join(keep_vals)}]" if keep_vals else "모두 굴리기"

        score_str = {
            "Large Straight": "30점 (확정)",
            "Small Straight": "15점 (확정)",
        }.get(cat_name, "합계 점수")

        keep_prefix = (
            keep_str if keep_str in ("모두 굴리기",) or "Keep 후보" in keep_str
            else f"{keep_str} keep"
        )
        breakdown.append({
            "name": move["name"], "prob": move["prob"],
            "val_str": f"{move['prob'] * 100:.2f}%", "type": "hand",
            "keep_str": f"{keep_prefix} → {score_str}", "keep_indices": move["keep_indices"],
            "reason": build_reason(move["name"], move["prob"], "focused"),
        })

    return breakdown


def _build_decision_rows(
    dice, scorecard, open_categories, mode,
    keep_action_values, best_keep_tuple, chosen_ev,
    explaining_row, straight_upgrade, all_dice_kept,
    score_value_mode="heuristic", endgame_value_table=None,
    learned_value_model=None, learned_value_max_mae=25.0, learned_value_min_turns=5,
):
    """지금 멈추기 비교 / 차선책 비교 decision row 목록을 반환."""
    decision_rows = []
    stop_now_advice = build_score_stage_advice(
        dice,
        scorecard,
        open_categories,
        mode,
        score_value_mode=score_value_mode,
        endgame_value_table=endgame_value_table,
        learned_value_model=learned_value_model,
        learned_value_max_mae=learned_value_max_mae,
        learned_value_min_turns=learned_value_min_turns,
    )
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
        decision_rows.append({
            "name": "지금 멈추기 비교",
            "prob": 0.0,
            "meter": min(1.0, max(0.1, abs(stop_gain) / 12.0)),
            "val_str": f"평가 {stop_gain:+.2f}",
            "type": "decision",
            "keep_str": stop_keep_str,
            "keep_indices": kept_tuple_to_indices(dice, best_keep_tuple),
            "reason": stop_now_advice.get("summary", ""),
        })

    alternative_actions = sorted(
        ((kt, v) for kt, v in keep_action_values if kt != best_keep_tuple),
        key=lambda item: (item[1], len(item[0]), keep_values_desc(item[0])),
        reverse=True,
    )
    if alternative_actions:
        alt_keep_tuple, alt_value = alternative_actions[0]
        alt_gap = chosen_ev - alt_value
        alt_keep_label = _format_keep_tuple(dice, alt_keep_tuple)
        if alt_gap >= 0:
            alt_reason = f"차선책보다 평가값이 {alt_gap:.2f}점 높습니다."
            alt_keep_str = f"{alt_keep_label} 대비 현재 추천 우세"
        else:
            target_reason = ""
            if straight_upgrade:
                target_reason = (
                    f" 대신 현재 추천은 Large Straight {straight_upgrade['val_str']}를 보면서 "
                    "실패해도 Small Straight를 유지합니다."
                )
            elif mode == "focused" and explaining_row and explaining_row.get("type") == "hand":
                target_reason = (
                    f" 대신 현재 추천은 {explaining_row['name']} 성공 확률 "
                    f"{explaining_row.get('val_str', '')}를 더 높게 봅니다."
                )
            elif mode == "focused" and explaining_row and explaining_row.get("type") == "upper":
                target_reason = " 대신 현재 추천은 Upper Bonus 페이스를 더 좋게 가져갑니다."
            alt_reason = f"{alt_keep_label} 쪽이 평가값 {abs(alt_gap):.2f}점만큼 더 높습니다.{target_reason}"
            alt_keep_str = (
                f"{alt_keep_label} 쪽은 평가 우세, 현재 추천은 {explaining_row.get('name', '목표')} 우선"
                if explaining_row and explaining_row.get("name")
                else f"{alt_keep_label} 쪽이 조금 더 유리"
            )
        decision_rows.append({
            "name": "차선책 비교",
            "prob": 0.0,
            "meter": min(1.0, max(0.1, abs(alt_gap) / 10.0)),
            "val_str": f"평가 {alt_gap:+.2f}",
            "type": "decision",
            "keep_str": alt_keep_str,
            "keep_indices": kept_tuple_to_indices(dice, best_keep_tuple),
            "reason": alt_reason,
        })

    return decision_rows, stop_now_advice, stop_gain


def _build_focus_ev_guard_row(dice, best_keep_tuple, focus_ev_guard):
    if not focus_ev_guard:
        return None

    focused_label = _format_keep_tuple(dice, focus_ev_guard["focus_keep_tuple"])
    chosen_label = _format_keep_tuple(dice, best_keep_tuple)
    target_name = focus_ev_guard.get("target_name") or "목표 족보"
    gap = focus_ev_guard["gap"]
    return {
        "name": "집중 공략 보정",
        "prob": 0.0,
        "meter": min(1.0, max(0.15, gap / 30.0)),
        "val_str": f"평가 +{gap:.2f}",
        "type": "decision",
        "keep_str": f"{chosen_label} 선택",
        "keep_indices": kept_tuple_to_indices(dice, best_keep_tuple),
        "reason": (
            f"{target_name} 확률만 보면 {focused_label}도 후보지만, "
            f"점수판 평가가 {gap:.2f}점 낮아 현재 선택으로 보정했습니다."
        ),
    }


def _format_keep_tuple(dice, kept_tuple):
    kept_vals = list(keep_values_desc(kept_tuple))
    if len(kept_vals) == 5:
        return "지금 기록"
    if not kept_vals:
        return "모두 굴리기"
    return f"[{', '.join(map(str, reversed(kept_vals)))}] Keep"


# ---------------------------------------------------------------------------
# 주 DP 함수 — 내부 클로저 DP 함수들은 그대로 유지 (lru_cache 스코프 필요)
# ---------------------------------------------------------------------------

def _normalize_score_value_mode(score_value_mode):
    if score_value_mode in ("hybrid", "learned_value"):
        return "hybrid"
    if score_value_mode in ("value_score_only", "score_only", "endgame_value_score_only"):
        return "value_score_only"
    if score_value_mode in ("value_optimal", "optimal_value", "endgame_value_optimal", "ev_optimal"):
        return "value_optimal"
    if score_value_mode in ("value", "endgame_value"):
        return "value"
    return "heuristic"


def _banked_score_total(scorecard):
    scorecard = scorecard_to_tuple(scorecard)
    upper_total = sum((value or 0) for value in scorecard[:6])
    return int(sum((value or 0) for value in scorecard)) + (35 if upper_total >= 63 else 0)


def _resolve_score_value_options(
    score_value_mode=None,
    endgame_value_table_path=None,
    learned_value_model_path=None,
    learned_value_max_mae=None,
    learned_value_min_turns=None,
):
    requested_mode = score_value_mode
    if requested_mode is None:
        requested_mode = os.environ.get("YACHT_SCORE_STAGE_MODE", "heuristic")
    resolved_mode = _normalize_score_value_mode(requested_mode)
    resolved_path = endgame_value_table_path or os.environ.get("YACHT_ENDGAME_VALUE_TABLE", "")
    if resolved_mode in ("value", "value_score_only", "value_optimal", "hybrid") and not resolved_path:
        resolved_path = DEFAULT_ENDGAME_VALUE_TABLE_PATH
    if resolved_mode not in ("value", "value_score_only", "value_optimal", "hybrid"):
        resolved_path = ""
    resolved_model_path = learned_value_model_path or os.environ.get("YACHT_LEARNED_VALUE_MODEL", "")
    if resolved_mode != "hybrid":
        resolved_model_path = ""
    if learned_value_max_mae is None:
        try:
            resolved_max_mae = float(os.environ.get("YACHT_LEARNED_VALUE_MAX_MAE", "25.0"))
        except ValueError:
            resolved_max_mae = 25.0
    else:
        resolved_max_mae = float(learned_value_max_mae)
    if learned_value_min_turns is None:
        try:
            resolved_min_turns = int(os.environ.get("YACHT_LEARNED_VALUE_MIN_TURNS", "5"))
        except ValueError:
            resolved_min_turns = 5
    else:
        resolved_min_turns = int(learned_value_min_turns)
    return resolved_mode, resolved_path, resolved_model_path, resolved_max_mae, max(0, resolved_min_turns)


def _load_score_value_table(score_value_mode, endgame_value_table_path):
    if score_value_mode not in ("value", "value_score_only", "value_optimal", "hybrid") or not endgame_value_table_path:
        return None
    try:
        return load_endgame_value_table(endgame_value_table_path)
    except OSError:
        return None


def _load_learned_value_model(score_value_mode, learned_value_model_path):
    if score_value_mode != "hybrid" or not learned_value_model_path:
        return None
    try:
        return load_linear_value_model(learned_value_model_path)
    except (OSError, ValueError):
        return None


def _exact_value_score_row_from_state(
    state_dice,
    category_idx,
    base_closed_mask,
    base_upper_total,
    base_yacht_bonus_available,
    endgame_value_table,
):
    if endgame_value_table is None:
        return None

    score = calc_score(state_dice, category_idx)
    next_mask = base_closed_mask | (1 << category_idx)
    next_upper_total = base_upper_total + score if category_idx < 6 else base_upper_total
    next_yacht_bonus_available = (
        base_yacht_bonus_available
        or (category_idx == CATS["Yacht"] and score >= 50)
    )
    next_state_value = endgame_value_table.lookup_state(
        next_mask,
        next_upper_total,
        next_yacht_bonus_available,
    )
    if next_state_value is None:
        return None

    immediate_gain = float(score)
    if category_idx < 6 and base_upper_total < 63 <= base_upper_total + score:
        immediate_gain += UPPER_BONUS_VALUE
    yacht_bonus_active = (
        category_idx != CATS["Yacht"]
        and score > 0
        and base_yacht_bonus_available
        and calc_score(state_dice, CATS["Yacht"]) == 50
    )
    if yacht_bonus_active:
        immediate_gain += YACHT_BONUS_CASH_IN

    return {
        "name": CATEGORY_NAMES[category_idx],
        "category_idx": category_idx,
        "score": score,
        "utility": immediate_gain + next_state_value,
        "immediate_gain": immediate_gain,
        "exact_next_state_value": next_state_value,
        "utility_mode": "endgame_value",
    }


def _value_table_for_cached_optimal(table_path):
    try:
        return load_endgame_value_table(table_path)
    except OSError:
        return None


@lru_cache(maxsize=262144)
def _value_optimal_terminal_utility_cached(
    state_dice,
    open_categories,
    base_closed_mask,
    base_upper_total,
    base_yacht_bonus_available,
    endgame_value_table_path,
):
    table = _value_table_for_cached_optimal(endgame_value_table_path)
    if table is None:
        return None

    best_key = None
    best_utility = float("-inf")
    for category_idx in open_categories:
        row = _exact_value_score_row_from_state(
            state_dice,
            category_idx,
            base_closed_mask,
            base_upper_total,
            base_yacht_bonus_available,
            table,
        )
        if row is None:
            return None
        row_key = (row["utility"], row["score"], -SACRIFICE_PRIORITY.get(row["name"], 99))
        if best_key is None or row_key > best_key:
            best_key = row_key
            best_utility = row["utility"]
    return best_utility


@lru_cache(maxsize=262144)
def _value_optimal_keep_transition_cached(
    kept_tuple,
    rerolls_remaining,
    open_categories,
    base_closed_mask,
    base_upper_total,
    base_yacht_bonus_available,
    endgame_value_table_path,
):
    total = 0.0
    for next_dice, prob in get_transition_distribution(kept_tuple):
        next_value = _value_optimal_turn_value_cached(
            next_dice,
            rerolls_remaining - 1,
            open_categories,
            base_closed_mask,
            base_upper_total,
            base_yacht_bonus_available,
            endgame_value_table_path,
        )
        if next_value is None:
            return None
        total += prob * next_value
    return total


@lru_cache(maxsize=262144)
def _value_optimal_turn_value_cached(
    state_dice,
    rerolls_remaining,
    open_categories,
    base_closed_mask,
    base_upper_total,
    base_yacht_bonus_available,
    endgame_value_table_path,
):
    stop_value = _value_optimal_terminal_utility_cached(
        state_dice,
        open_categories,
        base_closed_mask,
        base_upper_total,
        base_yacht_bonus_available,
        endgame_value_table_path,
    )
    if stop_value is None:
        return None
    if rerolls_remaining == 0:
        return stop_value

    best_value = stop_value
    for kept_tuple in get_keep_options(state_dice):
        value = _value_optimal_keep_transition_cached(
            kept_tuple,
            rerolls_remaining,
            open_categories,
            base_closed_mask,
            base_upper_total,
            base_yacht_bonus_available,
            endgame_value_table_path,
        )
        if value is None:
            return None
        if value > best_value:
            best_value = value
    return best_value


@lru_cache(maxsize=4096)
def _solve_best_move_cached(
    dice_key,
    rolls_left,
    open_categories,
    mode,
    scorecard_tuple,
    score_value_mode,
    endgame_value_table_path,
    learned_value_model_path,
    learned_value_max_mae,
    learned_value_min_turns,
    explain,
):
    dice = list(dice_key)
    scorecard = list(scorecard_tuple)
    open_categories = tuple(sorted(set(open_categories)))
    dice_tuple = tuple(sorted(dice))
    yacht_bonus_available = has_yacht_bonus(scorecard)
    endgame_value_table = _load_score_value_table(score_value_mode, endgame_value_table_path)
    learned_value_model = _load_learned_value_model(score_value_mode, learned_value_model_path)
    ev_optimal_mode = score_value_mode == "value_optimal"
    terminal_score_value_mode = "heuristic" if score_value_mode == "value_score_only" else ("value" if ev_optimal_mode else score_value_mode)
    direct_score_value_mode = "value" if score_value_mode in ("value_score_only", "value_optimal") else score_value_mode
    base_closed_mask = sum(1 << idx for idx, value in enumerate(scorecard[:len(CATEGORY_NAMES)]) if value is not None)
    base_upper_total = sum((value or 0) for value in scorecard[:6])
    base_yacht_bonus_available = has_yacht_bonus(scorecard)

    def exact_value_score_row(state_dice, category_idx):
        return _exact_value_score_row_from_state(
            state_dice,
            category_idx,
            base_closed_mask,
            base_upper_total,
            base_yacht_bonus_available,
            endgame_value_table,
        )

    if rolls_left == 0:
        if ev_optimal_mode and not explain:
            rows = [exact_value_score_row(tuple(dice), idx) for idx in open_categories]
            if rows and all(row is not None for row in rows):
                best_row = max(rows, key=lambda row: (row["utility"], row["score"]))
                return {
                    "keep_indices": [],
                    "expected_value": round(best_row["utility"], 2),
                    "dice_recommendations": [],
                    "message": best_row["name"],
                    "breakdown": [],
                    "strategy_mode": "optimal",
                    "score_value_mode": "value_optimal",
                    "primary_target": best_row["name"],
                    "summary": "",
                    "stage": "score",
                    "policy_source": "exact_value_optimal",
                }

        result = build_score_stage_advice(
            dice,
            scorecard,
            open_categories,
            mode,
            score_value_mode=direct_score_value_mode,
            endgame_value_table=endgame_value_table,
            learned_value_model=learned_value_model,
            learned_value_max_mae=learned_value_max_mae,
            learned_value_min_turns=learned_value_min_turns,
        )
        if ev_optimal_mode:
            result = dict(result)
            banked_total = _banked_score_total(scorecard)
            remaining_ev = float(result.get("expected_value", 0.0))
            expected_final = banked_total + remaining_ev
            target = result.get("primary_target") or result.get("message") or "점수 기록"
            result["summary"] = (
                f"점수 기록 추천: {target}, 기대 최종점수 {expected_final:.2f}점 "
                f"(확정 {banked_total}점 + 남은 기대 {remaining_ev:.2f}점)"
            )
            result["breakdown"] = [{
                "name": "기대 최종점수",
                "prob": 0.0,
                "meter": min(1.0, max(0.15, expected_final / 240.0)),
                "val_str": f"EV {expected_final:.2f}",
                "type": "decision",
                "keep_str": f"{target} 기록 선택",
                "keep_indices": [],
                "reason": (
                    f"확정 {banked_total}점에 이번 기록부터 남은 기대점수 "
                    f"{remaining_ev:.2f}점을 더한 full-game exact V 기준입니다."
                ),
            }] + list(result.get("breakdown") or [])
            result["strategy_mode"] = "optimal"
            result["score_value_mode"] = "value_optimal"
            result["policy_source"] = "exact_value_optimal"
        else:
            result.setdefault("policy_source", "exact")
        return result

    # --- 클로저 DP 함수 (per-call lru_cache) ---

    def evaluate_keep_transition(kept_tuple, rerolls_remaining, state_solver):
        if (
            ev_optimal_mode
            and endgame_value_table is not None
            and endgame_value_table_path
            and state_solver is exact_turn_value
        ):
            cached_value = _value_optimal_keep_transition_cached(
                kept_tuple,
                rerolls_remaining,
                open_categories,
                base_closed_mask,
                base_upper_total,
                base_yacht_bonus_available,
                endgame_value_table_path,
            )
            if cached_value is not None:
                return cached_value

        total = 0.0
        for next_dice, prob in get_transition_distribution(kept_tuple):
            total += prob * state_solver(next_dice, rerolls_remaining - 1)
        return total

    @lru_cache(maxsize=None)
    def terminal_best_utility(state_dice):
        best_key = None
        best_utility = float("-inf")
        for category_idx in open_categories:
            row = exact_value_score_row(state_dice, category_idx) if ev_optimal_mode else None
            if row is None:
                row = score_stage_category_advice(
                    list(state_dice),
                    scorecard,
                    category_idx,
                    mode,
                    score_value_mode=terminal_score_value_mode,
                    endgame_value_table=endgame_value_table,
                    learned_value_model=learned_value_model,
                    learned_value_max_mae=learned_value_max_mae,
                    learned_value_min_turns=learned_value_min_turns,
                )
            row_key = (row["utility"], row["score"], -SACRIFICE_PRIORITY.get(row["name"], 99))
            if best_key is None or row_key > best_key:
                best_key = row_key
                best_utility = row["utility"]
        return best_utility

    @lru_cache(maxsize=None)
    def exact_turn_value(state_dice, rerolls_remaining):
        if ev_optimal_mode and endgame_value_table is not None and endgame_value_table_path:
            cached_value = _value_optimal_turn_value_cached(
                state_dice,
                rerolls_remaining,
                open_categories,
                base_closed_mask,
                base_upper_total,
                base_yacht_bonus_available,
                endgame_value_table_path,
            )
            if cached_value is not None:
                return cached_value

        stop_value = terminal_best_utility(state_dice)
        if rerolls_remaining == 0:
            return stop_value
        best_value = stop_value
        for kept_tuple in get_keep_options(state_dice):
            value = evaluate_keep_transition(kept_tuple, rerolls_remaining, exact_turn_value)
            if value > best_value:
                best_value = value
        return best_value

    @lru_cache(maxsize=None)
    def target_success_value(state_dice, rerolls_remaining, category_idx):
        yacht_bonus_target = (
            category_idx == CATS["Yacht"]
            and yacht_bonus_available
            and CATS["Yacht"] not in open_categories
        )
        if not yacht_bonus_target:
            return get_precomputed_target_success_value(state_dice, rerolls_remaining, category_idx)

        stop_value = (
            1.0 if can_cash_yacht_bonus(state_dice, open_categories, scorecard) else 0.0
        ) if yacht_bonus_target else (
            1.0 if calc_score(state_dice, category_idx) > 0 else 0.0
        )
        if rerolls_remaining == 0:
            return stop_value
        best_value = stop_value
        for kept_tuple in get_keep_options(state_dice):
            value = evaluate_keep_transition(
                kept_tuple, rerolls_remaining,
                lambda nd, nr: target_success_value(nd, nr, category_idx),
            )
            if value > best_value:
                best_value = value
        return best_value

    @lru_cache(maxsize=None)
    def target_score_value(state_dice, rerolls_remaining, category_idx):
        return get_precomputed_target_score_value(state_dice, rerolls_remaining, category_idx)

    def terminal_target_hit(state_dice, category_idx):
        if category_idx == CATS["Yacht"] and yacht_bonus_available and CATS["Yacht"] not in open_categories:
            return can_cash_yacht_bonus(state_dice, open_categories, scorecard)
        return calc_score(state_dice, category_idx) > 0

    # --- keep action EV 계산 ---
    keep_action_values = []
    keep_ev_map = {}
    best_ev = float("-inf")
    for kept_tuple in get_keep_options(dice_tuple):
        value = evaluate_keep_transition(kept_tuple, rolls_left, exact_turn_value)
        keep_action_values.append((kept_tuple, value))
        keep_ev_map[kept_tuple] = value
        if value > best_ev:
            best_ev = value

    best_general_keeps = [kt for kt, v in keep_action_values if abs(v - best_ev) <= EPS]
    best_general_keep_tuple = choose_general_keep(best_general_keeps)

    if ev_optimal_mode and not explain:
        best_keep_tuple = best_general_keep_tuple
        chosen_ev = keep_ev_map.get(best_keep_tuple, best_ev)
        best_keep_indices = kept_tuple_to_indices(dice, best_keep_tuple)
        dice_recommendations = [
            {"index": i, "value": dice[i], "action": "keep" if i in best_keep_indices else "reroll", "confidence": 100}
            for i in range(5)
        ]
        return {
            "keep_indices": best_keep_indices,
            "expected_value": round(chosen_ev, 2),
            "dice_recommendations": dice_recommendations,
            "message": "",
            "breakdown": [],
            "strategy_mode": "optimal",
            "score_value_mode": "value_optimal",
            "primary_target": "기대점수 최적",
            "summary": "",
            "stage": "roll",
            "policy_source": "exact_value_optimal",
        }

    hand_cats = ["Yacht", "4 of a Kind", "Full House", "Large Straight", "Small Straight"]
    hand_priority = {"Yacht": 5, "Large Straight": 4, "Full House": 3, "4 of a Kind": 2, "Small Straight": 1}

    hand_targets, best_hand_moves = _compute_hand_targets(
        dice, dice_tuple, rolls_left, open_categories,
        hand_cats, hand_priority, yacht_bonus_available,
        evaluate_keep_transition, target_success_value, target_score_value,
    )

    # --- Cover 모드: 별도 함수에서 처리 후 바로 반환 ---
    if mode == "cover" and hand_targets and not ev_optimal_mode:
        return _build_cover_mode_result(
            dice, dice_tuple, rolls_left, hand_targets, keep_ev_map,
            evaluate_keep_transition, target_success_value, terminal_target_hit,
        )

    cover_fallback = mode == "cover" and not hand_targets

    # --- Focused 모드 keep 선택 ---
    current_upper = sum((v or 0) for v in scorecard[:6])
    upper_rows = build_upper_roll_rows(dice, scorecard, open_categories, mode, keep_ev_map)
    best_upper_row = upper_rows[0] if upper_rows else None
    upper_focus_override = False
    focus_ev_guard = None

    if ev_optimal_mode:
        best_keep_tuple = best_general_keep_tuple
    elif best_hand_moves:
        best_focus_move = max(best_hand_moves, key=lambda m: mode_rank(m, mode))
        focus_keep_tuple = best_focus_move["kept_tuple"]
        focus_ev = keep_ev_map.get(focus_keep_tuple, float("-inf"))
        focus_ev_gap = best_ev - focus_ev
        if (
            best_upper_row
            and current_upper >= 42
            and best_upper_row.get("ev", float("-inf")) > focus_ev + 1.0
        ):
            best_keep_tuple = best_general_keep_tuple
            upper_focus_override = True
        elif mode == "focused" and focus_ev_gap > FOCUSED_EV_GUARD_POINTS:
            best_keep_tuple = best_general_keep_tuple
            focus_ev_guard = {
                "focus_keep_tuple": focus_keep_tuple,
                "focus_ev": focus_ev,
                "best_ev": best_ev,
                "gap": focus_ev_gap,
                "target_name": best_focus_move.get("name"),
            }
        else:
            best_keep_tuple = focus_keep_tuple
    else:
        best_keep_tuple = best_general_keep_tuple

    chosen_ev = keep_ev_map.get(best_keep_tuple, best_ev)
    best_keep_indices = kept_tuple_to_indices(dice, best_keep_tuple)
    alternative_actions = sorted(
        ((kt, v) for kt, v in keep_action_values if kt != best_keep_tuple),
        key=lambda item: (item[1], len(item[0]), keep_values_desc(item[0])),
        reverse=True,
    )
    best_alternative = alternative_actions[0] if alternative_actions else None
    alternative_gap = chosen_ev - best_alternative[1] if best_alternative else None

    # --- Focused breakdown 빌드 (분리된 함수) ---
    breakdown = _build_focused_breakdown_rows(
        dice, rolls_left, best_hand_moves, open_categories,
        yacht_bonus_available, hand_priority,
        evaluate_keep_transition, target_success_value,
    )

    # 하단 족보 없거나 전부 0이면 상단 fallback
    hand_rows = [r for r in breakdown if r.get("type") == "hand"]
    all_hands_filled = (
        all(CATS[n] not in open_categories for n in ["4 of a Kind", "Full House", "Small Straight", "Large Straight"])
        and (CATS["Yacht"] not in open_categories and not yacht_bonus_available)
    )
    if (hand_rows and all(r.get("prob") == 0 for r in hand_rows)) or all_hands_filled:
        upper_cats = [CATS["Ones"], CATS["Twos"], CATS["Threes"], CATS["Fours"], CATS["Fives"], CATS["Sixes"]]
        upper_names = ["Ones", "Twos", "Threes", "Fours", "Fives", "Sixes"]
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
                "keep_indices": [i for i, v in enumerate(dice) if v == target_val],
                "reason": f"안전하게 상단 점수를 쌓을 수 있는 확률 {prob_get_more * 100:.1f}%",
            })

    # Upper bonus push 행 통합
    if upper_rows:
        pinned = [r for r in upper_rows if r.get("keep_indices") == best_keep_indices and r.get("keep_indices")]
        for row in upper_rows:
            if row in pinned:
                continue
            if row.get("bonus_delta") or current_upper >= 42:
                pinned.append(row)
            if len(pinned) >= 2:
                break
        if pinned:
            seen = {r["name"] for r in pinned}
            breakdown = pinned + [r for r in breakdown if not (r.get("type") == "upper" and r.get("name") in seen)]

    # 현재 추천 keep과 일치하는 best_row 선택
    matching_rows = [r for r in breakdown if r.get("keep_indices") == best_keep_indices and r.get("keep_indices")]
    best_row = None
    if matching_rows:
        hand_matches = [r for r in matching_rows if r.get("type") == "hand"]
        upper_matches = [r for r in matching_rows if r.get("type") == "upper"]
        bonus_upper = [r for r in upper_matches if r.get("bonus_delta")]
        if bonus_upper:
            best_row = max(bonus_upper, key=lambda r: (r.get("bonus_delta", 0), r.get("ev", 0.0), r.get("prob", 0.0), r.get("name", "")))
        elif upper_focus_override and upper_matches:
            best_row = max(upper_matches, key=lambda r: (r.get("ev", 0.0), r.get("bonus_delta", 0), r.get("prob", 0.0), r.get("name", "")))
        elif hand_matches:
            best_row = max(
                hand_matches,
                key=lambda r: mode_rank(
                    {"name": r["name"], "prob": r.get("prob", 0),
                     "priority": hand_priority.get(r["name"], 0),
                     "tie_values": keep_values_desc(tuple(dice[i] for i in r.get("keep_indices", [])))},
                    mode,
                ),
            )
        else:
            best_row = max(matching_rows, key=lambda r: (r.get("prob", 0), r.get("name", "")))

    # Small → Large Straight 업그레이드 체크
    straight_upgrade = None
    if mode == "focused" and best_row and best_row.get("name") == "Small Straight" and CATS["Large Straight"] in open_categories:
        small_prob = evaluate_keep_transition(
            best_keep_tuple, rolls_left,
            lambda nd, nr: target_success_value(nd, nr, CATS["Small Straight"]),
        )
        large_prob = evaluate_keep_transition(
            best_keep_tuple, rolls_left,
            lambda nd, nr: target_success_value(nd, nr, CATS["Large Straight"]),
        )
        if small_prob >= 1.0 - EPS and large_prob > EPS:
            straight_upgrade = {
                "name": "Large Straight",
                "prob": large_prob,
                "val_str": f"{large_prob * 100:.2f}%",
                "keep_indices": best_keep_indices,
                "reason": f"Large Straight {large_prob * 100:.1f}%를 노리되, 실패해도 Small Straight는 유지됩니다.",
            }

    explaining_row = straight_upgrade or (
        best_row if best_row and (mode == "focused" or best_row.get("prob", 0) >= 0.05) else None
    )

    kept_vals = [str(dice[i]) for i in sorted(best_keep_indices)]
    all_dice_kept = len(best_keep_indices) == 5

    # featured row를 breakdown 맨 앞으로
    if explaining_row and not all_dice_kept:
        if straight_upgrade:
            keep_label = "모두 굴리기" if not kept_vals else f"[{', '.join(kept_vals)}] keep"
            featured = [{
                "name": "Large Straight 업그레이드",
                "prob": straight_upgrade["prob"],
                "val_str": straight_upgrade["val_str"],
                "type": "hand",
                "keep_str": f"{keep_label} → 실패해도 Small Straight 유지",
                "keep_indices": best_keep_indices,
                "reason": straight_upgrade["reason"],
            }]
        elif explaining_row.get("name"):
            featured = [explaining_row]
        else:
            featured = []
        seen_featured = {r.get("name") for r in featured}
        breakdown = featured + [r for r in breakdown if r.get("name") not in seen_featured]

    # 메시지 / 요약 작성
    rec_msg = "모두 굴리기"
    optimal_action_label = _format_keep_tuple(dice, best_keep_tuple)
    banked_total = _banked_score_total(scorecard)
    expected_final = banked_total + chosen_ev
    if ev_optimal_mode:
        if all_dice_kept:
            rec_msg = "지금 기록 추천 (기대점수 최적)"
        elif best_keep_indices:
            rec_msg = f"[{', '.join(kept_vals)}] Keep (기대점수 최적)"
        else:
            rec_msg = "모두 굴리기 (기대점수 최적)"
    elif best_keep_indices:
        if all_dice_kept:
            rec_msg = "지금 기록 추천"
            if explaining_row and explaining_row.get("name"):
                rec_msg += f" ({explaining_row['name']})"
        else:
            rec_msg = f"[{', '.join(kept_vals)}] Keep"
            if straight_upgrade:
                rec_msg += " (Large Straight 업그레이드)"
            elif explaining_row and explaining_row.get("name") and not cover_fallback:
                rec_msg += f" ({explaining_row['name']} 노리기)"

    style_label = "기대점수 최적" if ev_optimal_mode else ("집중 공략" if mode != "cover" else "커버 플레이")
    if ev_optimal_mode:
        if alternative_gap is None:
            gap_text = ""
        elif alternative_gap <= EPS:
            gap_text = ", 차선책과 거의 동률"
        else:
            gap_text = f", 차선 대비 +{alternative_gap:.2f}점"
        summary = (
            f"{style_label} 추천: {optimal_action_label}, 기대 최종점수 {expected_final:.2f}점 "
            f"(확정 {banked_total}점 + 남은 기대 {chosen_ev:.2f}점){gap_text}"
        )
    elif cover_fallback and best_keep_indices:
        summary = f"{style_label}: 커버 대상이 없어 일반 추천으로 전환, [{', '.join(kept_vals)}] keep, 평가값 {chosen_ev:.2f}"
    elif cover_fallback:
        summary = f"{style_label}: 커버 대상이 없어 일반 추천으로 전환, 평가값 {chosen_ev:.2f}"
    elif straight_upgrade:
        summary = f"{style_label} 추천: Large Straight {straight_upgrade['val_str']}, 실패해도 Small Straight 유지"
    elif explaining_row:
        summary = build_summary(explaining_row, mode)
    elif best_keep_indices and not all_dice_kept:
        summary = f"{style_label} 추천: [{', '.join(kept_vals)}] keep, 평가값 {chosen_ev:.2f}"
    elif all_dice_kept:
        summary = f"{style_label} 추천: 지금 기록하는 편이 평가값 {chosen_ev:.2f}로 가장 좋습니다"
    else:
        summary = f"{style_label} 추천: 모두 굴리기, 평가값 {chosen_ev:.2f}"

    # decision rows (지금 멈추기 / 차선책 비교)
    decision_rows, stop_now_advice, stop_gain = _build_decision_rows(
        dice, scorecard, open_categories, mode,
        keep_action_values, best_keep_tuple, chosen_ev,
        explaining_row, straight_upgrade, all_dice_kept,
        score_value_mode=terminal_score_value_mode,
        endgame_value_table=endgame_value_table,
        learned_value_model=learned_value_model,
        learned_value_max_mae=learned_value_max_mae,
        learned_value_min_turns=learned_value_min_turns,
    )

    if ev_optimal_mode:
        if best_alternative:
            alt_label = _format_keep_tuple(dice, best_alternative[0])
            if alternative_gap <= EPS:
                alt_reason = f"차선책({alt_label})도 거의 같은 기대값입니다."
            else:
                alt_reason = f"차선책({alt_label})보다 기대 최종점수가 {alternative_gap:.2f}점 높습니다."
        else:
            alt_reason = "비교할 다른 keep 후보가 없는 확정 상태입니다."
        breakdown = [{
            "name": "기대 최종점수",
            "prob": 0.0,
            "meter": min(1.0, max(0.15, expected_final / 240.0)),
            "val_str": f"EV {expected_final:.2f}",
            "type": "decision",
            "keep_str": f"{optimal_action_label} 선택",
            "keep_indices": best_keep_indices,
            "reason": (
                f"확정 {banked_total}점에 남은 기대점수 {chosen_ev:.2f}점"
                "(즉시 기록 점수 + full-game exact V)을 합산한 기준입니다. "
                f"{alt_reason}"
            ),
        }] + breakdown

    recommendation_context_row = None if ev_optimal_mode else build_recommendation_context_row(
        mode, chosen_ev, explaining_row, straight_upgrade,
        best_keep_indices,
        stop_now_advice.get("primary_target") or stop_now_advice.get("message"),
        stop_gain,
    )
    if recommendation_context_row:
        breakdown = breakdown[:1] + [recommendation_context_row] + breakdown[1:]
    focus_ev_guard_row = _build_focus_ev_guard_row(dice, best_keep_tuple, focus_ev_guard)
    if focus_ev_guard_row:
        insert_at = 2 if recommendation_context_row else 1
        breakdown = breakdown[:insert_at] + [focus_ev_guard_row] + breakdown[insert_at:]

    if decision_rows:
        breakdown = breakdown[:3] + decision_rows[:2] + breakdown[3:]

    if all_dice_kept:
        if not ev_optimal_mode:
            summary = stop_now_advice.get("summary", summary)
        score_breakdown = stop_now_advice.get("breakdown", [])
        breakdown = score_breakdown[:3] + decision_rows[:2] + score_breakdown[3:]
        if ev_optimal_mode:
            breakdown = [{
                "name": "기대 최종점수",
                "prob": 0.0,
                "meter": min(1.0, max(0.15, expected_final / 240.0)),
                "val_str": f"EV {expected_final:.2f}",
                "type": "decision",
                "keep_str": f"{optimal_action_label} 선택",
                "keep_indices": best_keep_indices,
                "reason": (
                    f"확정 {banked_total}점 + 남은 기대 {chosen_ev:.2f}점 기준으로, "
                    "지금 기록하는 선택이 full-game exact V에서 가장 높은 기대 최종점수입니다."
                ),
            }] + breakdown
        if stop_now_advice.get("primary_target"):
            explaining_row = {"name": stop_now_advice["primary_target"]}

    dice_recommendations = [
        {"index": i, "value": dice[i], "action": "keep" if i in best_keep_indices else "reroll", "confidence": 100}
        for i in range(5)
    ]

    return {
        "keep_indices": best_keep_indices,
        "expected_value": round(chosen_ev, 2),
        "dice_recommendations": dice_recommendations,
        "message": rec_msg,
        "breakdown": breakdown,
        "strategy_mode": "optimal" if ev_optimal_mode else mode,
        "primary_target": "기대점수 최적" if ev_optimal_mode else (explaining_row["name"] if explaining_row else None),
        "summary": summary,
        "stage": "roll",
        "policy_source": "exact_value_optimal" if ev_optimal_mode else "exact",
    }


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------

def solve_best_move(
    dice,
    rolls_left,
    open_categories,
    strategy_mode="focused",
    scorecard=None,
    score_value_mode=None,
    endgame_value_table_path=None,
    learned_value_model_path=None,
    learned_value_max_mae=None,
    learned_value_min_turns=None,
    explain=True,
):
    mode = normalize_strategy_mode(strategy_mode)
    (
        resolved_score_value_mode,
        resolved_endgame_value_table_path,
        resolved_learned_value_model_path,
        resolved_learned_value_max_mae,
        resolved_learned_value_min_turns,
    ) = _resolve_score_value_options(
        score_value_mode,
        endgame_value_table_path,
        learned_value_model_path,
        learned_value_max_mae,
        learned_value_min_turns,
    )
    dice_key = tuple(int(v) for v in dice)
    try:
        rolls_left = int(rolls_left)
    except (TypeError, ValueError):
        rolls_left = 0

    normalized_open = []
    for idx in open_categories:
        try:
            cat_idx = int(idx)
        except (TypeError, ValueError):
            continue
        if 0 <= cat_idx < 12:
            normalized_open.append(cat_idx)

    result = _solve_best_move_cached(
        dice_key,
        rolls_left,
        tuple(sorted(set(normalized_open))),
        mode,
        scorecard_to_tuple(scorecard),
        resolved_score_value_mode,
        resolved_endgame_value_table_path,
        resolved_learned_value_model_path,
        resolved_learned_value_max_mae,
        resolved_learned_value_min_turns,
        bool(explain),
    )
    return deepcopy(result)


def get_solver_cache_info():
    return _solve_best_move_cached.cache_info()


def clear_solver_cache():
    _solve_best_move_cached.cache_clear()
    _value_optimal_terminal_utility_cached.cache_clear()
    _value_optimal_keep_transition_cached.cache_clear()
    _value_optimal_turn_value_cached.cache_clear()
