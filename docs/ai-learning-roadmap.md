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
```

현재 baseline의 목적은 운영 투입이 아니라 품질 기준선이다.

- 입력: 점수판 상태, 열린 칸 mask, 상단 보너스 진행도, 현재 총점, Yacht bonus 상태
- target: exact self-play가 해당 상태에서 도달한 `target_remaining_score`
- 활용: score-stage utility를 손으로 조정할 때, 실제 full-game 결과와 어긋나는 구간을 찾는 기준선

8게임 smoke 기준으로 데이터 생성과 선형 baseline 학습은 정상 동작했다. 실제 모델 판단에 쓰려면 최소 수백~수천 게임 self-play 데이터로 재학습하고, endgame holdout과 full-game simulation을 같이 확인해야 한다.
