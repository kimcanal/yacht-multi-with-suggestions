from .constants import (
    CATS,
    CATEGORY_NAMES,
    EPS,
    FOCUSED_HAND_PRIORITY,
    HAND_FIXED_SCORES,
    SACRIFICE_PRIORITY,
    UPPER_CAT_NAMES,
)
from .scoring import calc_score, has_yacht_bonus


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
    if not isinstance(scorecard, list):
        return base
    for idx, value in enumerate(scorecard[:12]):
        base[idx] = value
    return base


def scorecard_to_tuple(scorecard):
    return tuple(normalize_scorecard(scorecard))


def score_stage_upper_bonus_push(face, count, current_upper, score, mode):
    projected_upper = current_upper + score
    bonus_delta = 35 if current_upper < 63 <= projected_upper else 0
    bonus_push = 0.0

    if current_upper < 63:
        progress = max(0, min(score, 63 - current_upper))
        bonus_push += progress * 0.35
        if count >= 3:
            bonus_push += face * (2.4 if mode == "focused" else 2.0)
        elif count == 2 and face >= 5:
            bonus_push += face * (1.2 if mode == "focused" else 0.8)

    return bonus_push + bonus_delta, bonus_delta


def score_stage_category_advice(dice, scorecard, category_idx, mode):
    name = CATEGORY_NAMES[category_idx]
    score = calc_score(dice, category_idx)
    utility = float(score)
    reason = f"즉시 {score}점"
    yacht_bonus_active = (
        category_idx != CATS["Yacht"]
        and score > 0
        and has_yacht_bonus(scorecard)
        and calc_score(dice, CATS["Yacht"]) == 50
    )

    if category_idx < 6:
        face = category_idx + 1
        count = dice.count(face)
        current_upper = sum((value or 0) for value in scorecard[:6])
        bonus_push, bonus_delta = score_stage_upper_bonus_push(face, count, current_upper, score, mode)
        utility += bonus_push
        if bonus_delta:
            reason = "이번 기록으로 Upper Bonus +35를 바로 확보합니다"
        elif count >= 3 and face >= 4:
            reason = f"{name} {score}점으로 상단 보너스 페이스를 강하게 유지합니다"
        elif count >= 3:
            reason = f"{name} {score}점으로 상단 점수를 안정적으로 쌓습니다"
        elif score > 0:
            reason = f"{name} {score}점으로 손실 없이 턴을 정리합니다"
        else:
            reason = f"{name}에 기록하면 0점 처리입니다"
    elif category_idx == CATS["Choice"]:
        if score >= 20:
            utility += 3.0 if mode == "cover" else 1.5
            reason = f"즉시 {score}점으로 무난하게 착지할 수 있습니다"
        elif score > 0:
            utility += 1.0
            reason = f"Choice {score}점으로 이번 턴 손실을 줄입니다"
        else:
            reason = "Choice도 이번 턴엔 점수가 나지 않습니다"
    elif category_idx == CATS["4 of a Kind"]:
        if score > 0:
            utility += 6.0 if mode == "focused" else 4.0
            reason = f"4 of a Kind {score}점으로 하단 고점을 확보합니다"
        else:
            utility -= 1.5
            reason = "4 of a Kind에 적으면 0점입니다"
    elif category_idx == CATS["Full House"]:
        if score > 0:
            utility += 4.5 if mode == "focused" else 3.0
            reason = f"Full House {score}점으로 점수 효율이 좋습니다"
        else:
            utility -= 1.5
            reason = "Full House에 적으면 0점입니다"
    elif category_idx == CATS["Small Straight"]:
        if score > 0:
            utility += 2.5
            reason = "Small Straight 15점을 바로 확보합니다"
        else:
            utility -= 1.0
            reason = "Small Straight에 적으면 0점입니다"
    elif category_idx == CATS["Large Straight"]:
        if score > 0:
            utility += 6.0
            reason = "Large Straight 30점은 바로 챙길 가치가 큽니다"
        else:
            utility -= 1.0
            reason = "Large Straight에 적으면 0점입니다"
    elif category_idx == CATS["Yacht"]:
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
    return (row["score"], SACRIFICE_PRIORITY.get(row["name"], 99))


def build_score_stage_advice(dice, scorecard, open_categories, mode):
    scorecard = normalize_scorecard(scorecard)
    rows = [score_stage_category_advice(dice, scorecard, idx, mode) for idx in open_categories]
    positive_rows = [row for row in rows if row["score"] > 0]
    positive_rows.sort(key=lambda row: (row["utility"], row["score"]), reverse=True)

    sacrifice_rows = [row for row in rows if row["score"] == 0]
    if not sacrifice_rows:
        sacrifice_rows = sorted(rows, key=_score_stage_sacrifice_key)[:2]
    else:
        sacrifice_rows.sort(key=_score_stage_sacrifice_key)

    display_rows = []
    for row in positive_rows[:3]:
        display_rows.append(
            {
                "name": row["name"],
                "prob": 0.0,
                "meter": min(1.0, max(0.15, row["utility"] / 50.0)),
                "val_str": f"{row['score']}점",
                "type": "score",
                "keep_str": "지금 기록 추천",
                "keep_indices": [],
                "reason": row["reason"],
            }
        )

    for row in sacrifice_rows:
        if any(existing["name"] == row["name"] for existing in display_rows):
            continue
        display_rows.append(
            {
                "name": row["name"],
                "prob": 0.0,
                "meter": 0.18,
                "val_str": f"{row['score']}점",
                "type": "sacrifice",
                "keep_str": "망한 턴 정리용 희생 후보",
                "keep_indices": [],
                "reason": (
                    "이번 턴을 넘겨야 하면 손실이 작은 칸부터 비우는 편이 좋습니다"
                    if row["name"] != "Yacht"
                    else "Yacht는 마지막 수단용 희생 칸 후보로만 보세요"
                ),
            }
        )
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


def build_upper_roll_rows(dice, scorecard, open_categories, mode, keep_ev_map):
    current_upper = sum((value or 0) for value in scorecard[:6])
    if current_upper >= 63:
        return []

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
        keep_ev = keep_ev_map.get(kept_tuple, 0.0)
        reroll_count = 5 - len(keep_indices)
        prob_get_more = 1.0 if reroll_count == 0 else 1.0 - ((5.0 / 6.0) ** reroll_count)
        remaining_after_score = max(0, 63 - (current_upper + current_score))
        keep_vals = [str(dice[idx]) for idx in sorted(keep_indices)]
        keep_label = f"[{', '.join(keep_vals)}] keep"

        if bonus_delta:
            reason = f"지금 {cat_name}에 적으면 Upper Bonus +35를 바로 확보할 수 있습니다."
        elif current_score > 0:
            reason = f"현재 상단 {current_upper}/63. {cat_name} {current_score}점이면 목표까지 {remaining_after_score}점 남습니다."
        else:
            reason = f"{cat_name}를 모아 상단 보너스 페이스를 이어갈 수 있습니다."

        rows.append(
            {
                "name": cat_name,
                "prob": prob_get_more,
                "meter": min(1.0, max(prob_get_more, keep_ev / 60.0)),
                "val_str": f"EV {keep_ev:.1f}",
                "type": "upper",
                "keep_str": f"{keep_label} → Upper Bonus 페이스",
                "keep_indices": keep_indices,
                "reason": reason,
                "summary_text": f"상단 보너스 추천: {cat_name} EV {keep_ev:.1f}",
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
