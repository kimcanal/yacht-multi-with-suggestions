# Yacht AI Portfolio Summary

이 프로젝트의 AI 작업은 "요트 주사위에서 어떤 주사위를 keep할지 추천한다"에서 끝나지 않는다. 핵심은 추천을 만들고, 그 추천이 실제로 안전한지 검증하고, 모델을 exact solver의 대체재가 아니라 guarded candidate generator로 배치한 점이다.

## 30-Second Pitch

요트 다이스는 한 턴 안에서는 모든 keep/reroll 경우를 계산할 수 있지만, 전체 12턴을 매 요청마다 완전 탐색하기에는 부담이 커진다. 이 프로젝트는 그 경계를 분리했다. 한 턴 안의 roll decision은 exact DP로 계산하고, 게임 전체의 장기 가치는 score-stage utility와 simulation으로 검증한다.

학습 모델은 "AI라서 무조건 믿는" 구조가 아니다. exact solver를 teacher로 삼아 roll-stage MLP를 학습했고, 운영에서는 confidence와 exact gap guard를 통과한 경우에만 모델 출력을 사용한다. 통과하지 못하면 exact solver로 fallback한다.

포트폴리오에서 강조할 한 줄은 이렇다.

> Exact solver로 기준선을 만들고, ML 모델의 위험 구간을 EV gap과 full-game simulation으로 검증한 뒤, runtime guard로 안전하게 배치한 AI 추천 시스템.

## Interview Talking Points

- 왜 full-game DP를 바로 하지 않았나: 상태공간은 점수판 mask, upper total, Yacht bonus 가능성까지 커지므로 운영 요청마다 12턴 전체를 exact로 푸는 방식은 비효율적이다.
- 어디까지 exact인가: 남은 reroll 안의 keep -> chance -> keep -> chance -> score 평가는 exact tree/DP다.
- 어디부터 heuristic인가: 점수칸에 실제로 기록하는 단계는 즉시 점수, Upper/Yacht Bonus, 남은 칸의 future pressure를 섞은 utility다.
- 모델이 배운 것은 무엇인가: score decision 전체가 아니라 roll stage에서 exact solver의 keep 선택을 빠르게 근사하는 정책이다.
- 검증에서 얻은 결론은 무엇인가: teacher accuracy가 높아도 model-only는 rare worst-case가 있으므로, confidence + exact guard + fallback이 필요하다.
- 제품 관점의 보강은 무엇인가: 싱글 랭킹과 멀티 점수 저장은 서버가 세션/주사위/점수판을 검증해서 클라이언트 조작을 줄였다.

## Problem

요트 다이스는 한 턴 안에서는 경우의 수를 exact tree/DP로 계산할 수 있지만, 전체 12턴을 완전 탐색하기에는 상태공간이 빠르게 커진다. 그래서 이 프로젝트는 한 턴 내부 roll/reroll 선택은 exact하게 계산하고, 점수 기록 단계는 즉시 점수와 장기 압력을 섞은 utility로 근사한다.

사용자에게 보여주는 추천은 단순히 "확률이 높다"가 아니라 아래 질문에 답해야 한다.

- 지금 멈추는 편이 좋은가, 한 번 더 굴리는 편이 좋은가?
- 어떤 점수칸이 열려 있을 때 이 keep이 유리한가?
- Upper Bonus와 Yacht Bonus 가능성이 선택을 바꾸는가?
- 실패했을 때 장기적으로 어떤 칸을 희생하는 것이 덜 아픈가?

## Approach

1. Exact solver를 teacher로 사용한다.
   - `rolls_left=2`: keep -> chance -> keep -> chance -> score 평가
   - `rolls_left=1`: keep -> chance -> score 평가
   - `rolls_left=0`: score 평가

2. Roll-stage MLP를 distillation한다.
   - 모델: `model-20260630-roll-policy-v2`
   - 입력: dice counts, rolls_left, strategy mode, scorecard 상태
   - 출력: keep-count class 462개 중 하나
   - 목적: exact solver 선택을 빠르게 근사

3. 모델을 무조건 믿지 않는다.
   - confidence threshold를 통과해야 한다.
   - exact gap guard를 통과해야 한다.
   - 실패하면 exact solver로 fallback한다.

