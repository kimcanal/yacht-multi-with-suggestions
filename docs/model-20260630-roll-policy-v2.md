# model-20260630-roll-policy-v2

`model-20260630-roll-policy-v2`는 v1과 같은 roll-stage distillation 모델이다. 구조는 그대로 두고 seed를 바꿔 재학습했다. 목표는 네트워크를 키우는 것이 아니라, 같은 teacher data에서 더 좋은 수렴점을 찾는 것이었다.

## 산출물

- Model: `artifacts/models/model-20260630-roll-policy-v2.json`
- Eval report: `artifacts/reports/model-20260630-roll-policy-v2.eval.json`
- Teacher data: `artifacts/teacher_roll_32768.jsonl`
- Baseline: `artifacts/models/model-20260630-roll-policy-v1.json`

## 학습 설정

- Model type: `roll_mlp_v1`
- Input features: 41
- Hidden dim: 96
- Keep classes: 462
- Epochs: 120
- Seed: `20260701`
- Best epoch: 107
- Train examples: 26,214
- Validation examples: 6,554

## 평가 결과

Held-out split 기준:

- Top-1 accuracy: 98.5200%
- Top-3 accuracy: 99.7559%
- Validation accuracy recorded by trainer: 98.2301%

Confidence threshold별 운영 후보:

| Threshold | Coverage | Accuracy on covered examples |
| --- | ---: | ---: |
| 0.80 | 98.6421% | 98.9791% |
| 0.90 | 97.4672% | 99.1860% |
| 0.95 | 96.4297% | 99.2880% |
| 0.98 | 94.2325% | 99.3847% |
| 0.99 | 92.0812% | 99.4200% |

## v1 비교

| Model | Top-1 | Top-3 | Raw mean excess EV gap | Runtime acceptance | Runtime accepted accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| v1 | 98.5505% | 99.7864% | 0.036379 | 48.9930% | 99.5017% |
| v2 | 98.5200% | 99.7559% | 0.023701 | 46.9637% | 99.3827% |

made-hand safety override 이후에는 v1이 top-1 정확도와 confidence coverage에서 아주 근소하게 앞선다. v2는 teacher 대비 raw 평균 추가 EV 손실이 더 낮고, full-game runtime 평균도 더 높다. 그래서 `coverage/top-1 baseline`은 v1, `mean-EV/runtime candidate`는 v2로 보는 것이 정확하다.

운영에서 둘 중 하나만 고르면 v2를 기본값으로 둔다. 이유는 fallback이 있기 때문에 low-confidence/high-gap 구간의 위험을 exact solver가 흡수하고, 전체 roll-stage 일치율과 평균 추가 EV 손실은 v2가 더 좋기 때문이다. 다만 confidence threshold 기반 A/B 테스트를 한다면 v1과 v2를 함께 비교하는 편이 좋다.

## EV gap 검증

단순 accuracy는 "teacher와 같은 keep을 골랐나"만 본다. 그래서 별도 EV gap 검증에서는 모델이 teacher와 다른 keep을 골랐을 때 exact turn-DP 기준으로 추가 손실을 다시 계산했다. 여기서의 `excess EV gap`은 `model objective gap - teacher objective gap`이다. focused/cover 전략 자체가 순수 점수 EV만 최대화하지 않는 경우가 있으므로, 순수 objective gap이 아니라 teacher 대비 추가 손실을 따로 본다.

Raw model-only 기준:

- Evaluated examples: 6,554
- Top-1 accuracy: 98.5200%
- Mismatches: 97
- Mean excess EV gap: 0.023701
- p95 excess EV gap: 0
- p99 excess EV gap: 0
- Max excess EV gap: 10.145227
- Gap > 0.25: 51 cases
- Gap > 1: 43 cases
- Gap > 2: 29 cases

made-hand safety override 이후에도 모델 단독 사용은 exact보다 낮지만, rare worst-case 규모는 크게 줄었다. 대부분은 teacher와 같거나 사실상 손실이 없고, 남은 hard case는 exact guard가 걸러야 한다.

## Runtime guard 검증

서버 운영 방식은 모델을 무조건 쓰지 않는다. `YACHT_AI_POLICY_MIN_CONFIDENCE=0.95`를 넘고, 모델 keep의 pure objective gap이 `0.25` 이하일 때만 learned policy를 채택한다. 아니면 exact solver로 fallback한다.

Runtime policy 기준:

- Evaluated examples: 6,554
- Accepted examples: 3,078
- Acceptance rate: 46.9637%
- Rejected by confidence: 234
- Rejected by gap guard: 3,242
- Accepted top-1 accuracy: 99.3827%
- Effective excess EV gap with fallback: mean 0, max 0

