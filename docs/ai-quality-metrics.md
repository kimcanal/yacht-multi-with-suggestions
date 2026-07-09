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

## 지표 5 — (예정) 멀티플레이어 승률

- 정의: 상대(EV-optimal 봇) 대비 승률. EV 최대화와 승률 최대화는 다르다 —
  지고 있으면 고분산, 이기고 있으면 저분산이 옳다.
- 필요물: 점수차·남은 턴 조건부 정책(distribution-aware). 아직 미구현.

## 현재 스코어보드 (2026-07-09)

| 지표 | focused | cover | optimal | 근거 |
|---|---|---|---|---|
| Regret/게임 (100게임) | 22.41점 | 37.92점 | **0.00점** | decision-regret-100 |
| Roll 결정 최적 일치율 | 70.7% | 60.0% | 100% | 상동 |
| Score 결정 최적 일치율 | 79.0% | 71.0% | 100% | 상동 |
| Score 실수 시 평균 손실 | 5.00점 | 5.23점 | - | 상동 |
| 평균 점수 (200게임, indexed) | 168.2 | - | 198.6 | score-value-full-table-optimal-focused-200-indexed |
| 응답(cold) | 38~194ms | - | 59~140ms | ai-runtime-* artifacts |

읽는 법: focused의 regret 22.4점 중 roll 단계가 게임당 약 9.8점(0.41×~24회), score 단계가 약 12.6점(1.05×12회).
즉 **점수 기록 순간의 실수가 더 크다** — 틀릴 확률은 21%뿐이지만 한 번 틀리면 평균 5점을 잃는다.

focused/cover는 "설명 가능한 목표 지향 플레이"가 목적이므로 regret 0이 목표가 아니다.
다만 regret이 **어디서** 새는지(turn/stage별)를 보고, 설명력을 해치지 않는 선에서 줄이는 것이 개선 방향이다.
