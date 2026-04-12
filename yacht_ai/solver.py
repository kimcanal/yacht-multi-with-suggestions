from copy import deepcopy
from functools import lru_cache

from .advice import (
    build_reason,
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
from .constants import CATS, EPS, SACRIFICE_PRIORITY
from .scoring import (
    calc_score,
    can_cash_yacht_bonus,
    get_keep_options,
    get_outcomes_probs,
    has_yacht_bonus,
    keep_values_desc,
    kept_tuple_to_indices,
)


@lru_cache(maxsize=4096)
def _solve_best_move_cached(dice_key, rolls_left, open_categories, mode, scorecard_tuple):
    dice = list(dice_key)
    scorecard = list(scorecard_tuple)
    open_categories = tuple(sorted(set(open_categories)))
    dice_tuple = tuple(sorted(dice))
    yacht_bonus_available = has_yacht_bonus(scorecard)

    if rolls_left == 0:
        return build_score_stage_advice(dice, scorecard, open_categories, mode)

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
        best_utility = float("-inf")
        for category_idx in open_categories:
            row = score_stage_category_advice(list(state_dice), scorecard, category_idx, mode)
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

        best_value = float("-inf")
        for kept_tuple in get_keep_options(state_dice):
            value = evaluate_keep_transition(kept_tuple, rerolls_remaining, exact_turn_value)
            if value > best_value:
                best_value = value
        return best_value

    @lru_cache(maxsize=None)
    def target_success_value(state_dice, rerolls_remaining, category_idx):
        if rerolls_remaining == 0:
            if category_idx == CATS["Yacht"] and yacht_bonus_available and CATS["Yacht"] not in open_categories:
                return 1.0 if can_cash_yacht_bonus(state_dice, open_categories, scorecard) else 0.0
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

    def terminal_target_hit(state_dice, category_idx):
        if category_idx == CATS["Yacht"] and yacht_bonus_available and CATS["Yacht"] not in open_categories:
            return can_cash_yacht_bonus(state_dice, open_categories, scorecard)
        return calc_score(state_dice, category_idx) > 0

    keep_action_values = []
    keep_ev_map = {}
    best_ev = float("-inf")
    for kept_tuple in get_keep_options(dice_tuple):
        value = evaluate_keep_transition(kept_tuple, rolls_left, exact_turn_value)
        keep_action_values.append((kept_tuple, value))
        keep_ev_map[kept_tuple] = value
        if value > best_ev:
            best_ev = value

    hand_cats = ["Yacht", "4 of a Kind", "Full House", "Large Straight", "Small Straight"]
    hand_priority = {"Yacht": 5, "Large Straight": 4, "Full House": 3, "4 of a Kind": 2, "Small Straight": 1}
    hand_targets = []
    best_hand_moves = []

    for cat_name in hand_cats:
        cat_idx = CATS[cat_name]
        yacht_bonus_target = cat_name == "Yacht" and yacht_bonus_available and cat_idx not in open_categories
        if cat_idx not in open_categories and not yacht_bonus_target:
            continue

        display_name = "Yacht Bonus" if yacht_bonus_target else cat_name
        hand_targets.append(
            {
                "name": display_name,
                "internal_name": cat_name,
                "category_idx": cat_idx,
                "bonus_active": yacht_bonus_target,
                "priority": hand_priority[cat_name],
            }
        )

        action_rows = []
        for kept_tuple in get_keep_options(dice_tuple):
            success_prob = evaluate_keep_transition(
                kept_tuple,
                rolls_left,
                lambda next_dice, next_rolls: target_success_value(next_dice, next_rolls, cat_idx),
            )
            expected_score = 0.0
            if cat_name == "4 of a Kind":
                expected_score = evaluate_keep_transition(
                    kept_tuple,
                    rolls_left,
                    lambda next_dice, next_rolls: target_score_value(next_dice, next_rolls, cat_idx),
                )
            action_rows.append(
                {
                    "kept_tuple": kept_tuple,
                    "prob": success_prob,
                    "expected_score": expected_score,
                }
            )

        max_prob = max((row["prob"] for row in action_rows), default=0.0)
        if max_prob <= EPS:
            continue

        tie_rows = [row for row in action_rows if abs(row["prob"] - max_prob) <= EPS]
        best_keep_for_cat = choose_target_keep(cat_name, [row["kept_tuple"] for row in tie_rows])
        selected_row = next(row for row in tie_rows if row["kept_tuple"] == best_keep_for_cat)
        conditional_ev = selected_row["expected_score"] / max_prob if cat_name == "4 of a Kind" and max_prob > EPS else 0.0

        best_hand_moves.append(
            {
                "name": display_name,
                "internal_name": cat_name,
                "bonus_active": yacht_bonus_target,
                "category_idx": cat_idx,
                "prob": max_prob,
                "kept_tuple": best_keep_for_cat,
                "keep_indices": kept_tuple_to_indices(dice, best_keep_for_cat),
                "priority": hand_priority[cat_name],
                "tie_values": list(keep_values_desc(best_keep_for_cat)),
                "tie_keeps": [
                    {
                        "keep_indices": kept_tuple_to_indices(dice, row["kept_tuple"]),
                        "values": list(keep_values_desc(row["kept_tuple"])),
                    }
                    for row in tie_rows
                ],
                "conditional_ev": conditional_ev,
            }
        )

    cover_success_prob = None
    cover_fail_prob = None
    cover_target_rows = []
    cover_fallback = mode == "cover" and not hand_targets

    if mode == "cover" and hand_targets:

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
                rows.append(
                    {
                        "name": target["name"],
                        "prob": prob,
                        "priority": target["priority"],
                    }
                )
            return cover_upgrade_rank(rows)

        def terminal_cover_hit(state_dice):
            return any(terminal_target_hit(state_dice, target["category_idx"]) for target in hand_targets)

        @lru_cache(maxsize=None)
        def cover_success_value(state_dice, rerolls_remaining):
            if rerolls_remaining == 0:
                return 1.0 if terminal_cover_hit(state_dice) else 0.0
            return cover_best_action(state_dice, rerolls_remaining)[1]

        @lru_cache(maxsize=None)
        def cover_best_action(state_dice, rerolls_remaining):
            if rerolls_remaining == 0:
                return ((), 1.0 if terminal_cover_hit(state_dice) else 0.0)

            best_value = float("-inf")
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
                    keep_values_desc(kept_tuple),
                ),
            )
            return (best_keep, best_value)

        @lru_cache(maxsize=None)
        def cover_policy_target_prob(state_dice, rerolls_remaining, category_idx):
            if rerolls_remaining == 0:
                return 1.0 if terminal_target_hit(state_dice, category_idx) else 0.0
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
            cover_target_rows.append(
                {
                    "name": target["name"],
                    "internal_name": target["internal_name"],
                    "bonus_active": target["bonus_active"],
                    "prob": prob,
                    "priority": target["priority"],
                }
            )

        cover_target_rows.sort(
            key=lambda row: (row["prob"], row["priority"], hand_score_hint(row["name"], row)),
            reverse=True,
        )

    current_upper = sum((value or 0) for value in scorecard[:6])
    best_general_keeps = [kept for kept, value in keep_action_values if abs(value - best_ev) <= EPS]
    best_general_keep_tuple = choose_general_keep(best_general_keeps)
    upper_rows = build_upper_roll_rows(dice, scorecard, open_categories, mode, keep_ev_map)
    best_upper_row = upper_rows[0] if upper_rows else None
    upper_focus_override = False

    if mode == "cover" and hand_targets:
        pass
    elif best_hand_moves:
        best_focus_move = max(best_hand_moves, key=lambda move: mode_rank(move, mode))
        focus_keep_tuple = best_focus_move["kept_tuple"]
        focus_ev = keep_ev_map.get(focus_keep_tuple, float("-inf"))
        if (
            best_upper_row
            and current_upper >= 42
            and best_upper_row.get("ev", float("-inf")) > focus_ev + 1.0
        ):
            best_keep_tuple = best_general_keep_tuple
            upper_focus_override = True
        else:
            best_keep_tuple = focus_keep_tuple
    else:
        best_keep_tuple = best_general_keep_tuple

    chosen_ev = keep_ev_map.get(best_keep_tuple, best_ev)
    best_keep_indices = kept_tuple_to_indices(dice, best_keep_tuple)

    if mode == "cover" and hand_targets:
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
            breakdown.append(
                {
                    "name": row["name"],
                    "prob": row["prob"],
                    "meter": row["prob"],
                    "val_str": f"{row['prob'] * 100:.2f}%",
                    "type": "hand",
                    "keep_str": f"{keep_label} → 커버 경로에서 함께 열리는 후보",
                    "keep_indices": best_keep_indices,
                    "reason": build_reason(row["name"], row["prob"], mode),
                }
            )

        dice_recommendations = []
        for idx in range(5):
            action = "keep" if idx in best_keep_indices else "reroll"
            dice_recommendations.append(
                {
                    "index": idx,
                    "value": dice[idx],
                    "action": action,
                    "confidence": 100,
                }
            )

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
    hand_cats_display = ["4 of a Kind", "Full House", "Small Straight", "Large Straight", "Yacht"]

    for cat_name in hand_cats_display:
        cat_idx = CATS[cat_name]
        yacht_bonus_target = cat_name == "Yacht" and yacht_bonus_available and cat_idx not in open_categories
        if cat_idx not in open_categories and not yacht_bonus_target:
            continue

        same_cat_moves = [move for move in best_hand_moves if move.get("internal_name") == cat_name]
        if not same_cat_moves:
            keep_str = "Keep 후보 없음: 다시 돌리기" if len(set(dice)) == 5 and cat_name in ("Yacht", "4 of a Kind", "Full House") else "불가능"
            breakdown.append(
                {
                    "name": "Yacht Bonus" if yacht_bonus_target else cat_name,
                    "prob": 0.0,
                    "val_str": "",
                    "type": "hand",
                    "keep_str": keep_str,
                    "keep_indices": [],
                    "reason": "현재 턴에는 이 족보를 현실적으로 노리기 어렵습니다.",
                }
            )
            continue

        move = same_cat_moves[0]
        if move["prob"] == 0:
            breakdown.append(
                {
                    "name": move["name"],
                    "prob": 0.0,
                    "val_str": "",
                    "type": "hand",
                    "keep_str": "불가능",
                    "keep_indices": [],
                    "reason": "이번 상태에선 완성 경로가 없습니다.",
                }
            )
            continue

        if cat_name == "4 of a Kind":
            keep_vals = [str(dice[i]) for i in sorted(move["keep_indices"])]
            keep_str = f"[{', '.join(keep_vals)}]" if keep_vals else "모두 굴리기"
            keep_str = f"{keep_str} keep → 성공시 평균 {round(move.get('conditional_ev', 0), 1)}점"
            breakdown.append(
                {
                    "name": move["name"],
                    "prob": move["prob"],
                    "val_str": f"{move['prob'] * 100:.2f}%",
                    "type": "hand",
                    "keep_str": keep_str,
                    "keep_indices": move["keep_indices"],
                    "reason": build_reason(move["name"], move["prob"], mode),
                }
            )
            continue

        tie_keeps = move.get("tie_keeps") or []
        if cat_name == "Yacht":
            keep_vals = [str(dice[i]) for i in sorted(move["keep_indices"])]
            keep_str = f"[{', '.join(keep_vals)}]" if keep_vals else "모두 굴리기"
            final_keep = keep_str if keep_str == "모두 굴리기" else f"{keep_str} keep"
            score_str = "Yacht Bonus +100 발동" if move.get("bonus_active") else "50점 (확정)"
            breakdown.append(
                {
                    "name": move["name"],
                    "prob": move["prob"],
                    "val_str": f"{move['prob'] * 100:.2f}%",
                    "type": "hand",
                    "keep_str": f"{final_keep} → {score_str}",
                    "keep_indices": move["keep_indices"],
                    "reason": build_reason(move["name"], move["prob"], mode),
                }
            )
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

            if cat_name in ("Small Straight", "Large Straight"):
                min_len = min((value_len for (_, value_len) in unique_values.items()), default=0)
                display = [values for values, value_len in unique_values.items() if value_len == min_len]
                display.sort(reverse=True)
                display = display[:1]
            elif cat_name == "Full House" and tuple() in unique_values:
                display = [tuple()]
            else:
                display = sorted(unique_values.keys(), reverse=True)[:3]

            keep_labels = [f"[{', '.join(map(str, values))}]" if values else "모두 굴리기" for values in display]
            keep_str = keep_labels[0] if len(keep_labels) == 1 else f"Keep 후보: {', '.join(keep_labels)}"
        else:
            keep_vals = [str(dice[i]) for i in sorted(move["keep_indices"])]
            keep_str = f"[{', '.join(keep_vals)}]" if keep_vals else "모두 굴리기"

        if cat_name == "Large Straight":
            score_str = "30점 (확정)"
        elif cat_name == "Small Straight":
            score_str = "15점 (확정)"
        else:
            score_str = "합계 점수"

        keep_prefix = keep_str if keep_str == "모두 굴리기" or "Keep 후보" in keep_str else f"{keep_str} keep"
        breakdown.append(
            {
                "name": move["name"],
                "prob": move["prob"],
                "val_str": f"{move['prob'] * 100:.2f}%",
                "type": "hand",
                "keep_str": f"{keep_prefix} → {score_str}",
                "keep_indices": move["keep_indices"],
                "reason": build_reason(move["name"], move["prob"], mode),
            }
        )

    hand_rows = [row for row in breakdown if row.get("type") == "hand"]
    all_hands_filled = (
        all(CATS[name] not in open_categories for name in ["4 of a Kind", "Full House", "Small Straight", "Large Straight"])
        and (CATS["Yacht"] not in open_categories and not yacht_bonus_available)
    )

    if (hand_rows and all(row.get("prob") == 0 for row in hand_rows)) or all_hands_filled:
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

            breakdown.append(
                {
                    "name": cat_name,
                    "prob": prob_get_more,
                    "val_str": f"{prob_get_more * 100:.2f}%",
                    "type": "upper",
                    "keep_str": f"현재 나온 {target_val}들을 모두 Keep → {target_val}{josa} 적어도 하나 더 뜰 확률",
                    "keep_indices": [i for i, value in enumerate(dice) if value == target_val],
                    "reason": f"안전하게 상단 점수를 쌓을 수 있는 확률 {prob_get_more * 100:.1f}%",
                }
            )

    if upper_rows:
        pinned_upper_rows = [
            row for row in upper_rows if row.get("keep_indices") == best_keep_indices and row.get("keep_indices")
        ]
        for row in upper_rows:
            if row in pinned_upper_rows:
                continue
            if row.get("bonus_delta") or current_upper >= 42:
                pinned_upper_rows.append(row)
            if len(pinned_upper_rows) >= 2:
                break

        if pinned_upper_rows:
            seen_upper = {row["name"] for row in pinned_upper_rows}
            breakdown = pinned_upper_rows + [
                row
                for row in breakdown
                if not (row.get("type") == "upper" and row.get("name") in seen_upper)
            ]

    matching_rows = [row for row in breakdown if row.get("keep_indices") == best_keep_indices and row.get("keep_indices")]

    best_row = None
    if matching_rows:
        hand_matches = [row for row in matching_rows if row.get("type") == "hand"]
        upper_matches = [row for row in matching_rows if row.get("type") == "upper"]
        bonus_upper_matches = [row for row in upper_matches if row.get("bonus_delta")]
        if bonus_upper_matches:
            best_row = max(
                bonus_upper_matches,
                key=lambda row: (row.get("bonus_delta", 0), row.get("ev", 0.0), row.get("prob", 0.0), row.get("name", "")),
            )
        elif upper_focus_override and upper_matches:
            best_row = max(
                upper_matches,
                key=lambda row: (row.get("ev", 0.0), row.get("bonus_delta", 0), row.get("prob", 0.0), row.get("name", "")),
            )
        elif hand_matches:
            best_row = max(
                hand_matches,
                key=lambda row: mode_rank(
                    {
                        "name": row["name"],
                        "prob": row.get("prob", 0),
                        "priority": hand_priority.get(row["name"], 0),
                        "tie_values": keep_values_desc(tuple(dice[i] for i in row.get("keep_indices", []))),
                    },
                    mode,
                ),
            )
        else:
            best_row = max(matching_rows, key=lambda row: (row.get("prob", 0), row.get("name", "")))

    straight_upgrade = None
    if mode == "focused" and best_row and best_row.get("name") == "Small Straight" and CATS["Large Straight"] in open_categories:
        small_prob_for_keep = evaluate_keep_transition(
            best_keep_tuple,
            rolls_left,
            lambda next_dice, next_rolls: target_success_value(next_dice, next_rolls, CATS["Small Straight"]),
        )
        large_prob_for_keep = evaluate_keep_transition(
            best_keep_tuple,
            rolls_left,
            lambda next_dice, next_rolls: target_success_value(next_dice, next_rolls, CATS["Large Straight"]),
        )
        if small_prob_for_keep >= 1.0 - EPS and large_prob_for_keep > EPS:
            straight_upgrade = {
                "name": "Large Straight",
                "prob": large_prob_for_keep,
                "val_str": f"{large_prob_for_keep * 100:.2f}%",
                "keep_indices": best_keep_indices,
                "reason": f"Large Straight {large_prob_for_keep * 100:.1f}%를 노리되, 실패해도 Small Straight는 유지됩니다.",
            }

    explaining_row = straight_upgrade or (best_row if best_row and (mode == "focused" or best_row.get("prob", 0) >= 0.05) else None)
    kept_vals = [str(dice[i]) for i in sorted(best_keep_indices)]
    rec_msg = "모두 굴리기"
    if best_keep_indices:
        rec_msg = f"[{', '.join(kept_vals)}] Keep"
        if straight_upgrade:
            rec_msg += " (Large Straight 업그레이드)"
        elif explaining_row and explaining_row.get("name") and not cover_fallback:
            rec_msg += f" ({explaining_row['name']} 노리기)"

    style_label = "집중 공략" if mode != "cover" else "커버 플레이"
    if cover_fallback and best_keep_indices:
        summary = f"{style_label}: 커버 대상이 없어 일반 추천으로 전환, [{', '.join(kept_vals)}] keep, 기대값 {chosen_ev:.2f}"
    elif cover_fallback:
        summary = f"{style_label}: 커버 대상이 없어 일반 추천으로 전환, 기대값 {chosen_ev:.2f}"
    elif straight_upgrade:
        summary = f"{style_label} 추천: Large Straight {straight_upgrade['val_str']}, 실패해도 Small Straight 유지"
    elif explaining_row:
        summary = build_summary(explaining_row, mode)
    elif best_keep_indices:
        summary = f"{style_label} 추천: [{', '.join(kept_vals)}] keep, 기대값 {chosen_ev:.2f}"
    else:
        summary = f"{style_label} 추천: 모두 굴리기, 기대값 {chosen_ev:.2f}"

    dice_recommendations = []
    for idx in range(5):
        action = "keep" if idx in best_keep_indices else "reroll"
        dice_recommendations.append(
            {
                "index": idx,
                "value": dice[idx],
                "action": action,
                "confidence": 100,
            }
        )

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


def solve_best_move(dice, rolls_left, open_categories, strategy_mode="focused", scorecard=None):
    mode = normalize_strategy_mode(strategy_mode)
    dice_key = tuple(int(value) for value in dice)
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
        scorecard_to_tuple(scorecard),
    )
    return deepcopy(result)


def get_solver_cache_info():
    return _solve_best_move_cached.cache_info()


def clear_solver_cache():
    _solve_best_move_cached.cache_clear()
