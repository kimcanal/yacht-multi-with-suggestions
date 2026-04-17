# AI Logic, Formally

추천 엔진이 어떤 상태를 보고 keep / reroll / score 결정을 내리는지 수식 중심으로 정리한다. 구현은 [`yacht_ai/solver.py`](../yacht_ai/solver.py), [`yacht_ai/advice.py`](../yacht_ai/advice.py), [`yacht_ai/ml_policy.py`](../yacht_ai/ml_policy.py)에 있다.

---

## 왜 exact DP인가

요트 추천에서 한 턴은 세 가지 결정이 맞물린다. 어떤 주사위를 keep할지, 남은 reroll에서 어떤 결과 분포가 생기는지, 마지막에 어느 칸에 기록하는 게 유리한지.

이 프로젝트는 한 턴 안의 의사결정을 exact turn DP로 풀고, 점수 기록 단계는 점수판 맥락까지 반영한 utility 함수로 정리한다.

exact로 푸는 이유는 세 가지다. 주사위가 5개뿐이라 상태 공간을 정렬된 multiset 기준으로 압축할 수 있고, 남은 reroll이 최대 2라 한 턴 안의 상태 전이는 exact 계산이 가능하다. 반면 경기 전체 12턴을 full-game DP로 푸는 건 비용이 커서, 현재 구현은 score stage에서 장기 가치 휴리스틱을 섞는 방식으로 타협한다.

## 상태 표현

한 턴의 roll state를 이렇게 정의한다.

```
s = (d, r, c, m)
```

- `d`: 현재 주사위 multiset
- `r`: 남은 reroll 수
- `c`: 현재 점수판 상태
- `m`: 추천 모드 (`focused` 또는 `cover`)

주사위 `d`는 순서 대신 개수 벡터로도 쓸 수 있다.

```
n(d) = (n1, n2, n3, n4, n5, n6),  sum_i ni = 5
```

이미지처럼 공간적 locality가 중요한 문제가 아니라, 작은 조합 상태와 점수판 특징이 중요한 구조다.

## roll stage: exact turn DP

현재 주사위 `d`에서 keep action `k`는 `d`의 부분 multiset이다.

```
k ⊆ d
```

`k`를 유지하면 나머지 `5 - |k|`개를 다시 굴리고 다음 상태 `d'`로 전이한다. 전이확률은 독립 균등 주사위를 그대로 따른다.

```
P(d' | k) = Multinomial(5 - |k|, 1/6, ..., 1/6)
```

구현은 주사위 순서를 버린 multiset 전이분포를 미리 계산해 exact 합산한다.

roll stage 상태가치:

```
V_roll(d, r, c, m)
  = max(
      U_stop(d, c, m),
      max_k sum_{d'} P(d' | k) V_roll(d', r - 1, c, m)
    )
```

- `U_stop(d, c, m)`: 지금 굴림을 멈추고 점수 기록 단계로 넘어갈 때의 가치
- `k`: 가능한 모든 keep action

"계속 굴릴 기대값"과 "지금 바로 기록할 가치"를 같은 축에서 비교하는 게 핵심이다.

## focused mode: 한 족보를 깊게 미는 기준

`focused` 모드에서는 각 족보 `t`에 대해

```
P_t(k) = sum_{d'} P(d' | k) T_t(d', r - 1, c)
```

를 계산한다. 여기서 `T_t(d, r, c)`는 남은 reroll에서 족보 `t`를 달성할 최적 성공 확률이다.

이 확률과 보조 tie-break를 함께 써서 어떤 keep이 특정 족보를 가장 잘 살리는지 정한다. `4 of a Kind`는 단순 성공 확률뿐 아니라 성공 시 평균 점수도 같이 본다.

## cover mode: exact union probability

`cover` 모드는 열린 하단 족보 집합을

```
H = {4 of a Kind, Full House, Small Straight, Large Straight, Yacht}
```

중 현재 열려 있는 것들로 제한하고, "하나 이상 성공" 확률을 직접 계산한다.

```
P_cover(k) = P( union_{t in H} E_t )
```

이 값을 독립 가정으로 근사하지 않는다. 어떤 결과는 Full House와 4 of a Kind를 동시에 만족할 수 있어서 단순 합산하면 중복이 생긴다. 구현은 여집합도 exact하게 쓴다.

