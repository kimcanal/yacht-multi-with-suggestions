# 대학원 면접 예상 질문과 답변 — Yacht AI

답변은 결론부터 20~40초 안에 말하는 것을 기준으로 작성했다. 질문이 깊어질 때만 두 번째 문단의 세부 내용을 덧붙인다.

## 연구 문제와 기여

### Q1. 이 프로젝트의 연구적 기여를 한 문장으로 말해보세요.

Exact solver를 정답 기준선으로 만들고, 학습 정책의 오류를 accuracy가 아닌 decision regret으로 측정한 뒤, confidence와 EV gap 기반 fallback으로 위험한 행동을 통제한 것입니다.

새로운 신경망 구조를 제안했다기보다, 학습 모델을 어디까지 신뢰할 수 있는지 정량적으로 검증하고 안전한 배치 구조로 연결한 데 의미가 있습니다.

### Q2. 왜 하필 Yacht를 연구 대상으로 선택했나요?

규칙은 작지만 확률, 장기 보상, 조합적 행동 공간이 함께 있어 순차적 의사결정 연구를 끝까지 검증하기 좋은 환경이기 때문입니다. 일부 구간은 exact 해를 구할 수 있어 모델 성능의 절대 기준선을 만들 수 있고, 동시에 전체 게임에서는 장기 전략과 계산 비용 문제가 나타납니다.

### Q3. 단순 게임 프로젝트와 연구 프로젝트의 차이는 무엇인가요?

기능 구현에서 멈추지 않고 명확한 가설, 기준선, 지표, 통제 실험, 실패 사례와 한계를 함께 제시했다는 점입니다. 특히 “정확도가 높으면 안전하다”는 가정을 hard-case와 EV regret로 반증하고 guard 구조를 검증했습니다.

## MDP와 Exact Solver

### Q4. 이 문제를 MDP로 어떻게 정의했나요?

상태는 주사위 구성, 남은 reroll 횟수, 열린 점수 칸 mask, 상단 점수와 보너스 상태입니다. 행동은 roll 단계의 keep 조합 또는 score 단계의 기록할 카테고리이며, 최종 누적 점수를 보상으로 둡니다. 전이확률은 공정한 주사위 분포로 정확히 알 수 있습니다.

### Q5. 무엇이 exact이고 무엇이 근사인가요?

남은 reroll의 주사위 결과와 keep 선택은 정확히 열거하고 DP로 평가합니다. score-stage 장기 가치는 precomputed full-game value table을 사용합니다. 학습 모델은 roll-stage의 exact 행동을 근사하며, 위험한 후보는 다시 exact 평가로 검증합니다.

운영 UI의 설명 가능한 focused heuristic과 full value-optimal 정책은 목적이 다르므로, 발표에서는 어떤 정책을 비교하는지 명확히 구분해야 합니다.

### Q6. 상태공간이 왜 커지나요?

점수 칸의 open/closed mask만 12개이므로 최대 \(2^{12}\)개이고, 여기에 상단 누적 점수, Yacht bonus 상태, 주사위 multiset, 남은 굴림 수가 결합됩니다. 매 요청에서 전체 게임을 처음부터 재탐색하기보다 반복되는 상태 가치를 미리 계산하고 캐시하는 이유입니다.

### Q7. 시작 상태의 이론적 기대점수 198.36과 simulation의 198.645가 왜 다른가요?

198.36은 value table이 계산한 기대값이고, 198.645는 200개 표본 게임의 관측 평균입니다. 유한 표본에는 주사위 운에 따른 분산이 있으므로 두 값이 정확히 일치할 필요는 없습니다. 표본을 늘리면 관측 평균이 이론값 근처로 수렴하는지를 추가로 확인해야 합니다.

## 지표와 통계

### Q8. Accuracy가 98.52%면 충분하지 않나요?

아닙니다. 모든 오분류의 비용이 같지 않기 때문입니다. EV가 거의 같은 두 행동을 바꾸는 오류와 완성된 강한 패를 깨는 오류는 accuracy에서는 똑같이 한 건이지만 실제 손실은 크게 다릅니다. 그래서 \(Q^*(s,a^*)-Q^*(s,a)\)인 decision regret을 핵심 지표로 사용했습니다.

### Q9. Decision regret의 장점은 무엇인가요?

최종 게임 점수보다 주사위 운의 영향을 덜 받고, 손실이 roll 단계인지 score 단계인지 분해할 수 있습니다. 또한 worst decision을 상태 단위로 재현할 수 있어 다음 개선 대상을 직접 찾을 수 있습니다.

### Q10. Paired simulation을 쓴 이유는 무엇인가요?

두 정책에 같은 seed의 주사위 흐름을 적용해 운에서 오는 변동을 최대한 상쇄하기 위해서입니다. 정책별 독립 게임 평균을 비교하는 것보다 정책 변화의 효과를 더 민감하게 볼 수 있습니다.

