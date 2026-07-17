# Exact Solver 면접 설명 가이드

이 문서의 목표는 용어를 외우는 것이 아니라, Yacht 추천 알고리즘을 **자신의 말로 설명하고 질문에 방어할 수 있게 되는 것**이다.

## 1. 한 문장 정의

> Exact Solver는 현재 상태에서 가능한 모든 행동과 그 뒤의 확률적 결과를 게임 규칙대로 계산해, 목표 기대값이 가장 높은 행동을 고르는 프로그램입니다.

여기서 세 단어가 중요하다.

- **모든 행동:** 일부 후보만 찍어보는 것이 아니라 가능한 keep 또는 점수 칸을 빠짐없이 비교한다.
- **확률적 결과:** 주사위 결과마다 발생 확률을 곱해 평균, 즉 기대값을 구한다.
- **정해진 목표:** 이 프로젝트의 `value_optimal`은 기대 최종점수를 최대화한다.

`Exact`는 “무조건 현실에서 완벽하다”는 뜻이 아니다. **구현한 게임 규칙, 상태 표현, 목적함수 안에서 근사 없이 계산한다**는 뜻이다.

## 2. 가장 쉬운 예시

현재 주사위가 `[2, 2, 3, 5, 6]`이고 reroll이 한 번 남았다고 하자.

### 행동 A: `[2, 2]`를 keep

나머지 주사위 3개를 굴리므로 순서를 포함하면 가능한 결과는 다음과 같다.

\[
6^3=216
\]

각 결과가 나온 뒤 열린 점수 칸마다 아래 값을 계산한다.

\[
\text{이번에 얻는 점수}+\text{그 칸을 닫은 뒤 남은 게임의 기대점수}
\]

216개 결과의 값에 각각의 확률을 곱해 더하면 `[2, 2] keep`의 기대값이 된다.

### 행동 B: 모두 reroll

이번에는 주사위 5개를 다시 굴리므로 \(6^5=7,776\)개의 순서 있는 결과가 있다. 같은 방식으로 결과별 최선의 점수 기록 가치와 확률을 계산한다.

### 최종 선택

`[2, 2] keep`, `[2, 3] keep`, `[5, 6] keep`, `모두 reroll` 등 가능한 모든 고유 keep의 기대값을 비교해 가장 큰 것을 추천한다.

실제 코드는 같은 숫자의 순서를 구분할 필요가 없으므로 주사위를 정렬한 multiset으로 합치고, 합쳐진 결과의 정확한 확률을 사용한다. 그래서 계산량은 줄지만 결과는 근사되지 않는다.

## 3. Reroll이 두 번 남으면 어떻게 하나

한 번 남았을 때의 계산을 재귀적으로 한 단계 더 수행한다.