즉, v2를 모델 단독으로 쓰면 worst-case가 있지만, 현재 runtime guard를 적용하면 검증 split에서는 추가 EV 손실이 발생하지 않았다. 대신 모델 채택률이 절반 이하로 떨어진다. 이 trade-off는 의도된 설계다.

## Hard cases

Raw model-only worst case는 [model-20260630-roll-policy-v2-hard-cases.md](./model-20260630-roll-policy-v2-hard-cases.md)에 따로 정리했다. safety override 전에는 이미 완성된 4/5개짜리 강한 패를 모델이 일부만 keep하는 문제가 가장 컸다. override 이후 그 계열은 대부분 막혔고, 남은 hard case는 upper/four-kind/straight 사이의 미묘한 trade-off다.

이 hard-case 리포트의 의미는 모델을 폐기해야 한다는 뜻이 아니라, 모델 단독 사용이 위험하다는 근거다. runtime guard가 필요한 이유가 여기서 드러난다.

## Full-game simulation

teacher 일치율이나 single-turn EV gap만으로는 실제 게임 점수 영향을 충분히 설명하지 못한다. 그래서 같은 seed 묶음으로 complete game simulation을 돌렸다. score stage는 동일한 exact 추천을 쓰고, roll stage 정책만 바꿔 비교했다.

Focused mode, 100 games, seed `20260630` 기준:

| Policy | Avg total | Delta vs exact | Upper bonus rate | Avg zero categories |
| --- | ---: | ---: | ---: | ---: |
| exact | 152.21 | +0.00 | 12.00% | 1.34 |
| v1 runtime | 154.19 | +1.98 | 12.00% | 1.38 |
| v2 runtime | 155.70 | +3.49 | 13.00% | 1.36 |
| v1 model-only | 151.63 | -0.58 | 6.00% | 1.54 |
| v2 model-only | 148.88 | -3.33 | 5.00% | 1.69 |

이 결과는 앞의 EV gap 결론과 같은 방향이다. runtime fallback을 넣은 v1/v2는 exact와 같은 점수대를 유지하고, 이 seed 묶음에서는 평균이 조금 높게 나왔다. 반대로 model-only는 safety override 이후에도 평균 점수와 upper bonus rate가 떨어진다. 따라서 learned roll policy는 "exact solver 대체재"가 아니라 "guard가 붙은 빠른 후보 생성기"로 보는 것이 맞다.

## 재현 명령

```bash
python3 scripts/train_roll_policy.py \
  --data artifacts/teacher_roll_32768.jsonl \
  --output artifacts/models/model-20260630-roll-policy-v2.json \
  --epochs 120 \
  --hidden-dim 96 \
  --batch-size 256 \
  --learning-rate 0.003 \
  --seed 20260701 \
  --model-id model-20260630-roll-policy-v2 \
  --created-date 2026-06-30

python3 scripts/eval_roll_policy.py \
  --data artifacts/teacher_roll_32768.jsonl \
  --model artifacts/models/model-20260630-roll-policy-v2.json \
  --seed 20260701 \
  --output artifacts/reports/model-20260630-roll-policy-v2.eval.json

python3 scripts/eval_roll_policy_ev_gap.py \
  --data artifacts/teacher_roll_32768.jsonl \
  --model artifacts/models/model-20260630-roll-policy-v2.json \
  --seed 20260701 \
  --output artifacts/reports/model-20260630-roll-policy-v2.ev-gap.json

python3 scripts/eval_roll_policy_runtime.py \
  --data artifacts/teacher_roll_32768.jsonl \
  --model artifacts/models/model-20260630-roll-policy-v2.json \
  --seed 20260701 \
  --min-confidence 0.95 \
  --guard-gap 0.25 \
  --output artifacts/reports/model-20260630-roll-policy-v2.runtime.json

python3 scripts/report_roll_policy_hard_cases.py \
  --input artifacts/reports/model-20260630-roll-policy-v2.ev-gap.json \
  --output docs/model-20260630-roll-policy-v2-hard-cases.md \
  --limit 10

python3 scripts/simulate_roll_policy_games.py \
  --games 100 \
  --seed 20260630 \
  --mode focused \
  --output artifacts/reports/roll-policy-full-game-focused-100.json
```

## 해석

v2에서 확인한 점은 "더 큰 모델이 항상 좋은 것은 아니다"이다. hidden dim 160 후보도 학습했지만, 최종 top-1은 98.3064%로 v1/v2보다 낮았다. 현재 teacher data 규모에서는 모델 용량을 키우기보다 안정적인 구조와 seed/hyperparameter 선택이 더 중요하게 보인다.

다음 의미 있는 v3는 roll-policy 구조 변경보다 teacher data 확장, score-stage value table 연결, self-play value target 추가 쪽이 낫다. 이 기반 작업으로 `generate_value_data.py`와 `train_value_baseline.py`를 추가해 scorecard state -> remaining score baseline을 재현 가능하게 만들었다.
