# AI 추천 품질 지표 체계

추천 시스템이 "괜찮은지"를 감으로 판단하지 않기 위한 수치 지표 모음.
full-game exact value table(open12)이 있으므로, 모든 지표는 이론 최적 대비로 절대 평가할 수 있다.

## 지표 1 — Optimality Gap (게임 단위)

- 정의: `이론 최적 EV(198.358) - 정책의 평균 최종점수`
- 도구: `scripts/simulate_score_value_games.py` (+ `scripts/analyze_score_value_report.py`로 CI/p값)
- 해석: 정책이 최적 천장에서 얼마나 떨어져 있는지. 주사위 운이 섞이므로 표본이 커야 한다(±2점 판별에 2,000게임 이상).

## 지표 2 — Per-decision Regret (결정 단위, 핵심 지표)

- 정의: 매 결정(roll keep / score 기록)마다 `regret = Q*(최적 행동) - Q*(선택한 행동)`.
  Q*는 exact value table 기준이므로 **주사위 운과 무관하게** 정책 품질만 측정한다.
- 도구: `scripts/eval_decision_regret.py`

```bash
.venv/bin/python scripts/eval_decision_regret.py \
  --games 100 --policies focused,cover,optimal \
  --output artifacts/reports/decision-regret-100.json \
  --markdown-output docs/decision-regret-100.md
```

- 산출:
  - `avg_game_regret`: 게임당 평균 EV 손실(점) — 정책 품질의 대표 숫자
  - `roll/score match_rate`: 최적 행동과 일치한 결정 비율
  - `avg_mistake_size`: 틀렸을 때 평균 손실 크기
  - `regret_by_turn`: 몇 턴째 결정이 손실을 만드는지
  - `worst_decisions`: 재현 가능한 최악 사례 목록 (개선 대상 발굴용)
- 자체 검증: `optimal` 정책의 regret은 0이어야 한다 (평가기와 solver의 정합성 체크).
  게임 단위 지표와도 정합해야 한다: `avg_game_regret ≈ optimality gap` (performance difference).

## 지표 3 — A/B 유의성

- 정의: 정책 변경 전후 paired seed 비교의 95% CI / p값.
- 도구: `scripts/analyze_score_value_report.py`
- 규칙: CI가 0을 포함하면 채택/기각 판단 보류. 노이즈로 결론 내리지 않는다.

## 지표 4 — 응답 시간

- 도구: `scripts/benchmark_ai.py`
- 기준선(2026-07-08): heuristic cold 37.8~193.6ms, value-optimal cold 58.5~140.3ms, warm 0.04~0.05ms.

## 지표 5 — 멀티플레이어 승률 전망

- 정의: 상대(EV-optimal 봇) 대비 승률. EV 최대화와 승률 최대화는 다르다 —
  지고 있으면 고분산, 이기고 있으면 저분산이 옳다.
- 현재 구현: 양쪽이 `value_optimal`로 남은 게임을 진행하는 Monte Carlo 전망. UI는 기본 30샘플과 95% 표본 오차를 함께 표시한다.
- 미구현: 실제 점수차에 따라 고분산/저분산 선택을 바꾸는 distribution-aware 승률 최대화 정책.

## 현재 스코어보드 (2026-07-09)

| 지표 | focused | cover | optimal | 근거 |
|---|---|---|---|---|
| Regret/게임 (100게임) | **10.39점** | 37.92점 | **0.00점** | decision-regret-100-value-score-only / decision-regret-100 |
| Roll 결정 최적 일치율 | 70.11% | 60.0% | 100% | 상동 |
| Score 결정 최적 일치율 | **100%** | 71.0% | 100% | 상동 |
| Score 실수 시 평균 손실 | **0.00점** | 5.23점 | - | 상동 |
| 평균 점수 (200게임, indexed) | **184.56** | - | 198.6 | score-value-score-only-open12 / full-table-optimal |
| 응답(cold) | 38~194ms | - | 59~140ms | ai-runtime-* artifacts |

읽는 법: 현재 focused는 score 단계가 exact value라 기록 실수가 0이고, 남은 regret은 설명 가능한 목표 지향 roll 정책에서 발생한다.

focused/cover는 "설명 가능한 목표 지향 플레이"가 목적이므로 regret 0이 목표가 아니다.
다만 regret이 **어디서** 새는지(turn/stage별)를 보고, 설명력을 해치지 않는 선에서 줄이는 것이 개선 방향이다.

## Focused Score-Stage Guard v2

`docs/decision-regret-100-focused-v2.md`는 score 단계 obvious-mistake guard 적용 후의 focused 재측정이다.

- Regret/게임: 22.41점 -> 20.89점
- Score 결정 최적 일치율: 79.0% -> 79.75%
- Score avg regret: 1.049 -> 0.9234
- 평균 점수: 175.12 -> 176.01

