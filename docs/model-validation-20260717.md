# Roll policy v2 독립 검증 (2026-07-17)

## 결론

`model-20260630-roll-policy-v2`는 기존 teacher split에서는 높은 정확도를 보였지만, 현재 solver로 새로 만든 독립 표본에서는 같은 성능이 재현되지 않았다. 따라서 이 모델은 **단독 추천기로 배포하면 안 된다**.

- 현재 운영처럼 learned model을 비활성화하고 exact solver를 사용하는 상태는 안전하다.
- 모델을 사용하려면 confidence `0.95`와 exact objective-gap `0.25` guard를 모두 유지해야 한다.
- 다음 모델은 현재 solver가 생성한 새 데이터로 재학습한 뒤, 이 문서와 같은 독립 검증을 다시 통과해야 한다.

## 왜 다시 검증했나

기존 평가는 학습에 사용한 `teacher_roll_32768.jsonl`의 held-out split이었다. 이 파일은 현재 저장소에 없고 정확한 생성 명령도 커밋 이력에 남아 있지 않으므로, 기존 수치를 완전히 재현할 수 없다. 또한 모델 학습 뒤 focused 전략과 보너스 보호 로직이 바뀌어 현재 solver가 만드는 label과 학습 당시 label 사이에 drift가 생길 수 있다.

이번 검증은 기존 split을 재사용하지 않고 현재 solver에서 새 표본을 생성했다. 실제 주사위 출현 확률을 반영하기 위해 `dice-source=weighted`를 사용했다.

## 검증 데이터

| 항목 | 값 |
| --- | --- |
| 생성 표본 | 4,096 roll-stage states |
| 평가 표본 | 4,095 states (`val-ratio=1.0`에서 split helper가 1개를 제외) |
| 생성 seed | `20260717` |
| 전략 분포 | focused 2,003 / cover 2,093 |
| 진행도 | 0~11 completed turns |
| 주사위 분포 | five-dice weighted random rolls |
| 데이터 SHA-256 | `7c75d4a09ca468fd63536f5156df302731add85dcf8368ffbf094238e65dce6a` |
| 모델 SHA-256 | `e047b0d1ed2ce351b8d84e6aa4b8b495300074c48b93cf771a730a2bdef8b58a` |

## 결과 1: teacher imitation

| 지표 | 기존 held-out split | 새 독립 표본 |
| --- | ---: | ---: |
| Top-1 accuracy | 98.5200% | **81.5873%** |
| Top-3 accuracy | 99.7559% | **89.0842%** |
| Top-1 95% Wilson CI | - | 80.37%~82.74% |

독립 표본의 전략별 Top-1은 cover 95.41%, focused 67.15%였다. 특히 게임 초반 focused 상태는 50.16%였는데 평균 confidence는 99.73%였다. confidence `0.95` 이상 표본도 정확도가 83.68%에 그쳤다. 즉 confidence만으로는 현재의 distribution/label drift를 탐지할 수 없다.

## 결과 2: EV gap

`excess EV gap`은 모델 keep의 pure-objective gap에서 teacher keep의 gap을 뺀 값이다. focused/cover teacher가 순수 점수 EV만 최적화하지 않는 경우가 있으므로 teacher 대비 추가 손실로 해석한다.

| Raw model-only | 결과 |
| --- | ---: |
| 불일치 | 754 / 4,095 |
| 전체 평균 추가 EV 손실 | **1.2111점** |
| p95 / p99 | 8.2435 / 14.1026점 |
| 최대 | **27.7715점** |
| 0.25점 초과 | 710건 |
| 1점 초과 | 690건 |
| 2점 초과 | 667건 |

오답 754건만 보면 평균 추가 손실은 6.5777점이었다. 대표 실패는 높은 눈의 pair/triple보다 straight 조각을 과도하게 선택하는 경우였다. 높은 confidence의 큰 손실도 있어 confidence threshold만 높이는 방식은 충분하지 않다.

## 결과 3: runtime guard

| Confidence 0.95 + gap 0.25 guard | 결과 |
| --- | ---: |
| 모델 채택 | 1,618 / 4,095 (39.51%) |
| 채택 구간 Top-1 | 99.0729% |
| 채택 구간 Top-1 95% Wilson CI | 98.48%~99.44% |
| confidence reject | 283 |
| gap-guard reject | 2,194 |
| fallback 포함 평균 추가 EV 손실 | 0.000031점 |
| fallback 포함 최대 추가 EV 손실 | 0.125091점 |
| 0.25점 초과 | 0건 |

guard는 큰 손실을 차단했지만 모델 채택률은 39.51%로 낮아졌다. 또한 gap guard 자체가 exact 계산을 수행하므로, 모델을 쓰는 목적이 latency 감소라면 별도의 성능 검증이 필요하다.

## 결과 4: complete-game paired simulation

Focused mode, 100 games, seed `20260717`에서 score stage는 동일한 exact 추천을 사용하고 roll policy만 비교했다.

