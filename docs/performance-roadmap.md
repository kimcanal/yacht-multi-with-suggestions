# Performance Roadmap

현재 구조에서 성능을 가장 크게 좌우하는 건 프론트 프레임워크보다 `yacht_engine.py` 계산량과 멀티플레이 동기화 빈도다. 전체 JS 리라이트보다 "측정 → 병목 최적화 → 점진 리팩토링" 순서가 더 안전하고 효과적이다.

---

## 어디를 먼저 측정할까

### AI 추천 응답 시간

가장 먼저 볼 지표는 `/api/recommend`와 `yacht_engine.solve_best_move()`다.

구분해서 측정해야 할 항목은 `focused` / `cover`, `rolls_left = 1` / `2`, 빈 점수판 / 후반 점수판이다. 기록할 값은 평균 응답 시간, p95, 가장 느린 케이스의 주사위 패턴.

현재 로컬 기준 대표 값은 `python3 scripts/benchmark_ai.py --repeats 2` 실행 시 대략 이렇다.

- `straight_upgrade_focused`: 평균 16.22ms
- `full_house_focus`: 평균 910.96ms
- `full_house_cover`: 평균 1028.26ms
- `yacht_bonus_focused`: 평균 774.75ms
- `yacht_bonus_cover`: 평균 859.39ms

반면 `--warm-cache` 옵션으로 보면 동일 요청 재호출은 사실상 0.1ms 수준까지 내려간다. 즉 cold path는 exact DP, hot path는 결과 캐시 적중 여부가 핵심이다. 현재 체감 병목은 프론트 렌더링이 아니라 `rolls_left=2`인 exact DP 경로다.

### 멀티플레이 동기화 빈도

[templates/multi-game.html](../templates/multi-game.html)에서는 현재 다음 주기로 통신하고 있다.

- visible polling: 1200ms
- hidden polling: 4000ms
- heartbeat: 8000ms

여기서 볼 지표는 플레이어 2명 + 관전자 1명일 때 분당 요청 수, 평균 payload 크기, 실패 재시도 횟수, 탭이 숨겨졌을 때 불필요한 트래픽 비율이다.

현재 클라이언트는 SSE를 상태 변화 알림으로 우선 사용하고, 알림이 오면 `sv`를 포함한 인증 GET으로 최신 상태를 받는다. SSE가 끊기거나 탭이 숨겨지면 polling으로 자동 복귀한다. 변경 없는 경우에는 `unchanged` 최소 payload만 응답한다.

### 프론트 렌더 비용

지금 프론트는 템플릿 기반이라 프레임워크 오버헤드는 거의 없지만, 대신 전체 패널 재렌더가 잦을 수 있다. `updateScorecard()`, `refreshInsightPanels()`, `updateDice()` — 이 세 함수가 한 턴에 몇 번 호출되는지부터 보는 게 좋다.

### 배포 서버 성능

현재 구조에선 앱 코드보다 Flask 개발 서버 자체가 먼저 한계에 닿을 수 있다. 동시 접속 수가 늘 때 응답 시간, 1 worker와 multi-worker 차이, 재시작/복구 방식을 확인해야 한다.

---

## 효과 큰 성능 개선 5가지

**DP 내부 캐시를 더 공격적으로 재사용** — 가장 큰 효과가 예상된다. 주사위 상태는 정렬된 multiset 기준으로 캐시하고, `rolls_left`, `strategy_mode`, 열린 카테고리 상태를 캐시 키에 포함한다. 점수판 전체 대신 계산에 진짜 필요한 요약 상태만 분리하는 것도 중요하다. `focused`와 `cover`가 같은 중간 확률 분포를 많이 공유하므로, 하위 계산 테이블을 분리하면 중복 계산을 줄일 수 있다.

**추천 결과 캐싱 계층 추가** — 같은 턴에서 UI가 다시 추천을 요청해도 결과를 재계산하지 않게 만드는 방식이다. 키는 정렬된 dice, kept 상태, `rolls_left`, `strategy_mode`, 열린 카테고리 요약으로 구성한다. 서버 메모리 캐시만으로도 체감 개선이 크다.

**멀티 polling을 SSE 또는 WebSocket으로 축소** — 현재는 상태 변화가 없어도 주기적으로 polling한다. 멀티플레이 인원이 늘면 이쪽이 금방 더 비싸진다. 1차는 polling 유지하되 interval 동적 확대, 2차는 SSE로 방 상태 브로드캐스트, 3차는 WebSocket으로 roll/sync/observe 통합이다. 프론트를 프레임워크로 바꾸기 전에 이 단계가 훨씬 큰 효과를 낸다.

**Flask 개발 서버를 운영 서버로 교체** — gunicorn 같은 WSGI 서버로 옮기면 코드 변경 없이도 안정성과 처리량이 좋아진다. preload app, worker 수 조정, reverse proxy와 함께 운용. 리팩토링이라기보다 배포 개선에 가깝지만, 체감 성능에는 매우 직접적이다.

**템플릿 유지하고 프론트 JS만 모듈화** — 지금 단계에서 React/Vue 전체 이관은 비용이 크다. 대신 `ai_panel.js`, `game_state.js`, `score_utils.js`, multiplayer sync 로직 정도로 모듈 경계를 정리하면 성능 측정도 쉬워지고, 나중에 Vite/TypeScript로 옮길 때도 부담이 줄어든다.

---

## 점진 리팩토링 로드맵

**Phase 1. 측정 기반 정리**

`scripts/benchmark_ai.py`로 AI 기준치 고정하고, `/api/recommend` 서버 로그에 처리 시간 남기기, 멀티 sync/heartbeat 요청 수 측정, 큰 JS 함수 호출 빈도 체크. 목표는 "느리다"를 감이 아니라 숫자로 확인하는 것이다.

**Phase 2. 엔진 최적화**

exact DP 하위 캐시 재사용, score-stage와 roll-stage 계산 경계 분리, 결과 캐시 추가, 느린 케이스 회귀 벤치 유지. 여기까지가 현재 프로젝트에서 가장 큰 ROI 구간이다.

**Phase 3. 네트워크/상태 전파 개선**

polling 주기 재조정, observer / player 분리 전송, SSE 또는 WebSocket 도입 검토. 멀티플레이 체감은 이 단계에서 많이 좋아질 가능성이 크다.

**Phase 4. 프론트 구조 개선**

템플릿 유지 + ES module 정리, 필요하면 Vite 도입, 필요하면 TypeScript 도입. 이 단계는 "성능"보다는 유지보수성과 UI 확장성을 위한 투자다.

**Phase 5. 프레임워크 전환 여부 재판단**

아래 조건이 모이면 그때 React/Vue/Svelte를 검토하는 게 좋다. 화면 수가 더 늘어남, 상태 동기화 버그가 반복됨, UI 컴포넌트 재사용 요구가 커짐, 멀티/관전/AI 패널이 계속 복잡해짐. 지금은 Python 엔진과 멀티 통신 쪽이 더 큰 병목이라, 전체 프론트 리라이트를 첫 번째 카드로 꺼내는 건 순서가 맞지 않는다.

---

## 바로 다음 액션 추천

1. `scripts/benchmark_ai.py --repeats 10` 기준치 저장
2. `/api/recommend` 처리 시간 로깅 추가
3. 멀티 polling 요청 수 측정
4. DP 캐시 구조 정리
5. 이후에만 SSE/WebSocket 여부 판단