Yacht 50 / Large Straight 30 같은 확정 고득점 족보가 상단 보너스 push에 밀리지 않도록 막고, 아주 낮은 양수 점수보다 0점 희생이 명백히 나은 경우를 허용했다. 4 of a Kind / Full House까지 강하게 보호하면 반대로 상단 선택을 막는 오판이 생겨 제외했다.

## Focused Sacrifice Upper-Bonus Guard v3

`docs/decision-regret-100-focused-v3.md`는 0점 희생 후보 정렬에서 Upper Bonus 생존성을 반영한 focused 재측정이다.

- Regret/게임: 20.89점 -> 20.56점
- Score 결정 최적 일치율: 79.75% -> 79.83%
- Score avg regret: 0.9234 -> 0.8986
- 평균 점수: 176.01 -> 176.38

희생 후보 정렬을 `future_pressure + 35 * bonus_prob_drop` 기준으로 바꿔, 상단 보너스가 아직 살아 있는 칸을 0점으로 닫는 선택에 비용을 부여했다. 남은 worst 사례는 낮은 점수를 Sixes에 쓰는 패턴이라 별도 작업으로 분리한다.

## Focused Low Upper Score Guard v4

`docs/decision-regret-100-focused-v4.md`는 고가치 상단 칸(Fives/Sixes)에 낮은 점수를 낭비하는 패턴을 완화한 재측정이다.

- Regret/게임: 20.56점 -> 19.49점
- Score 결정 최적 일치율: 79.83% -> 81.00%
- Score avg regret: 0.8986 -> 0.7554
- Roll 결정 최적 일치율: 70.58% -> 70.09%
- 평균 점수: 176.38 -> 177.77

상수안 단독은 regret/game 20.02까지 내려갔지만 지목한 Sixes/Fives 낭비 재현 케이스를 직접 고치지 못했다. 가드 단독은 재현 케이스는 고쳤으나 regret/game 21.02로 악화됐다. 최종 v4는 품질 페널티를 강화하고, Upper Bonus 확률을 의미 있게 깎는 Fives/Sixes 저점 기록에서만 싼 dump 후보(Ones/Twos/Threes 또는 0점 희생)를 선택하도록 좁힌 조합이다. roll match는 소폭 낮아졌으므로 다음 개선은 Full House/4 of a Kind 고정 고득점 보호 쪽으로 분리한다.

## Score-only Exact Value 재검증 (open12)

`docs/decision-regret-100-value-score-only.md`와 `docs/score-value-score-only-open12-focused-200-analysis.md`는 full-game open12 value table 기준으로 `value_score_only`를 다시 측정한 결과다.

- Decision regret: focused 19.49점/게임 -> value_score_only 10.39점/게임
- Score 단계 regret: 0.7554 -> 0.0000, score match 81.0% -> 100.0%
- Roll 단계는 focused와 거의 동일: roll match 70.09% -> 70.11%
- 200게임 paired A/B: heuristic 175.52점 vs value_score_only 184.56점, 평균 delta +9.04점
- 95% CI: +3.43 ~ +14.65점, two-sided normal p=0.001587
- Score-stage exact table hit: 12.0턴/게임, fallback 0.0턴/게임

해석: open4 시절의 `value_score_only` 결과는 exact hit가 부족해 결론을 내리기 어려웠지만, open12 테이블에서는 점수 기록 순간의 손실이 완전히 사라진다.

## Focused 기본값 승격 (2026-07-09)

`routes/ai.py`의 `_solver_options_for_strategy`가 `strategy_mode == "focused"`일 때 `score_value_mode="value_score_only"`를 기본으로 넘기도록 바뀌었다. roll 단계는 여전히 focused 휴리스틱(`terminal_score_value_mode="heuristic"`)이라 "집중 공략" 설명력은 유지되고, score 단계만 exact V(next_state) 조회로 대체된다.

- 사용자에게 노출되는 `focused` 추천의 score-stage regret이 이제 이론상 항상 0이다 (환경변수 설정 없이도 적용).
- `policy_source`/`decision_report.method.source`는 여전히 `"exact"`로 표시된다(새 값 강제 없음) — `report.py`의 `_source_label`/`_learning_note`가 미인식 소스에 안전한 기본 문구를 반환하는 걸 확인했다.
- `scripts/check_ai_golden.py`는 `yacht_engine.solve_best_move`를 `score_value_mode` 없이 직접 호출하므로 이 변경의 영향을 받지 않는다(환경변수 `YACHT_SCORE_STAGE_MODE` 기본값은 그대로 `heuristic`).
- roll-stage `keep_indices`는 값 변화 없음을 회귀 테스트로 확인(`tests/test_routes.py`의 `[0, 1, 2, 3]` 기대값 유지).

프론트의 AI 모드 설명 카드에 노출하는 평균 점수/최적 대비 손실 수치는 이 문서와 regret 리포트를 기준으로 하며, 새 regret 리포트를 채택할 때 함께 갱신한다.