다만 정책이 서로 다른 시점에 다른 개수의 주사위를 굴리면 단순 random stream 비교가 완전한 공통 난수를 보장하지 않을 수 있어, indexed random source 실험도 별도로 두었습니다.

### Q11. +9.04점 개선은 통계적으로 유의한가요?

200 paired games에서 평균 차이의 95% 정규근사 신뢰구간은 +3.43점에서 +14.65점이고, two-sided p-value는 0.00159였습니다. 따라서 이 표본에서는 0보다 큰 개선이라는 근거가 있습니다.

다만 standardized paired effect size는 약 0.223으로 크지 않고, 고정 seed와 200게임이라는 범위가 있으므로 더 큰 표본과 복수 seed 재검증이 필요합니다.

### Q12. 왜 최종 점수와 regret 결과의 평균이 서로 다른가요?

서로 다른 평가 목적과 random source를 가진 별도 실험이기 때문입니다. Decision-regret 실험은 각 결정의 exact Q 손실을 측정하고, score-stage A/B는 200개의 full-game 결과를 비교합니다. 절대 평균을 섞지 않고 각 실험 안에서 정책 간 차이를 해석합니다.

## 모델과 Guard

### Q13. 모델 구조를 설명해보세요.

41개 상태 feature를 입력받고 hidden dimension 96을 거쳐 462개의 keep-count class를 분류하는 MLP입니다. 32,768개의 exact teacher state를 만들었고, 26,214개를 학습에, 6,554개를 검증에 사용했습니다.

구조를 크게 만드는 실험보다 같은 teacher data에서 안정적으로 수렴하는 설정과 배치 guard가 더 중요했습니다.

### Q14. Confidence 0.95와 EV gap 0.25는 어떻게 정했나요?

Confidence는 모델이 스스로 확신하는 구간을 고르고, EV gap은 그 확신이 실제 가치와 일치하는지 확인하는 서로 다른 역할을 합니다. 현재 값은 validation report에서 coverage와 accepted accuracy, 최대 손실의 trade-off를 비교해 선택한 운영 기준입니다.

향후에는 고정 threshold가 아니라 calibration set에서 목표 risk bound를 만족하도록 자동 선택하는 selective prediction 방식으로 개선할 수 있습니다.

### Q15. 정확도를 보려면 confidence guard만으로 충분하지 않나요?

충분하지 않습니다. 신경망은 틀린 예측에도 높은 confidence를 줄 수 있습니다. 실제로 중요한 것은 confidence 자체가 아니라 후보 행동의 가치 손실이므로 exact EV gap guard를 함께 사용했습니다.

### Q16. Guard를 썼는데 왜 채택률이 46.96%밖에 안 되나요?

안전성을 우선한 결과입니다. 낮은 채택률은 위험한 상태를 많이 fallback해 손실을 줄인다는 장점이 있지만, 계산량 절감이 제한된다는 단점도 있습니다. 이 trade-off를 숨기지 않고 다음 연구 문제로 두었습니다.

### Q17. Exact guard를 매번 계산하면 모델을 쓰는 의미가 없지 않나요?

현재 구현만으로 큰 속도 향상을 입증했다고 말할 수는 없습니다. 이 단계의 목적은 learned candidate의 위험 구간을 식별하고 안전한 배치 가능성을 검증하는 것이었습니다. 실제 계산 절감을 얻으려면 cheap bound, uncertainty calibration, 상태별 selective verification, Q-value surrogate 같은 방법으로 exact 검증 자체를 줄여야 합니다.

이 질문에는 방어적으로 답하기보다 현재 한계를 인정하고, 바로 후속 연구 문제로 연결하는 편이 좋습니다.

### Q18. 검증 split에서 EV gap이 0이면 안전성이 보장된 것 아닌가요?

아닙니다. 관측한 6,554개 validation state에서 fallback을 포함한 추가 손실이 0이었다는 뜻입니다. 분포 밖 상태나 새로운 teacher data에 대한 수학적 보장은 아니며, 별도 seed, adversarial hard case, calibration split으로 재검증해야 합니다.

### Q19. Model-only의 평균 손실은 작은데 최대 손실이 큰 이유는 무엇인가요?

대부분 상태에서는 teacher와 같거나 가치가 거의 같은 행동을 선택하지만, 드물게 이미 완성된 강한 패를 깨는 행동을 선택했습니다. 이 long-tail error 때문에 평균만 보면 위험을 놓칠 수 있고, p95뿐 아니라 max와 hard-case를 함께 봐야 했습니다.

## 결과 해석과 한계

### Q20. Runtime 모델이 어떤 실험에서는 exact보다 평균 점수가 높았는데 모델이 더 좋은 것 아닌가요?

