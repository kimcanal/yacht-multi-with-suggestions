---
marp: true
theme: default
paginate: true
math: mathjax
size: 16:9
style: |
  section {
    background: #0d1025;
    color: #f5f7ff;
    font-family: Pretendard, "Noto Sans KR", sans-serif;
    padding: 52px 64px;
  }
  h1, h2 { color: #29efd2; letter-spacing: -0.03em; }
  h1 { font-size: 46px; }
  h2 { font-size: 34px; }
  strong { color: #ffdc5e; }
  table { font-size: 21px; width: 100%; }
  th { background: #202747; color: #29efd2; }
  td { background: #151a33; }
  code { color: #29efd2; }
  blockquote {
    border-left: 6px solid #29efd2;
    background: #151a33;
    padding: 12px 20px;
  }
  .lead h1 { font-size: 50px; }
  .lead p { font-size: 25px; }
  .small { font-size: 18px; }
  .metric { font-size: 34px; color: #ffdc5e; font-weight: 800; }
  footer { color: #9ba4c7; }
footer: "Yacht AI · 대학원 면접 발표"
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "" -->

# Exact Solver를 기준선으로 활용한
# 안전한 학습 기반 Yacht 의사결정 시스템

**모델의 정답률이 아니라 실제 의사결정 손실을<br>
어떻게 측정하고 통제할 것인가?**

`[지원 분야]` · `[지원 대학원]` · `[이름]`

![bg right:42%](./screenshots/single-cover.png)

---

# 1. 순차적 의사결정 문제

한 게임은 **12턴**, 매 턴 두 결정을 반복한다.

1. **Roll decision** — 어떤 주사위를 유지할 것인가?
2. **Score decision** — 어느 점수 칸에 기록할 것인가?

\[
s=(\text{dice},\ \text{rolls left},\ \text{scorecard},\ \text{bonus state})
\]

\[
\pi^*=\arg\max_\pi \mathbb{E}[\text{final score}\mid s]
\]

> 지금 점수와 Upper Bonus·남은 점수 칸의 **장기 가치가 충돌**한다.

---

# 2. Exact Value를 기준선으로

> **Exact Solver** = 가능한 모든 행동과 확률 결과를 계산해<br>
> 기대값이 가장 높은 행동을 고르는 프로그램

\[
Q^*(s,a)=\mathbb{E}[r(s,a)+V^*(s')],
\qquad V^*(s)=\max_a Q^*(s,a)
\]

- 남은 reroll: 모든 keep와 주사위 결과를 **exact tree / DP**로 평가
- 점수 기록: 12개 점수 칸을 포함한 **precomputed value table**
- 이론적 시작 상태 기대점수: <span class="metric">약 198.36점</span>

\[
\operatorname{regret}(s,a)=Q^*(s,a^*)-Q^*(s,a)
\]

**주사위 운이 아니라 정책이 만든 행동 손실을 직접 측정**

---

# 3. 모델은 후보 생성기, Exact는 안전장치

## Exact teacher → MLP candidate → 2단계 guard → 추천

| ① 학습 | ② Confidence gate | ③ EV-gap gate | ④ 배치 |
| --- | --- | --- | --- |
| 32,768 states | \(p \ge 0.95\) | gap \(\le 0.25\) | model action |
| 41 features | 실패 시 exact | 실패 시 exact | 또는 fallback |
| 462 actions |  |  |  |

> **confidence와 가치 손실을 모두 통과한 경우에만 모델 행동 채택**

---

# 4. Accuracy보다 Decision Regret

| 연구 질문 | 지표 | 실험 |
| --- | --- | --- |
| 행동 일치율은? | Top-1 / Top-3 | held-out 6,554 states |
| 틀렸을 때 비용은? | **Decision regret** | exact \(Q^*\) 비교 |
| 실제 게임 영향은? | 평균 점수·보너스율 | paired simulation |
| 서비스 비용은? | cold / warm latency | 6 scenarios |

- 동일 seed로 정책 간 주사위 운 통제
- 평균 차이에 95% CI와 paired test 병기
- `optimal` 정책의 regret = 0으로 평가기 정합성 확인

---

# 5. 장기 가치를 쓰자 평균 +9.04점

| 정책 | 평균 점수 | Upper Bonus | vs heuristic 승률 |
| --- | ---: | ---: | ---: |
| Heuristic | 175.52 | 42% | — |
| **Exact score value** | **184.56** | **54%** | **58.5%** |

<span class="metric">+9.04점</span> · 95% CI **[+3.43, +14.65]** · \(p=0.00159\)

| 정책 | Regret / game | Roll match | Score match |
| --- | ---: | ---: | ---: |
| Focused heuristic | 19.49 | 70.09% | 81.0% |
| **Exact score value** | **10.39** | 70.11% | **100%** |

**Roll은 유지하고 score-stage 손실만 0으로 제거**

---

# 6. 98% 정확도도 안전하지 않았다

| 배치 방식 | 채택 범위 | 정확도 | 추가 EV 손실 |
| --- | ---: | ---: | ---: |
| Raw model-only | 100% | Top-1 **98.52%** | 평균 0.0237 · **최대 10.15** |
| **Guarded runtime** | **46.96%** | 채택 구간 **99.38%** | 검증 split 평균·최대 **0** |

- mismatch **97 / 6,554**
- EV gap `> 0.25`: **51 cases**
- hard case: 완성된 강한 패에서 일부만 keep

> 평균 정확도보다 **rare worst-case와 fallback 비율**이 중요했다.

---

# 7. 결론과 다음 연구

1. Exact solver로 **학습·평가 기준선**을 만들었다.
2. Accuracy를 **decision regret**으로 확장했다.
3. Confidence + EV guard + fallback으로 위험을 통제했다.

### 현재 한계

- 200게임·고정 seed → 더 큰 표본과 복수 seed 필요
- 검증 split의 gap 0은 일반화 보장이 아님
- 모델 채택률 46.96% → 계산 절감 효과 제한
- 기대점수와 멀티플레이 승률은 다른 목적함수

> **정확성을 유지하면서 exact 검증 비용과 fallback을 함께 줄일 수 있는가?**

`Selective prediction` · `Uncertainty calibration` · `Offline RL / self-play`

---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "" -->

# 감사합니다

## Questions & Discussion

**연구 확장:** risk–coverage 최적화 · distribution-aware win policy

---

<!-- _header: "APPENDIX" -->

# A1. 전체 정책 기준선

200 paired games · indexed random source · seed `20260708`

| 정책 | 평균 점수 | vs heuristic | 승률 | Upper Bonus |
| --- | ---: | ---: | ---: | ---: |
| Heuristic | 168.195 | — | — | 23.5% |
| Exact score value | 182.600 | +14.405 | 63.0% | 43.0% |
| **Full value-optimal** | **198.645** | **+30.450** | **77.5%** | **66.0%** |

<span class="small">본문의 score-stage 실험은 stream random source, 이 표는 indexed random source다. 서로 다른 실험의 절대 평균을 직접 비교하지 않는다.</span>

---

<!-- _header: "APPENDIX" -->

# A2. 모델·검증 설정

| 항목 | 값 |
| --- | --- |
| Dataset | exact teacher states 32,768개 |
| Split | train 26,214 / validation 6,554 |
| MLP | input 41 / hidden 96 / output 462 |
| Training | 120 epochs / best epoch 107 |
| Runtime guard | confidence 0.95 / EV gap 0.25 |

**재현성:** seed · split · model metadata · simulation report를 JSON으로 보관

---

<!-- _header: "APPENDIX" -->

# A3. 구현 신뢰성

| 검증 | 결과 |
| --- | ---: |
| Python tests | **74 passed** |
| Golden scenarios | **7 passed** |
| Warm / cold soak | **120 / 40 passed** |
| Exact value cold | **58.5–140.2 ms** |
| Cache warm | **0.042–0.054 ms** |

Ruff lint · Python compile · frontend JavaScript syntax 검사 통과