```
P_fail(k) = 1 - P_cover(k)
```

UI에서 "하나 이상 성공"과 "전부 실패"를 같이 보여주는 이유다.

## score stage: immediate score + long-term pressure

굴림이 끝나면 열린 카테고리 `i`마다 utility를 계산한다.

```
U_score(i | d, c)
  = Score_i(d)
  + Bonus_i(d, c)
  + Quality_i(d, c)
  - Pressure_i(c)
```

현재 구현에서는 이걸 이렇게 나눈다.

```
U_i
  = s_i
  + b_upper
  + b_yacht
  + q_i
  + 35 * Delta p_upper
  - p_i
```

- `s_i`: 지금 `i` 칸에 적었을 때 즉시 점수
- `b_upper`: upper bonus를 바로 마감하거나 크게 밀어주는 보너스
- `b_yacht`: Yacht Bonus +100 가치
- `q_i`: "이번 점수 - fresh-turn 기준 기대치"를 반영한 quality bonus
- `Delta p_upper`: 기록 전후 upper bonus 도달 확률 변화
- `p_i`: 이 칸을 지금 닫을 때의 장기 부담

단순히 지금 몇 점이냐만 보는 게 아니라, 이 점수가 평균보다 좋은지, 지금 닫아도 덜 아픈 칸인지, upper bonus 흐름을 살리는지, Yacht Bonus를 현금화하는지를 같이 본다.

`fresh-turn 기대치`와 `closing cost`는 미리 추정한 기준값이다.

## 현재 구조의 한계

한 턴 안의 reroll은 exact하게 풀지만, 경기 전체를 full-game DP로 풀지는 않는다.

score stage utility는 "현재 점수 + 장기 가치 보정"에 가까운 거지, 엄밀하게 "현재 행동 이후 남은 경기 전체 기대값"을 계산하는 건 아니다. 그래서 현재 문서와 코드에서는 score stage를 `future-pressure heuristic`으로 설명한다.

## distillation: exact teacher → lightweight student

운영 환경에서 가장 비싼 부분은 `rolls_left = 2`인 cold-path exact DP다. 그래서 exact 추천을 teacher로 쓰고, 경량 신경망을 student policy로 증류하는 실험을 포함한다.

teacher policy:

```
pi*(s) = argmax_a Q_exact(s, a)
```

여기서 `a`는 keep action이고, `Q_exact`는 exact DP로 계산한 행동가치다.

student model은 상태 특징 `x(s)`를 입력받아 keep action class 분포를 예측한다.

```
pi_theta(a | s) = softmax(f_theta(x(s)))
```

현재 구현은 작은 MLP다. 입력은 주사위 count, 남은 reroll, 열린 칸, 현재 점수, upper gap, Yacht bonus 여부이고, 출력은 가능한 keep class에 대한 확률 분포다. confidence가 낮거나 exact 해와 차이가 크면 즉시 fallback한다.

운영 정책:

```
if confidence >= tau and optimality_gap <= epsilon:
    use student
else:
    use exact teacher
```

## 왜 CNN이나 LSTM이 아닌가

CNN은 이미지처럼 인접 픽셀 locality가 중요할 때 강하다. 여기서 핵심 입력은 "주사위 개수 벡터 + 점수판 feature"지, 공간 구조가 아니다.

LSTM은 긴 시계열 패턴을 잡을 때 유용하다. 하지만 추천 하나는 긴 시퀀스 해석이 필요한 문제가 아니고, 과거 시퀀스 전체보다 현재 점수판과 남은 칸 정보가 훨씬 직접적으로 중요하다.

그래서 현재 단계에서는 exact DP + score-stage heuristic + small MLP distillation 조합이 latency, 해석 가능성, 유지보수성 측면에서 가장 합리적이다.

## 다음 단계

멀티플레이까지 더 강하게 최적화하려면 이 방향이 자연스럽다.

```
V_match(s_self, s_opp) ~= P(win | current state)
```

"내 기대점수 최대화" 대신 "현재 상태에서 최종 승률 최대화"를 직접 예측하는 상대 인식 value model이다. 이 경우 score difference, 상대의 열린 칸, 상대 upper bonus 압력까지 feature에 넣을 수 있다. 그 단계가 되면 멀티플레이 추천은 단순 확률 테이블이 아니라 실제 판세를 반영한 policy로 확장된다.