그렇게 해석하지 않습니다. 100게임의 유한 표본에서 생긴 확률적 변동일 수 있고, teacher imitation 모델이 기준 정책을 체계적으로 능가했다는 증거가 아닙니다. 정책 우위를 주장하려면 훨씬 큰 paired sample과 신뢰구간이 필요합니다.

### Q21. Cold latency 58~140ms면 이미 충분히 빠르지 않나요?

현재 웹 추천 UX에는 사용할 수 있는 수준이지만, 동시 요청이 늘거나 Monte Carlo 승률 계산까지 결합되면 서버 비용이 커질 수 있습니다. 따라서 latency 숫자는 문제 해결의 증거라기보다 현재 기준선이며, throughput과 tail latency를 포함한 부하 실험이 추가로 필요합니다.

### Q22. 가장 큰 실험적 한계는 무엇인가요?

첫째, 일부 full-game 평가는 100~200게임과 고정 seed에 의존합니다. 둘째, teacher distribution에서 만든 validation split이 실제 사용자 상태 분포를 완전히 대표하지 않습니다. 셋째, 현재 목적함수는 주로 기대점수여서 상대와 점수차가 있는 멀티플레이 승률 최적화와 다릅니다.

### Q23. 재현 가능성은 어떻게 확보했나요?

학습 seed, 데이터 split, model metadata, simulation seed를 report에 저장했고, 평가 결과를 Markdown 요약뿐 아니라 원본 JSON으로 보관했습니다. 학습, EV-gap 평가, runtime guard 평가, full-game simulation 명령도 문서화했습니다.

## 대학원 연구 확장

### Q24. 대학원에서 가장 먼저 확장한다면 무엇을 하겠나요?

Selective prediction으로 모델의 risk–coverage curve를 체계적으로 측정하겠습니다. 별도의 calibration set에서 허용 regret을 정하고, 그 범위 안에서 coverage를 최대화해 현재 46.96%인 채택률과 exact 검증 비용을 개선하는 것이 첫 과제입니다.

### Q25. 강화학습으로 바로 풀지 않은 이유는 무엇인가요?

전이확률과 일부 exact value를 알 수 있는 환경에서는 먼저 강한 기준선과 평가기를 만드는 것이 더 안정적이라고 판단했습니다. 기준선 없이 self-play만 사용하면 성능 개선인지 평가 노이즈인지 구분하기 어렵습니다. 이후 exact value를 offline target 또는 critic 검증에 활용해 RL로 확장할 수 있습니다.

### Q26. 멀티플레이어로 확장하면 목적함수가 어떻게 바뀌나요?

평균 최종점수가 아니라 현재 점수차와 상대 상태를 조건으로 한 승리 확률이 목적함수가 됩니다. 뒤지고 있을 때는 고분산 행동, 앞서 있을 때는 저분산 행동이 더 유리할 수 있으므로 점수 분포 전체를 예측하는 distributional value model이 필요합니다.

### Q27. 논문 형태로 발전시키려면 어떤 실험이 더 필요한가요?

복수 seed와 수천 게임 규모의 paired evaluation, confidence calibration 비교, risk–coverage curve, guard 구성요소별 ablation, distribution shift와 adversarial hard-case 평가가 필요합니다. 여기에 exact verification 비용까지 포함한 quality–latency Pareto frontier를 제시하면 연구 질문이 더 선명해집니다.

## 개인 기여와 구현

### Q28. 본인이 직접 한 일은 무엇인가요?

상태와 action 정의, exact solver와 value table 연결, teacher data 생성과 MLP 학습, regret·paired simulation·runtime 평가 도구, guard와 fallback 설계, 그리고 웹 서비스 통합과 회귀 검증까지 전체 파이프라인을 구현했습니다.

실제 답변에서는 공동 작업이 있었다면 자신의 기여와 다른 사람의 기여를 정확히 구분해서 말한다.
### Q29. 구현 중 가장 어려웠던 점은 무엇인가요?

모델 정확도를 높이는 것보다 서로 다른 평가가 같은 결론을 지지하도록 만드는 것이 어려웠습니다. 최종 점수는 분산이 크고 accuracy는 오류 비용을 숨기므로, exact Q 기반 regret과 paired simulation을 함께 만들고 worst case를 재현 가능한 상태로 저장했습니다.

### Q30. 실패한 시도에서 배운 점은 무엇인가요?

모델 크기를 키운 hidden dimension 160 후보가 오히려 top-1 98.31%로 낮아졌고, model-only 배치는 높은 평균 정확도에도 rare hard case를 남겼습니다. 데이터와 기준선이 제한된 상황에서는 모델 규모보다 평가 설계, calibration, fallback이 더 중요하다는 것을 배웠습니다.
