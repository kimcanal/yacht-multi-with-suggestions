#!/usr/bin/env python3
"""Golden-case regression checks for the Yacht AI solver."""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yacht_engine

GOLDEN_CASES = [
    {
        "name": "straight_upgrade_focused",
        "dice": [1, 2, 3, 4, 6],
        "rolls_left": 1,
        "scorecard": [None] * 12,
        "mode": "focused",
        "expected": {
            "stage": "roll",
            "strategy_mode": "focused",
            "message": "[1, 2, 3, 4] Keep (Large Straight 업그레이드)",
            "summary": "집중 공략 추천: Large Straight 16.67%, 실패해도 Small Straight 유지",
            "keep_indices": [0, 1, 2, 3],
            "primary_target": "Large Straight",
            "expected_value": 21.11,
            "breakdown_names": ["Large Straight 업그레이드", "추천 근거", "4 of a Kind"],
        },
    },
    {
        "name": "full_house_focus",
        "dice": [6, 6, 5, 1, 5],
        "rolls_left": 2,
        "scorecard": [None] * 12,
        "mode": "focused",
        "expected": {
            "stage": "roll",
            "strategy_mode": "focused",
            "message": "[6, 6, 5, 5] Keep (Full House 노리기)",
            "summary": "집중 공략 추천: Full House 확률 55.56%",
            "keep_indices": [0, 1, 2, 4],
            "primary_target": "Full House",
            "expected_value": 34.37,
            "breakdown_names": ["Full House", "추천 근거", "4 of a Kind"],
        },
    },
    {
        "name": "full_house_cover",
        "dice": [6, 6, 5, 1, 5],
        "rolls_left": 2,
        "scorecard": [None] * 12,
        "mode": "cover",
        "expected": {
            "stage": "roll",
            "strategy_mode": "cover",
            "message": "[6, 6, 5, 5] Keep (커버 플레이)",
            "summary": "커버 플레이: 핸드 하나 이상 55.56%, 전부 실패 44.44%",
            "keep_indices": [0, 1, 2, 4],
            "primary_target": "핸드 하나 이상 성공",
            "expected_value": 33.04,
            "cover_success_prob": 0.555556,
            "cover_fail_prob": 0.444444,
            "breakdown_names": ["핸드 하나 이상 성공", "전부 실패", "Full House"],
        },
    },
    {
        "name": "yacht_bonus_focused",
        "dice": [6, 6, 6, 2, 1],
        "rolls_left": 2,
        "scorecard": [3, None, 9, None, None, 18, 22, None, None, None, None, 50],
        "mode": "focused",
        "expected": {
            "stage": "roll",
            "strategy_mode": "focused",
            "message": "[6, 6, 6] Keep (4 of a Kind 노리기)",
            "summary": "집중 공략 추천: 4 of a Kind 확률 51.77%",
            "keep_indices": [0, 1, 2],
            "primary_target": "4 of a Kind",
            "expected_value": 32.76,
            "breakdown_names": ["4 of a Kind", "추천 근거", "Full House"],
        },
    },
    {
        "name": "upper_bonus_finish_focused",
        "dice": [6, 6, 6, 1, 2],
        "rolls_left": 2,
        "scorecard": [3, 6, 9, 12, 15, None, None, None, None, None, None, None],
        "mode": "focused",
        "expected": {
            "stage": "roll",
            "strategy_mode": "focused",
            "message": "[6, 6, 6] Keep (Sixes 노리기)",
            "summary": "상단 보너스 추천: Sixes 평가 100.9, 이번 턴 보너스 마감권",
            "keep_indices": [0, 1, 2],
            "primary_target": "Sixes",
            "expected_value": 100.91,
            "breakdown_names": ["Sixes", "추천 근거", "4 of a Kind"],
        },
    },
    {
        "name": "score_stage_upper_finish",
        "dice": [6, 6, 6, 1, 2],
        "rolls_left": 0,
        "scorecard": [3, 6, 9, 12, 15, None, None, None, None, None, None, None],
        "mode": "focused",
        "expected": {
            "stage": "score",
            "strategy_mode": "focused",
            "message": "Sixes",
            "summary": "점수 기록 추천: Sixes 18점. 이번 기록으로 Upper Bonus +35를 바로 확보합니다",
            "keep_indices": [],
            "primary_target": "Sixes",
            "expected_value": 96.44,
            "breakdown_names": ["Sixes", "장기 가치", "Choice"],
        },
    },
    {
        "name": "score_stage_yacht_bonus",
        "dice": [4, 4, 4, 4, 4],
        "rolls_left": 0,
        "scorecard": [3, 6, 9, 12, 15, 18, 22, None, None, None, None, 50],
        "mode": "focused",
        "expected": {
            "stage": "score",
            "strategy_mode": "focused",
            "message": "4 of a Kind",
            "summary": "점수 기록 추천: 4 of a Kind 20점. Yacht Bonus +100과 함께 4 of a Kind 20점을 기록할 수 있습니다",
            "keep_indices": [],
            "primary_target": "4 of a Kind",
            "expected_value": 127.37,
            "breakdown_names": ["4 of a Kind", "장기 가치", "Full House"],
        },
    },
]


def approx_equal(actual: float, expected: float, tolerance: float = 0.02) -> bool:
    return math.isfinite(actual) and abs(actual - expected) <= tolerance


def validate_case(case: dict) -> list[str]:
    expected = case["expected"]
    open_categories = [idx for idx, value in enumerate(case["scorecard"]) if value is None]
    result = yacht_engine.solve_best_move(
        case["dice"],
        case["rolls_left"],
        open_categories,
        case["mode"],
        case["scorecard"],
    )

    errors: list[str] = []
    for field in ("stage", "strategy_mode", "message", "summary", "keep_indices", "primary_target"):
        if expected.get(field) != result.get(field):
            errors.append(f"{field}: expected {expected.get(field)!r}, got {result.get(field)!r}")

    expected_value = expected.get("expected_value")
    actual_value = result.get("expected_value")
    if expected_value is not None and not approx_equal(actual_value, expected_value):
        errors.append(f"expected_value: expected {expected_value!r}, got {actual_value!r}")

    for field in ("cover_success_prob", "cover_fail_prob"):
        if field not in expected:
            continue
        actual = result.get(field)
        target = expected[field]
        if not approx_equal(actual, target, tolerance=1e-6):
            errors.append(f"{field}: expected {target!r}, got {actual!r}")

    expected_breakdown_names = expected.get("breakdown_names", [])
    actual_breakdown_names = [row.get("name") for row in result.get("breakdown", [])[: len(expected_breakdown_names)]]
    if expected_breakdown_names != actual_breakdown_names:
        errors.append(
            f"breakdown_names: expected {expected_breakdown_names!r}, got {actual_breakdown_names!r}"
        )

    return errors


def main() -> None:
    failures: list[str] = []
    for case in GOLDEN_CASES:
        case_failures = validate_case(case)
        if case_failures:
            failures.append(f"[{case['name']}] " + " | ".join(case_failures))

    print(f"Golden cases checked: {len(GOLDEN_CASES)}")
    if failures:
        print(f"Failures: {len(failures)}")
        for failure in failures:
            print(f"  - {failure}")
        raise SystemExit(1)

    print("Failures: 0")


if __name__ == "__main__":
    main()
