# Performance Roadmap

현재 구조에서 성능을 가장 크게 좌우하는 부분은 프론트 프레임워크보다 `yacht_engine.py` 계산량과 멀티플레이 동기화 빈도입니다. 그래서 전체 JS 리라이트보다는 "측정 -> 병목 최적화 -> 점진 리팩토링" 순서가 더 안전하고 효과적입니다.

## 1. 어디를 먼저 측정할까

### A. AI 추천 응답 시간

가장 먼저 볼 지표는 `/api/recommend` 와 `yacht_engine.solve_best_move()` 입니다.

- 구분해서 측정할 항목
  - `focused` / `cover`
  - `rolls_left = 1` / `2`
  - 빈 점수판 / 후반 점수판
- 기록할 값
  - 평균 응답 시간
  - p95 응답 시간
  - 가장 느린 케이스의 주사위 패턴

현재 로컬 기준 대표 값은 `python3 scripts/benchmark_ai.py --repeats 3` 실행 시 대략 이렇습니다.

- `straight_upgrade_focused`: 평균 `16.81ms`
- `full_house_focus`: 평균 `784.11ms`
- `full_house_cover`: 평균 `888.43ms`
- `yacht_bonus_focused`: 평균 `773.31ms`
- `yacht_bonus_cover`: 평균 `870.49ms`

즉 현재 체감 병목은 프론트 렌더링이 아니라 `rolls_left=2` 인 exact DP 경로입니다.

### B. 멀티플레이 동기화 빈도

[templates/multi-game.html](../templates/multi-game.html) 에서는 현재 다음 주기로 통신합니다.

- visible polling: `1200ms`
- hidden polling: `4000ms`
- heartbeat: `8000ms`

여기서 볼 지표는 다음입니다.

- 플레이어 2명 + 관전자 1명일 때 분당 요청 수
- 평균 payload 크기
- 실패 재시도 횟수
- 탭이 숨겨졌을 때 불필요한 트래픽 비율

### C. 프론트 렌더 비용

지금 프론트는 템플릿 기반이라 프레임워크 오버헤드는 거의 없지만, 대신 전체 패널 재렌더가 잦을 수 있습니다.

- `updateScorecard()`
- `refreshInsightPanels()`
- `updateDice()`

이 세 함수가 한 턴에 몇 번 호출되는지부터 보는 게 좋습니다.

### D. 배포 서버 성능

현재 구조에선 앱 코드보다 Flask 개발 서버 자체가 먼저 한계에 닿을 수 있습니다.

- 동시 접속 수가 늘 때 응답 시간
- 1 worker 와 multi-worker 차이
- 재시작/복구 방식

## 2. 가장 효과 큰 성능 개선 5개

### 1. DP 내부 캐시를 더 공격적으로 재사용

가장 큰 효과가 예상됩니다.

- 주사위 상태는 정렬된 multiset 기준으로 캐시
- `rolls_left`, `strategy_mode`, 열린 카테고리 상태를 캐시 키에 포함
- 점수판 전체 대신 계산에 진짜 필요한 요약 상태만 분리

특히 `focused` 와 `cover` 가 같은 중간 확률 분포를 많이 공유하므로, 하위 계산 테이블을 분리하면 중복 계산을 줄일 수 있습니다.

### 2. 추천 결과 캐싱 계층 추가

같은 턴에서 UI가 다시 추천을 요청해도 결과를 재계산하지 않게 만드는 방식입니다.

- 키 후보
  - 정렬된 dice
  - kept 상태
  - `rolls_left`
  - `strategy_mode`
  - 열린 카테고리 요약

서버 메모리 캐시만으로도 체감 개선이 큽니다.

### 3. 멀티 polling을 SSE 또는 WebSocket 으로 축소

현재는 상태 변화가 없어도 주기적으로 polling 합니다. 멀티플레이 인원이 늘면 이쪽이 금방 더 비싸집니다.

- 1차 전환안: polling 유지 + interval 동적 확대
- 2차 전환안: SSE 로 방 상태 브로드캐스트
- 3차 전환안: WebSocket 으로 roll/sync/observe 통합

프론트를 프레임워크로 바꾸기 전에 이 단계가 훨씬 큰 효과를 냅니다.

### 4. Flask 개발 서버를 운영 서버로 교체

`gunicorn` 같은 WSGI 서버로 옮기면 코드 변경 없이도 안정성과 처리량이 좋아집니다.

- preload app
- worker 수 조정
- reverse proxy 와 함께 운용

이건 "리팩토링"보다 "배포 개선"에 가깝지만 체감 성능에는 매우 직접적입니다.

### 5. 템플릿은 유지하고 프론트 JS 만 모듈화

지금 단계에서 React/Vue 전체 이관은 비용이 큽니다. 대신 아래 정도가 적절합니다.

- `ai_panel.js`
- `game_state.js`
- `score_utils.js`
- multiplayer sync 로직

이렇게 모듈 경계를 정리하면 성능 측정도 쉬워지고, 나중에 Vite/TypeScript 로 옮길 때도 부담이 줄어듭니다.

## 3. 리라이트 없이 가는 점진 리팩토링 로드맵

### Phase 1. 측정 기반 정리

- `scripts/benchmark_ai.py` 로 AI 기준치 고정
- `/api/recommend` 서버 로그에 처리 시간 남기기
- 멀티 sync/heartbeat 요청 수 측정
- 큰 JS 함수 호출 빈도 체크

목표는 "느리다"를 감이 아니라 숫자로 바꾸는 것입니다.

### Phase 2. 엔진 최적화

- exact DP 하위 캐시 재사용
- score-stage 와 roll-stage 계산 경계 분리
- 결과 캐시 추가
- 느린 케이스 회귀 벤치 유지

여기까지가 현재 프로젝트에서 가장 큰 ROI 구간입니다.

### Phase 3. 네트워크/상태 전파 개선

- polling 주기 재조정
- observer / player 분리 전송
- SSE 또는 WebSocket 도입 검토

멀티플레이 체감은 이 단계에서 많이 좋아질 가능성이 큽니다.

### Phase 4. 프론트 구조 개선

- 템플릿 유지 + ES module 정리
- 필요하면 Vite 도입
- 필요하면 TypeScript 도입

이 단계는 "성능"보다는 유지보수성과 UI 확장성을 위한 투자입니다.

### Phase 5. 프레임워크 전환 여부 재판단

아래 조건이 모이면 그때 React/Vue/Svelte 를 검토하는 게 좋습니다.

- 화면 수가 더 늘어남
- 상태 동기화 버그가 반복됨
- UI 컴포넌트 재사용 요구가 커짐
- 멀티/관전/AI 패널이 계속 복잡해짐

반대로 지금은 Python 엔진과 멀티 통신 쪽이 더 큰 병목이므로, 전체 프론트 리라이트를 첫 번째 카드로 쓰는 건 추천하지 않습니다.

## 바로 다음 액션 추천

1. `scripts/benchmark_ai.py --repeats 10` 기준치 저장
2. `/api/recommend` 처리 시간 로깅 추가
3. 멀티 polling 요청 수 측정
4. DP 캐시 구조 정리
5. 이후에만 SSE/WebSocket 여부 판단
