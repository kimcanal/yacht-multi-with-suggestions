from yacht_ai.decision_confidence import classify_alternative_gap


def _as_percent(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return f"{number * 100:.1f}%"


def _top_reason_lines(rows, limit=3):
    lines = []
    for row in rows:
        name = row.get("name")
        value = row.get("val_str")
        reason = row.get("reason")
        keep = row.get("keep_str")
        parts = []
        if name:
            parts.append(str(name))
        if value:
            parts.append(str(value))
        head = " · ".join(parts)
        if reason:
            line = f"{head}: {reason}" if head else str(reason)
        elif keep:
            line = f"{head}: {keep}" if head else str(keep)
        else:
            line = head
        if line:
            lines.append(line)
        if len(lines) >= limit:
            break
    return lines


def _tradeoff_lines(rows, limit=2):
    lines = []
    for row in rows:
        if row.get("type") not in ("decision", "risk", "sacrifice"):
            continue
        name = row.get("name") or "비교"
        value = row.get("val_str")
        reason = row.get("reason") or row.get("keep_str")
        if value and reason:
            lines.append(f"{name} {value}: {reason}")
        elif reason:
            lines.append(f"{name}: {reason}")
        if len(lines) >= limit:
            break
    return lines


def _source_label(policy_source):
    if policy_source == "learned_roll_policy":
        return "학습 정책 모델"
    if policy_source == "exact_value_optimal":
        return "Full-game exact V"
    return "Exact solver"


def _method_note(policy_source, stage):
    if policy_source == "learned_roll_policy":
        return (
            "이번 굴림 선택은 exact solver가 만든 teacher 데이터를 학습한 정책 모델이 먼저 냈고, "
            "confidence 기준을 넘은 경우에만 채택됩니다."
        )
    if policy_source == "exact_value_optimal":
        return (
            "현재 기록 점수와 이번 선택 이후의 기대점수를 합산해 기대 최종점수가 가장 큰 선택을 고릅니다. "
            "이후 기대점수에는 이번 턴의 기록과 남은 모든 턴의 full-game exact V가 포함됩니다."
        )
    if stage == "score":
        return "점수 기록 단계는 현재 점수와 남은 칸의 장기 가치를 utility로 비교한 계산 결과입니다."
    return "현재 Yacht 상태공간은 작아서 모든 합리적 keep 후보를 동적계획법으로 직접 비교할 수 있습니다."


def _learning_note(policy_source):
    if policy_source == "learned_roll_policy":
        return (
            "모델은 스스로 결정을 흉내 내는 실행 정책이고, 낮은 확신이나 위험한 상태에서는 exact solver로 돌아갑니다. "
            "다음 단계의 self-learning은 self-play 데이터를 더 쌓아 win-rate/value model을 붙이는 방식이 좋습니다."
        )
    if policy_source == "exact_value_optimal":
        return (
            "이 모드는 학습 모델 없이 full-game exact value table을 직접 조회합니다. "
            "현재 목표는 승률이 아니라 기대 최종점수 최대화입니다."
        )
    return (
        "이 결정에는 ML/DL 모델이 꼭 필요하지 않습니다. 지금 게임처럼 상태공간이 작으면 exact solver가 teacher 역할을 하며, "
        "모델은 그 결정을 빠르게 근사하거나 상대/승률 같은 더 큰 맥락을 학습할 때 가치가 커집니다."
    )


def build_decision_report(result, dice, rolls_left, strategy_mode, scorecard, open_categories):
    rows = result.get("breakdown") if isinstance(result.get("breakdown"), list) else []
    stage = result.get("stage") or ("score" if rolls_left == 0 else "roll")
    policy_source = result.get("policy_source", "exact")
    confidence = result.get("policy_confidence")
    action_margin = classify_alternative_gap(result.get("alternative_gap"))
    confidence_text = _as_percent(confidence) if confidence is not None else (
        "계산 확정" if policy_source in ("exact", "exact_value_optimal") else None
    )
    primary_target = result.get("primary_target") or result.get("message") or "추천 없음"
    summary = result.get("summary") or result.get("message") or "추천을 계산했습니다."

    report = {
        "title": "AI 결론 리포트",
        "conclusion": summary,
        "decision": {
            "stage": stage,
            "mode": strategy_mode,
            "target": primary_target,
            "action": result.get("message") or primary_target,
            "expected_value": result.get("expected_final_score", result.get("expected_value")),
        },
        "method": {
            "source": policy_source,
            "label": _source_label(policy_source),
            "confidence": confidence,
            "confidence_text": confidence_text,
            "decision_margin": action_margin["gap"],
            "decision_margin_key": action_margin["key"],
            "decision_margin_text": action_margin["label"],
            "decision_margin_note": action_margin["description"],
            "note": _method_note(policy_source, stage),
        },
        "why": _top_reason_lines(rows),
        "tradeoffs": _tradeoff_lines(rows),
        "learning_note": _learning_note(policy_source),
        "state": {
            "dice": list(dice)[:5] if isinstance(dice, list) else [],
            "rolls_left": rolls_left,
            "open_slots": len(open_categories) if isinstance(open_categories, (list, tuple)) else 0,
            "filled_slots": 12 - len(open_categories) if isinstance(open_categories, (list, tuple)) else None,
            "upper_score": sum((value or 0) for value in scorecard[:6]) if isinstance(scorecard, list) else 0,
        },
    }
    return report
