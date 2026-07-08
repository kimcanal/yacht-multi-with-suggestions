# AI Learning Roadmap

이 프로젝트의 의사결정 코어는 "모델이 먼저"가 아니라 "정확 계산을 teacher로 삼고, 필요할 때 모델을 붙이는" 구조가 가장 잘 맞는다.

## 모델이 꼭 필요한가

현재 Yacht 한 턴의 keep/reroll 의사결정은 상태공간이 작아서 exact DP로 직접 비교할 수 있다. 그래서 최선의 행동을 찾는 것만 놓고 보면 ML/DL 모델은 필수 요소가 아니다.

대신 모델이 유용해지는 지점은 다음이다.

- exact solver 결정을 더 빠르게 근사하는 roll policy distillation
- self-play 결과를 누적해 전체 게임 승률을 예측하는 value model
- 상대의 위험 선호, 점수판 흐름, 후반 압박 같은 더 큰 문맥 학습
- UI에서 "이 선택이 왜 좋은지"를 자연어/시각 자료로 요약하는 설명 계층

## 현재 구조

1. Exact solver
   - 한 턴의 keep 후보를 DP로 비교한다.
   - score stage는 즉시 점수, upper bonus 압박, 장기 칸 가치, Yacht bonus를 같이 본다.

2. Learned roll policy
   - exact solver가 만든 teacher data를 학습한 경량 MLP다.
   - confidence가 낮거나 위험한 상태에서는 exact solver fallback을 사용한다.

3. Decision report
   - `/api/recommend` 응답의 `decision_report`가 사람이 읽을 수 있는 결론을 제공한다.
   - 포함 내용: 결론, decision stage/mode/target, method, confidence, 핵심 근거, 비교 포인트, ML/DL 역할 설명.

## 다음 학습 단계

1. Teacher data 확장
   - 다양한 scorecard 맥락과 roll state를 더 많이 생성한다.
   - exact 결과, 차선책 gap, stop-now 비교를 함께 저장한다.

2. Policy distillation 강화
   - roll stage keep policy를 더 안정적으로 학습한다.
   - exact와 action mismatch, EV gap, confidence calibration을 같이 본다.

3. Value model 추가
   - 한 턴 최선이 아니라 게임 전체 기대 점수/승률을 예측한다.
   - self-play 결과를 모아 scorecard state의 장기 가치를 학습한다.
   - `scripts/generate_value_data.py`로 exact self-play value target을 만들고,
     `scripts/train_value_baseline.py`로 선형 baseline을 먼저 검증한다.

4. 리포트 고도화
   - `decision_report`를 기반으로 EV 변화, 성공 확률, 차선책 gap을 그래프화한다.
   - "모델 판단"과 "exact fallback 판단"의 차이를 UI에서 구분해 보여준다.

## 판단 기준

작게 정확히 풀 수 있는 문제는 exact solver가 기준선이다. ML/DL은 그 기준선을 대체하기보다, 더 넓은 문맥을 배우거나 빠르게 근사하거나 사용자에게 설명 가능한 형태로 바꾸는 보조 엔진으로 두는 편이 안전하다.

## Self-play Value Baseline

게임 전체 장기 가치를 학습하기 위한 첫 단계로 scorecard state value 데이터 파이프라인을 추가했다.

```bash
python3 scripts/generate_value_data.py \
  --games 256 \
  --seed 20260708 \
  --mode focused \
  --output artifacts/value/self-play-value-focused-256.jsonl \
  --summary-output artifacts/reports/self-play-value-focused-256.summary.json \
  --overwrite

python3 scripts/train_value_baseline.py \
  --data artifacts/value/self-play-value-focused-256.jsonl \
  --output artifacts/models/scorecard-value-linear-v1.json \
  --seed 20260708 \
  --ridge 1.0

python3 scripts/eval_value_baseline.py \
  --data artifacts/value/self-play-value-focused-256.jsonl \
  --model artifacts/models/scorecard-value-linear-v1.json \
  --output artifacts/reports/scorecard-value-linear-v1.eval.json \
  --markdown-output docs/scorecard-value-linear-v1-hard-cases.md \
  --limit 10

python3 scripts/simulate_value_state_distribution.py \
  --scorecard yacht_bonus_active \
  --trials 128 \
  --seed 20260708 \
  --markdown-output docs/yacht-bonus-value-distribution.md

python3 scripts/generate_value_distribution_data.py \
  --source-jsonl artifacts/value/self-play-value-focused-256.jsonl \
  --max-states 64 \
  --trials-per-state 64 \
  --output artifacts/value/self-play-value-distribution-focused-64x64.jsonl \
  --summary-output artifacts/reports/self-play-value-distribution-focused-64x64.summary.json \
  --overwrite

python3 scripts/train_value_distribution_baselines.py \
  --data artifacts/value/self-play-value-distribution-focused-64x64.jsonl \
  --output artifacts/models/scorecard-value-distribution-linear-v1.json \
  --seed 20260708

python3 scripts/eval_value_distribution_baselines.py \
  --data artifacts/value/self-play-value-distribution-focused-64x64.jsonl \
  --model artifacts/models/scorecard-value-distribution-linear-v1.json \
  --output artifacts/reports/scorecard-value-distribution-linear-v1.eval.json \
  --markdown-output docs/scorecard-value-distribution-linear-v1-hard-cases.md \
  --limit 10
```

