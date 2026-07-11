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

## API/UI 연결 (2026-07-11)

`POST /api/win-probability`와 멀티 판세 패널에 연결했다. 요청 스레드는 시뮬레이션을 기다리지 않고 `202 pending`을 반환하며, 백그라운드 worker가 상태별 계산을 한 번만 수행한다. 같은 body를 다시 요청하면 완료된 캐시를 `200 ready`로 반환한다.

- 점수판 예상 최종점수는 open12 exact value table로 즉시 표시한다.
- UI는 30샘플 빠른 추정을 먼저 보여주고 같은 상태를 100샘플 정밀 추정으로 자동 교체하며, 두 단계 모두 95% 표본 오차를 표시한다.
- 캐시는 기본 10분, 최대 64개 상태를 유지한다.
- 환경변수: `YACHT_WIN_PROBABILITY_WORKERS`, `YACHT_WIN_PROBABILITY_SAMPLES`, `YACHT_WIN_PROBABILITY_CACHE_MAX`, `YACHT_WIN_PROBABILITY_CACHE_TTL`.

## 알려진 한계

**속도는 크게 개선됐지만, 동기 API에 바로 붙이기에는 아직 무겁다.** 초기 구현은 빈 점수판 기준
1인분 풀게임 시뮬레이션이 약 **1.17초/rollout** 걸렸다. solver fast-path(`explain=False`)와
value-optimal 전이 캐시를 넣은 뒤, 같은 조건의 `samples=20, seed=1` 측정은 **46.87초 → 2.86초**로
줄었다. 1인분 풀게임 기준으로는 약 **0.072초/rollout**이고, 300샘플 요청은 단순 환산 시
약 **43초** 수준이다.

이번 최적화는 `keep_indices`/`primary_target`만 필요한 승률 시뮬레이션에서 한국어 설명 문구,
breakdown row, decision report 조립을 건너뛰고, 같은 점수판 상태에서 반복되는 exact DP 전이 합산을
LRU 캐시로 재사용한다.

다음 고도화 후보:

1. **점진적 샘플 누적**: 30~50샘플의 넓은 CI를 먼저 보여주고, 백그라운드에서
   샘플을 누적해 점진적으로 좁힐지 결정.
2. **exact 분포 테이블**(원래 계획): 상태당 O(1) 조회로 바뀌므로 가장 빠르지만, 오프라인 빌드
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

제품 UI의 승률은 정확한 확률표가 아니라 표본 기반 전망이므로, 항상 샘플 수와 오차 폭을 함께 표시한다.
