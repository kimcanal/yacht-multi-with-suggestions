# 멀티플레이어 승률(P(win)) 모드 — v1 엔진 프로토타입

`yacht_ai/win_probability.py`의 `estimate_win_probability`는 두 플레이어의 점수판(및 진행 중인
턴의 dice/rolls_left)을 받아, **양쪽 다 EV-optimal 정책(`value_optimal`)으로 남은 게임을
플레이한다는 가정** 하에 Monte Carlo로 승/패/무 확률을 추정한다.

## 왜 exact 분포 테이블이 아니라 Monte Carlo인가

두 플레이어의 점수판은 서로 완전히 독립이므로(공유 자원도, 방해도 없음), 원래 계획은
"각 상태의 최종점수 **분포**"를 open12 테이블처럼 exact backward induction으로 미리
계산해두고, 두 분포를 컨볼루션해서 `P(내 최종점수 > 상대 최종점수)`를 정확히 구하는 것이었다.

이 접근은 이론적으로는 맞지만, 상태당 스칼라 하나(기대값)가 아니라 분포(벡터) 전체를
524,288개 상태 각각에 대해 전파해야 해서 계산량이 스칼라 버전(약 26분)보다 훨씬 크다.
설계가 맞는지 먼저 검증하지 않고 몇 시간짜리 오프라인 계산을 바로 미룰지 판단하기 위해,
**이미 검증된 `value_optimal` 정책을 그대로 재사용하는 Monte Carlo 버전을 먼저 만들어
정답에 가까운지, 쓸모가 있는지부터 확인**하는 쪽을 택했다.

## 검증 결과

- **비대칭 사례(monotonicity)**: 11칸 채우고 거의 다 끝난 쪽(banked 223점, Yacht만 남음) vs
  완전 초반 쪽 비교 → 앞선 쪽 win_rate 86.7% (`samples=15`). 상식과 일치.
- **대칭 사례(unbiasedness)**: 양쪽 다 빈 점수판으로 비교했을 때, 두 배치(`n=20`, `n=100`)의
  전체 240개 rollout 평균이 198.78점으로 이론적 exact EV(198.358)와 거의 일치. 개별 배치는
  win_rate 50.0%/61.0%로 흔들렸지만(표준오차 ~5~11pp), 이는 `n=100` 규모에서 기대되는 정상적인
  MC 노이즈이지 구조적 편향이 아니다.
- 유닛 테스트(`tests/test_win_probability.py`)는 1칸만 남은 빠른 케이스로 shape/monotonicity만
  확인한다(전체 스위트에 추가해도 <2초).

## 알려진 한계 — 프로덕션 투입 전 필요한 작업

**속도가 아직 안 나온다.** 빈 점수판 기준 1인분 풀게임 시뮬레이션이 약 **1.15초/rollout**
걸린다(`solve_best_move`를 턴마다 3번 정도, 12턴 호출). 승률 추정에 200~300 샘플이 필요하다면
한 번의 라이브 요청에 **6~7분**이 걸린다는 뜻이라, 지금 상태로는 API에 그대로 연결할 수 없다.

다음 중 하나(또는 조합)가 필요하다:

1. **`solve_best_move` fast-path**: 승률 시뮬레이션은 `keep_indices`/`primary_target`만 필요한데,
   지금은 매 호출마다 한국어 설명 문구·breakdown row·decision report까지 다 만든다. 이 구성
   비용을 건너뛰는 내부 전용 경로를 solver에 추가하면 호출당 비용이 유의미하게 줄 것이다.
2. **비동기/캐시 설계**: 요청-응답을 막지 않고 턴이 바뀔 때만 재계산 + 게임 상태 키로 캐싱.
3. **exact 분포 테이블**(원래 계획): 상태당 O(1) 조회로 바뀌므로 가장 빠르지만, 오프라인 빌드
   비용이 가장 크다. 위 MC 버전으로 설계 방향이 맞다는 확신이 선 뒤 투자할 옵션.

## 사용법

```python
from yacht_ai.win_probability import estimate_win_probability

result = estimate_win_probability(
    my_scorecard, opp_scorecard,
    my_dice=None, my_rolls_left=None,   # 진행 중인 턴이 있으면 채움
    opp_dice=None, opp_rolls_left=None,
    samples=300, seed=None,
)
# {"win_rate":..., "loss_rate":..., "tie_rate":..., "win_rate_stderr":...,
#  "my_avg_final":..., "opp_avg_final":...}
```

API/UI 연결은 이번 단계에 포함하지 않았다 — 위 속도 문제를 먼저 풀거나, 낮은 샘플 수(예: 30~50)로
CI가 넓은 대략치를 받아들일지부터 결정해야 한다.