현재 baseline의 목적은 운영 투입이 아니라 품질 기준선이다.

- 입력: 점수판 상태, 열린 칸 mask, 상단 보너스 진행도, 현재 총점, Yacht bonus 상태
- target: exact self-play가 해당 상태에서 도달한 `target_remaining_score`
- 활용: score-stage utility를 손으로 조정할 때, 실제 full-game 결과와 어긋나는 구간을 찾는 기준선
- hard-case 리포트: baseline이 과대/과소평가하는 점수판 상태를 뽑아 다음 휴리스틱 수정 후보로 쓴다

현재 feature에는 단순 점수뿐 아니라 몇 가지 interaction 신호도 포함한다.

- upper bonus가 아직 살아있는지, 이미 막혔는지
- 4/5/6 상단 칸이 얼마나 남았는지
- Yacht bonus가 켜졌을 때 현금화 가능한 열린 칸이 얼마나 남았는지
- Choice/Yacht/하단 족보/0점 칸 상태

64게임 train smoke + 16게임 holdout smoke 기준:

- train split: 768 state samples, validation MAE 23.43, validation RMSE 32.84
- holdout: 192 state samples, MAE 19.76, RMSE 27.52, R2 0.79
- early game은 같은 empty scorecard에서도 최종 점수 분산이 커서 MAE가 가장 높다
- Yacht bonus active 상태는 폭발적인 후속 점수 가능성이 있어 단순 선형 baseline이 과소평가하기 쉽다

이 결과는 "바로 운영 투입 가능한 value model"이 아니라 다음 설계 방향을 보여준다. 실제 모델 판단에 쓰려면 최소 수백~수천 게임 self-play 데이터로 재학습하고, 평균값 하나뿐 아니라 quantile/variance target도 함께 예측하는 편이 좋다.

`simulate_value_state_distribution.py`는 이 quantile/variance 방향을 확인하기 위한 도구다. hard-case 리포트에서 나온 특정 scorecard를 여러 seed로 이어 플레이해 p10/p50/p90, 최악/최선 outcome을 뽑는다. 평균 remaining score가 비슷해도 p10이 낮은 상태와 p90이 높은 상태는 score-stage 의사결정에서 다르게 다뤄야 한다.

`generate_value_distribution_data.py`는 여러 scorecard state에 대해 같은 분포 target을 JSONL로 저장한다. 이 출력은 `train_value_baseline.py --target target_remaining_p10`처럼 target만 바꿔서 하방/중앙/상방 모델을 따로 학습하는 데 쓸 수 있다.

16-trial smoke 예시:

- `empty`: final mean 175.75, stdev 38.58, p10/p50/p90 136.5 / 166.5 / 236.5
- `yacht_bonus_active`: remaining mean 111.38, stdev 34.97, p10/p50/p90 67.0 / 107.0 / 147.0, best remaining 203

이 숫자는 아직 작은 표본이지만, 초반에는 분산이 크고 Yacht bonus active 상태는 상방이 크게 열린다는 점을 보여준다.

2-state distribution-data smoke에서는 `empty`와 `yacht_bonus_active` preset을 각각 4회 rollout했다. 출력 JSONL은 `target_remaining_mean/stdev/p10/p50/p90` 컬럼을 포함했고, `target_remaining_p10`을 대상으로 한 선형 baseline smoke도 정상 동작했다.

`train_value_distribution_baselines.py`와 `eval_value_distribution_baselines.py`는 p10/p50/p90/mean/stdev/upper-bonus-rate를 한 번에 학습/평가한다. 평가 리포트는 target별 MAE/RMSE와 predicted quantile 순서 위반 비율을 함께 본다.

## Exact Endgame Value Table

score stage 휴리스틱을 장기 가치와 정면 비교하기 위해 후반 endgame value table을 오프라인 artifact로 만든다. 키는 README의 12턴 value DP 실험과 동일하게 `closed_mask:upper_total:yacht_bonus_available`이다.

```bash
python3 scripts/build_value_table.py \
  --batch-open-count 3 \
  --output artifacts/value/endgame-value-table-open3.json \
  --max-states 40000

python3 scripts/build_value_table.py \
  --batch-open-count 4 \
  --output artifacts/value/endgame-value-table-open4.json \
  --max-states 110000
```