\[
Q(s,\text{keep})=
\sum_{s'}P(s'\mid s,\text{keep})V(s')
\]

\[
V(s')=\max\left(
\text{지금 기록하는 가치},
\max_{\text{next keep}}Q(s',\text{next keep})
\right)
\]

말로 풀면 다음과 같다.

1. 지금 keep 하나를 선택한다.
2. 그 뒤 나올 수 있는 주사위와 확률을 모두 계산한다.
3. 각 다음 상태에서도 “지금 멈출지, 다시 굴릴지” 중 더 좋은 값을 고른다.
4. 결과별 값을 확률 가중 평균한다.
5. 현재 가능한 모든 keep 중 기대값이 가장 큰 것을 고른다.

동일한 `정렬된 주사위 + 남은 reroll 수` 상태가 반복되므로 dynamic programming과 cache로 한 번 계산한 값을 재사용한다.

## 4. 점수판의 장기 가치는 어떻게 계산했나

이번 턴만 잘하는 것으로는 부족하다. 어느 칸에 기록했는지가 다음 턴부터의 선택지를 바꾸기 때문이다.

이 프로젝트는 점수판을 다음 세 값으로 압축한다.

\[
(\text{closed category mask},\ \text{upper total},\ \text{Yacht bonus available})
\]

- `closed category mask`: 12개 칸의 사용 여부를 12비트로 표현
- `upper total`: Upper Bonus 판단에 필요한 상단 합을 0~63으로 제한
- `Yacht bonus available`: 이미 Yacht 50점을 얻어 추가 보너스가 가능한지

가능한 압축 상태 수는 다음과 같다.

\[
2^{12}\times64\times2=524,288
\]

게임이 끝난 상태의 미래 가치는 0이다. 여기서 한 칸, 두 칸, 세 칸이 남은 상태 순으로 거꾸로 계산하는 **backward induction**을 사용한다.

\[
V(s)=\mathbb{E}_{\text{첫 굴림}}
\left[
\max_{\text{keep 또는 score}} Q(s,a)
\right]
\]

전체 표는 오프라인에서 약 1,569초에 계산해 `.npz`로 저장했다. 서비스 요청에서는 이 긴 계산을 반복하지 않고, 다음 점수판 상태의 값을 table에서 조회한다.

## 5. 실제 코드에서는 어디에 있나

### 주사위 결과와 확률

- [`get_outcomes_probs`](../yacht_core/scoring.py#L10): \(6^k\) 결과를 생성하고 같은 정렬 결과를 합쳐 정확한 확률을 만든다.
- [`get_keep_options`](../yacht_core/scoring.py#L24): 5개 주사위의 bit mask를 순회해 고유 keep 후보를 만든다.
- [`get_transition_distribution`](../yacht_core/scoring.py#L43): 한 keep에서 다음 주사위 상태로 갈 확률분포를 만든다.

### 한 턴의 exact DP

- [`exact_turn_value`](../yacht_ai/solvers/exact.py#L945): 지금 기록하는 가치와 모든 keep의 기대값 중 최댓값을 구한다.
- [`evaluate_keep_transition`](../yacht_ai/solvers/exact.py#L895): 다음 주사위별 확률과 다음 상태 가치를 곱해 더한다.
- [`keep_action_values`](../yacht_ai/solvers/exact.py#L1002): 현재 가능한 모든 keep의 값을 비교한다.

### 전체 게임 value table

- [`score_transition`](../scripts/build_value_table.py#L124): 한 점수 칸을 기록했을 때 즉시 점수, Upper Bonus, Yacht Bonus와 다음 상태를 계산한다.
- [`build_exact_endgame_batch_table`](../scripts/build_value_table.py#L229): 종료 상태부터 open count 순서로 모든 압축 상태의 값을 계산한다.
- [`exact_fresh_turn_ev_from_terminal`](../scripts/build_value_table.py#L215): 한 턴의 두 번 reroll을 backward DP로 계산한다.
- [`lookup_state`](../yacht_ai/value/endgame.py#L77): 런타임에 미리 만든 value table을 조회한다.

면접에서는 함수 이름을 외울 필요는 없다. “결과 분포 생성 → keep별 기대값 → 점수 기록 후 미래 가치 → 최댓값” 흐름을 이해하면 된다.

## 6. 정책 모드별로 어디까지 exact인가

이 구분은 반드시 알고 있어야 한다.

| 모드 | Roll decision | Score decision | 설명 |
| --- | --- | --- | --- |
| `focused` 과거 실험 | 목표 지향 heuristic | heuristic | 설명 가능한 추천 중심 |
| 현재 기본 `focused` | 목표 지향 roll | **exact V** | roll 설명력 유지, score 손실 제거 |
| `value_score_only` | focused roll | **exact V** | score-stage 교체 실험 정책 |
| `value_optimal` / UI `optimal` | **exact EV** | **exact V** | 기대 최종점수 기준 전체 최적 정책 |
| learned roll policy | MLP 후보 + guard/fallback | 설정한 score mode | 모델 단독 정책이 아님 |

따라서 “우리 추천 알고리즘 전체가 항상 exact입니다”라고 말하면 틀리다.

정확한 표현은 다음과 같다.

> 이 프로젝트는 exact 기준선과 설명 가능한 focused 정책을 모두 제공합니다. `optimal` 모드에서는 roll과 score 결정을 기대 최종점수 기준으로 exact하게 계산하고, 기본 focused 모드는 roll의 설명 가능한 목표 지향성을 유지하면서 score 단계에 exact value를 사용합니다.

## 7. 학습 모델은 왜 넣었나

Exact solver가 teacher가 되어 많은 상태에서 최적 keep을 label로 만든다. MLP는 그 행동을 빠르게 예측하도록 학습한다.

하지만 top-1 accuracy 98.52%에서도 최대 추가 EV 손실 10.15점인 rare hard case가 있었다. 그래서 다음 두 조건을 모두 통과할 때만 모델 후보를 채택한다.

1. model confidence \(\ge 0.95\)
2. exact objective gap \(\le 0.25\)

실패하면 exact solver로 fallback한다.

여기서 솔직해야 할 점이 있다. exact gap을 확인하는 현재 guard는 계산 절감 효과가 제한적이고, 모델 채택률도 46.96%다. 따라서 현재 성과는 “속도를 완전히 해결했다”가 아니라 **학습 모델의 위험을 측정하고 안전한 배치 구조를 검증했다**는 것이다.

## 8. Exact가 성립하는 가정과 한계

다음 조건 안에서 exact다.

- 주사위가 독립이고 각 면의 확률이 \(1/6\)이다.
- 구현한 Yacht 규칙과 점수 계산이 정확하다.
- 압축 상태가 미래 보상에 필요한 정보를 모두 포함한다.
- 목적함수는 기대 최종점수다.

다음은 exact가 보장하지 않는다.

- 실제 물리 주사위가 편향된 경우
- 규칙 구현 자체에 버그가 있는 경우
- 상대보다 이길 확률을 최대화하는 전략
- 사용자가 느끼는 재미나 설명 가능성
- 학습 모델이 새로운 모든 상태에서 안전하다는 일반화 보장

## 9. 면접 답변 세 가지 버전

### 10초 버전

> Exact solver는 가능한 keep과 이후 주사위 결과를 전부 확률 가중해 계산하고, 기대 최종점수가 가장 높은 행동을 고르는 알고리즘입니다.

### 30초 버전

> 예를 들어 주사위 세 개를 다시 굴리면 216개 결과가 있습니다. 각 결과의 확률과, 그 결과를 어느 점수 칸에 적었을 때의 남은 게임 가치를 계산하면 현재 keep 행동의 기대값을 구할 수 있습니다. 이를 모든 keep에 반복해 최댓값을 선택합니다. 반복 상태는 DP로 재사용하고, 점수판의 장기 가치는 52만여 개 상태를 오프라인에서 미리 계산한 table로 연결했습니다.

### 1분 버전

> 저는 Yacht를 상태, 행동, 확률 전이가 있는 순차적 의사결정 문제로 정의했습니다. Roll 단계에서는 현재 가능한 모든 고유 keep을 만들고, 각 keep 뒤에 나올 주사위 상태의 확률분포를 정확히 계산합니다. 다음 상태에서도 멈추거나 다시 굴리는 행동 중 가장 큰 값을 선택하는 Bellman recursion을 적용하고, 중복 상태는 DP cache로 재사용합니다. 턴이 끝날 때는 즉시 점수에 그 점수 칸을 닫은 뒤의 full-game value를 더합니다. 이 value는 closed mask, upper total, Yacht bonus 여부로 압축한 524,288개 상태를 종료 시점부터 backward induction으로 미리 계산했습니다. 그래서 `optimal` 모드에서는 이 규칙과 기대점수 목적함수 안에서 근사 없이 행동을 비교할 수 있습니다.

## 10. 화이트보드에 그릴 그림

면접관이 직접 설명해보라고 하면 아래 네 줄만 그린다.

```text
현재 상태 s
  ├─ keep A ─→ 가능한 주사위 결과들 ─→ best score + V(next)
  ├─ keep B ─→ 가능한 주사위 결과들 ─→ best score + V(next)
  └─ stop   ─→ best score + V(next)

각 가지: 확률 × 미래 가치
선택: 기대값이 가장 큰 행동
```

그 다음에 `V(next)`는 52만여 개 점수판 상태를 오프라인에서 거꾸로 계산한 표라고 설명한다.

## 11. 스스로 확인할 질문

아래 질문에 문서 없이 답할 수 있으면 기본 준비가 된 것이다.

1. 왜 `[2, 2] keep`의 가치를 단순 성공 확률 하나로 표현하면 부족한가?
2. reroll 3개의 216개 결과를 정렬해 합쳐도 왜 exact인가?
3. `V(next_state)`에는 무엇이 포함되어 있는가?
4. 왜 점수판 상태에서 upper total을 63까지만 저장해도 되는가?
5. `focused`, `value_score_only`, `value_optimal`의 차이는 무엇인가?
6. accuracy 98.52%인데도 guard가 필요한 이유는 무엇인가?
7. current guard가 속도를 완전히 해결했다고 말할 수 없는 이유는 무엇인가?
8. 기대점수 최적 정책이 멀티플레이 승률 최적 정책과 다른 이유는 무엇인가?

## 12. 절대 피할 표현

- “AI가 모든 경우의 수를 학습했습니다.”<br>→ 학습 모델과 exact enumeration을 혼동한 표현이다.
- “모델이 100% 안전합니다.”<br>→ validation split의 관측 결과를 일반화 보장으로 과장한 표현이다.
- “모든 모드가 완전 최적입니다.”<br>→ focused roll은 설명 가능한 목표 지향 정책이다.
- “경우의 수를 전부 매 요청마다 처음부터 계산합니다.”<br>→ full-game value는 오프라인 table, 반복 roll state는 cache를 사용한다.
- “Exact solver가 무조건 사람보다 잘합니다.”<br>→ 기대점수라는 특정 목적함수에서는 최적이지만, 재미·설명·상대 승률은 별도 목표다.