## What The Model Learned

Held-out teacher split 기준:

| Model | Top-1 | Top-3 | Raw mean excess EV gap |
| --- | ---: | ---: | ---: |
| v1 | 98.5505% | 99.7864% | 0.036379 |
| v2 | 98.5200% | 99.7559% | 0.023701 |

made-hand safety override 이후 v1은 top-1 accuracy에서 아주 근소하게 앞서고, v2는 teacher 대비 평균 추가 EV 손실이 더 낮다. 하지만 이 수치만으로 "게임을 더 잘한다"고 말할 수는 없다. teacher imitation은 독립적인 실력 검증이 아니기 때문이다.

## Safety Finding

EV gap 검증에서 가장 중요한 발견은 모델 단독 사용의 위험이다.

- v2 raw model-only mismatch: 97 / 6,554
- mean excess EV gap: 0.023701
- p95 excess EV gap: 0
- max excess EV gap: 10.145227

대부분의 케이스는 안전하지만, 드물게 이미 강한 패를 일부만 keep하는 hard case가 나온다. 예를 들어 5개가 이미 완성된 상황에서 모델이 4개만 keep하면 큰 손실이 생긴다.

그래서 서버 운영 정책은 모델을 무조건 사용하지 않는다.

Runtime guard 기준:

- confidence threshold: 0.95
- exact objective gap guard: 0.25
- accepted examples: 3,078 / 6,554
- acceptance rate: 46.9637%
- accepted accuracy: 99.3827%
- fallback 포함 effective excess EV gap: mean 0, max 0

결론은 명확하다. 모델은 exact solver를 대체하지 않는다. 모델은 빠른 후보를 만들고, exact guard가 위험한 후보를 걸러낸다.

## Full-Game Simulation

single-turn accuracy만으로는 실제 게임 점수 영향을 알 수 없어서, 같은 seed 묶음으로 complete game simulation을 돌렸다. 점수 기록은 동일한 exact score-stage를 쓰고, roll-stage 정책만 바꿨다.

Focused mode, 100 games, seed `20260630`:

| Policy | Avg total | Delta vs exact | Upper bonus rate | Avg zero categories |
| --- | ---: | ---: | ---: | ---: |
| exact | 152.21 | +0.00 | 12.00% | 1.34 |
| v1 runtime | 154.19 | +1.98 | 12.00% | 1.38 |
| v2 runtime | 155.70 | +3.49 | 13.00% | 1.36 |
| v1 model-only | 151.63 | -0.58 | 6.00% | 1.54 |
| v2 model-only | 148.88 | -3.33 | 5.00% | 1.69 |

Runtime fallback을 넣으면 exact와 같은 점수대를 유지한다. 반대로 model-only는 safety override 이후에도 평균 점수와 upper bonus rate가 떨어진다.

## Evidence

- Model v2 report: [model-20260630-roll-policy-v2.md](./model-20260630-roll-policy-v2.md)
- Hard cases: [model-20260630-roll-policy-v2-hard-cases.md](./model-20260630-roll-policy-v2-hard-cases.md)
- Full-game simulation JSON: `artifacts/reference/reports/roll-policy-full-game-focused-100.json`
- Runtime validation JSON: `artifacts/reference/reports/model-20260630-roll-policy-v2.runtime.json`

## Takeaway

이 AI 작업에서 얻은 것은 "ML 모델이 exact solver보다 낫다"가 아니다. 오히려 반대에 가깝다.

얻은 것은 다음이다.

- exact DP가 가능한 범위와 heuristic이 필요한 범위를 구분했다.
- teacher imitation accuracy가 실전 안전성과 다르다는 것을 EV gap으로 확인했다.
- model-only의 rare worst-case를 hard-case report로 드러냈다.
- confidence + exact guard + fallback 구조가 위험한 모델 출력을 막는다는 것을 runtime validation과 full-game simulation으로 확인했다.

포트폴리오 관점에서 이 프로젝트의 강점은 모델을 붙였다는 점이 아니라, 모델을 어디까지 믿을 수 있는지 검증하고 안전하게 배치했다는 점이다.