측정 결과:

- open3: 38,272 states, 81.881초, artifact 약 1.0MB
- open4: 101,632 states, 245.353초, artifact 약 2.7MB

N=4는 실시간 요청 중 계산할 대상은 아니지만, 오프라인으로 만들어두고 score stage의 `즉시 점수 + V(next_state)` 실험에 쓰기에는 현실적인 크기다.

score stage value mode는 운영 기본값을 바꾸지 않는 opt-in 경로다.

```bash
YACHT_SCORE_STAGE_MODE=value \
YACHT_ENDGAME_VALUE_TABLE=artifacts/value/endgame-value-table-open4.json \
python3 server.py
```

roll/keep 판단은 유지하고 실제 점수 기록 순간만 exact V를 쓰는 좁은 모드는 `value_score_only`다.

```bash
YACHT_SCORE_STAGE_MODE=value_score_only \
YACHT_ENDGAME_VALUE_TABLE=artifacts/value/endgame-value-table-open4.json \
python3 server.py
```

table에 있는 후반 next state는 exact V를 쓰고, 아직 커버하지 못하는 초반 상태는 기존 휴리스틱으로 fallback한다. 이 단계에서는 learned value model을 연결하지 않는다.

기존 `scripts/check_ai_golden.py`는 운영 기본값인 휴리스틱 추천을 고정하는 회귀 테스트다. value mode는 score-stage 결정을 의도적으로 바꿀 수 있으므로 별도 full-game A/B로 평가한다.

200게임 paired A/B (`scripts/simulate_score_value_games.py --games 200 --seed 20260708 --mode focused`) 결과:

- heuristic: 평균 177.635, 표준편차 44.5676, Upper Bonus 34.5%, Yacht bonus 평균 0.030
- value mode: 평균 178.440, 표준편차 47.9419, Upper Bonus 40.5%, Yacht bonus 평균 0.035
- paired delta: 평균 +0.805점, median 0점, win/loss/tie 30.5% / 37.0% / 32.5%, 범위 -72~+193
- value mode는 게임당 평균 5.0 score-stage turns에서 endgame table을 hit했고, 나머지 7.0 turns는 초반 fallback이었다.
- value_score_only: 평균 177.650, 표준편차 44.7589, Upper Bonus 39.0%, paired delta 평균 +0.015점, win/loss/tie 21.0% / 28.0% / 51.0%, 범위 -77~+104
- value_score_only도 게임당 평균 5.0 score-stage turns에서 endgame table을 hit했고, roll/keep 판단은 휴리스틱으로 유지했다.

결론: exact endgame V는 Upper Bonus 페이스를 올리지만 손실 꼬리도 남는다. full value mode는 평균 개선이 있지만 roll/keep 선택까지 흔들어 분산이 커지고, value_score_only는 더 보수적이지만 평균 개선이 거의 없다. 운영 기본값은 유지하고, 다음 실험은 큰 음수 delta를 줄이는 guard 조건을 먼저 찾는 방향이 맞다.

## Learned Early Value Hybrid

초반 미커버 상태를 채우기 위해 256 self-play games / 3,072 samples로 `scorecard-value-linear-v1`을 재학습했다.

- train: 2,458 examples, MAE 22.5723, RMSE 31.7251, R2 0.7613
- validation: 614 examples, MAE 24.4397, RMSE 33.9404, R2 0.7295
- full-data eval: 3,072 examples, MAE 22.9456, RMSE 32.1800, R2 0.7550

hybrid 모드는 `exact endgame table -> learned linear value -> heuristic fallback` 순서다. guard는 다음 조건을 둔다.

- model target이 `target_remaining_score`
- feature schema가 현재 encoder와 일치
- validation MAE <= 25.0
- learned V를 쓰는 next state가 최소 5턴 이상 진행된 상태
- 예측 remaining score는 0~350 범위로 clamp

200게임 paired A/B 결과:

- heuristic: 평균 177.635, 표준편차 44.5676, Upper Bonus 34.5%
- hybrid: 평균 168.895, 표준편차 43.5269, Upper Bonus 36.5%
- paired delta: 평균 -8.740점, win/loss/tie 39.0% / 56.5% / 4.5%, 범위 -150~+146
- hybrid는 게임당 평균 exact table 5.0 turns, learned model 3.0 turns, heuristic fallback 4.0 turns를 사용했다.

결론: 현재 선형 learned value는 validation MAE guard를 통과해도 full-game 의사결정에는 해롭다. 특히 초반 상태의 정책 분포 shift를 감당하지 못하므로 운영 기본값은 계속 휴리스틱이고, learned value는 더 많은 데이터, turn별 calibration, quantile/uncertainty guard, 비선형 모델 전까지 연결하지 않는다.
