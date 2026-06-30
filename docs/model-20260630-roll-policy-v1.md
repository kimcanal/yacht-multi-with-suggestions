# model-20260630-roll-policy-v1

`model-20260630-roll-policy-v1`은 roll stage에서 exact solver의 keep 선택을 빠르게 근사하는 distillation 모델이다. 점수 기록(score stage)은 여전히 exact/heuristic 추천 로직이 담당하고, 이 모델은 "남은 reroll에서 어떤 주사위를 keep할지"만 예측한다.

## 산출물

- Model: `artifacts/models/model-20260630-roll-policy-v1.json`
- Eval report: `artifacts/reports/model-20260630-roll-policy-v1.eval.json`
- Teacher data: `artifacts/teacher_roll_32768.jsonl`
- Smoke teacher data: `artifacts/teacher_roll_20260630_1008_exact_teacher.jsonl`

## 학습 설정

- Model type: `roll_mlp_v1`
- Input features: 41
- Hidden dim: 96
- Keep classes: 462
- Epochs: 120
- Seed: `20260630`
- Best epoch: 118
- Train examples: 26,214
- Validation examples: 6,554

## 평가 결과

Held-out split 기준:

- Top-1 accuracy: 98.5505%
- Top-3 accuracy: 99.7864%
- Validation accuracy recorded by trainer: 98.2148%

Confidence threshold별 운영 후보:

| Threshold | Coverage | Accuracy on covered examples |
| --- | ---: | ---: |
| 0.80 | 98.7489% | 99.0111% |
| 0.90 | 97.8334% | 99.2358% |
| 0.95 | 97.0095% | 99.3080% |
| 0.98 | 94.7818% | 99.4205% |
| 0.99 | 92.6152% | 99.4234% |

현재 서버 기본 실험값으로는 `YACHT_AI_POLICY_MIN_CONFIDENCE=0.95`가 적당하다. 이 값이면 대부분의 roll-stage 요청에서 모델을 쓸 수 있고, covered 구간에서는 teacher 선택과 거의 일치한다. confidence가 낮거나 exact solver와 의미 있게 갈라지면 fallback하도록 둔다.

추가 EV/runtime 검증 기준:

- Raw mean excess EV gap: 0.036379
- Raw mismatch count: 95 / 6,554
- Runtime acceptance at confidence 0.95 + gap guard 0.25: 48.9930%
- Runtime accepted accuracy: 99.5017%
- Effective excess EV gap with fallback: mean 0, max 0

이 수치는 teacher 일치율과 실전 안전성이 서로 다른 문제라는 점을 보여준다. 모델 단독으로는 rare worst-case가 있지만, runtime fallback을 적용하면 검증 split에서는 추가 EV 손실이 0으로 막혔다.

## 재현 명령

```bash
python3 scripts/generate_teacher_data.py \
  --all-dice \
  --contexts-per-dice 4 \
  --stage roll \
  --mode both \
  --output artifacts/teacher_roll_20260630_1008_exact_teacher.jsonl \
  --overwrite

python3 scripts/train_roll_policy.py \
  --data artifacts/teacher_roll_32768.jsonl \
  --output artifacts/models/model-20260630-roll-policy-v1.json \
  --epochs 120 \
  --hidden-dim 96 \
  --batch-size 256 \
  --learning-rate 0.003 \
  --seed 20260630 \
  --model-id model-20260630-roll-policy-v1 \
  --created-date 2026-06-30

python3 scripts/eval_roll_policy.py \
  --data artifacts/teacher_roll_32768.jsonl \
  --model artifacts/models/model-20260630-roll-policy-v1.json \
  --seed 20260630 \
  --output artifacts/reports/model-20260630-roll-policy-v1.eval.json
```

## 해석

이 모델은 Yacht 자체를 "새로 발견"한 모델이라기보다는, exact solver가 이미 계산한 선택을 빠르게 따라 하는 학생 모델이다. 얻은 것은 크게 세 가지다.

1. exact solver 선택을 32k teacher 기준으로 안정적으로 압축할 수 있다는 근거
2. confidence threshold를 걸면 모델 사용 구간과 exact fallback 구간을 나눌 수 있다는 운영 기준
3. 향후 full-game value model이나 상대 모델링을 붙일 때 쓸 학습 파이프라인의 기준선

## 한계와 다음 단계

- 전체 12턴 승률을 직접 예측하는 모델은 아니다.
- score stage의 장기 가치 판단은 아직 full-game DP/value table로 완전히 대체하지 않았다.
- teacher data가 exact solver의 편향을 그대로 배운다.
- 후속 모델인 [model-20260630-roll-policy-v2.md](./model-20260630-roll-policy-v2.md)는 같은 구조에서 seed를 바꿔 top-1 정확도를 소폭 개선했다.
- 다음 큰 개선은 value table `V(mask, upper_total, yacht_bonus)`를 score-stage feature로 연결하거나, self-play 결과를 value target으로 추가하는 방향이 좋다.