| Policy | 평균 총점 | exact 대비 평균 | paired 95% CI | 승/동/패 |
| --- | ---: | ---: | ---: | ---: |
| exact | 175.70 | 기준 | - | - |
| v2 runtime guard | 176.33 | +0.63 | **-0.57~+1.83** | 10/87/3 |
| v2 model-only | 149.00 | **-26.70** | **-34.74~-18.66** | 25/1/74 |

runtime guard와 exact의 차이는 이 표본에서 통계적으로 유의하지 않다. 반면 model-only의 성능 저하는 명확하다. 이 simulation의 `exact`는 한 턴 roll/score 결정을 exact하게 푸는 기준선이며, 12턴 전체 게임에 대한 전역 최적 정책이라는 뜻은 아니다.

## 제품 및 연구 판단

| 질문 | 판단 |
| --- | --- |
| 지금 모델을 단독 활성화해도 되는가? | 아니오 |
| guard와 함께 활성화해도 되는가? | 품질상 큰 손실은 막지만, latency 이득 검증 전에는 보류 |
| 현재 사이트가 안전한가? | 2026-07-17 확인 기준 learned model이 비활성이고 exact fallback을 사용함 |
| 모델 구조를 바로 키워야 하는가? | 아니오. 먼저 최신 teacher data와 focused label drift를 해결해야 함 |
| 발표에서 98.52%를 대표 성능으로 말해도 되는가? | 학습 당시 held-out 수치라고 한정해야 하며, 최신 독립 성능 81.59%를 함께 제시해야 함 |

## 재현 명령

생성 파일과 상세 report는 용량 때문에 `artifacts/generated/`에 두며 Git에는 포함하지 않는다. 아래 명령과 hash로 다시 만들 수 있다.

```bash
.venv/bin/python scripts/generate_teacher_data.py \
  --samples 4096 \
  --stage roll \
  --mode both \
  --dice-source weighted \
  --min-completed-turns 0 \
  --max-completed-turns 11 \
  --seed 20260717 \
  --clear-cache-every 500 \
  --output artifacts/generated/model-validation-20260717/teacher-independent-4096.jsonl \
  --overwrite

.venv/bin/python scripts/eval_roll_policy.py \
  --data artifacts/generated/model-validation-20260717/teacher-independent-4096.jsonl \
  --model artifacts/runtime/models/model-20260630-roll-policy-v2.json \
  --val-ratio 1.0 \
  --seed 20260717 \
  --output artifacts/generated/model-validation-20260717/model-v2.independent.eval.json

.venv/bin/python scripts/eval_roll_policy_ev_gap.py \
  --data artifacts/generated/model-validation-20260717/teacher-independent-4096.jsonl \
  --model artifacts/runtime/models/model-20260630-roll-policy-v2.json \
  --val-ratio 1.0 \
  --seed 20260717 \
  --output artifacts/generated/model-validation-20260717/model-v2.independent.ev-gap.json

.venv/bin/python scripts/eval_roll_policy_runtime.py \
  --data artifacts/generated/model-validation-20260717/teacher-independent-4096.jsonl \
  --model artifacts/runtime/models/model-20260630-roll-policy-v2.json \
  --val-ratio 1.0 \
  --seed 20260717 \
  --min-confidence 0.95 \
  --guard-gap 0.25 \
  --output artifacts/generated/model-validation-20260717/model-v2.independent.runtime.json

.venv/bin/python scripts/simulate_roll_policy_games.py \
  --games 100 \
  --seed 20260717 \
  --mode focused \
  --min-confidence 0.95 \
  --output artifacts/generated/model-validation-20260717/full-game-focused-100.json
```

## 회귀 검증

- Python `unittest`: 74/74 통과
- AI golden cases: 7/7 통과
- warm soak: 250 cases, failure 0
- cold soak: 80 cases, failure 0
- cold-cache representative benchmark: 평균 약 43~154 ms/scenario

테스트 통과는 구현 회귀가 없다는 근거이며, 모델의 일반화 성능을 보증하지는 않는다. 모델 배포 판단은 위 독립 정확도, EV gap, runtime guard, full-game 결과를 함께 사용한다.

## 후속 결과: v3 재학습

v2의 drift를 확인한 뒤, 현재 solver로 weighted teacher state 32,768개를 새로 생성해 v3를 재학습했다. 첫 독립 seed에서 v3는 Top-1 94.04%, raw 평균 추가 EV 손실 0.1747점, guarded runtime 채택률 52.60%를 기록했고, 두 번째 독립 seed에서도 Top-1 94.14%, 평균 손실 0.1755점, guarded runtime 최대 손실 0점을 재현했다. 하지만 model-only complete-game 평균은 exact보다 12.18점 낮았으므로, v3도 단독 배포는 금지한다. 상세 결과와 staging 기준은 [v3 검증 보고서](./model-20260717-roll-policy-v3.md)를 참고한다.
