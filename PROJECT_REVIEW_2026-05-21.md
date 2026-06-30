# 프로젝트 리뷰 (2026-05-21)

## 현재 구조 요약
- Flask 단일 앱에서 Blueprint(`lobby`, `ai`, `leaderboard`, `rooms`)로 라우트 분리.
- AI 추천은 `/api/recommend`에서 policy model 우선 호출 후 exact solver fallback하며, `decision_report`로 결론/근거/학습 모델 역할을 사람이 읽을 수 있게 반환.
- 멀티플레이 room state는 `RoomStore`, 로비 presence는 `PresenceStore` 경계를 통해 접근하며, 기본 in-memory backend와 Redis backend feature flag를 지원.
- 동기화는 기존 polling + `sv` unchanged payload + 클라이언트 backoff를 사용하고, `/api/rooms/<code>/events` SSE PoC endpoint가 추가됨.
- 모든 응답에 `X-Request-ID`를 붙이고, AI slow log는 JSON 구조화 로그로 남김. OpenTelemetry OTLP exporter는 환경변수로 opt-in 가능.
- leaderboard/game result는 JSON 파일 저장소를 사용하며, atomic write와 schema normalization을 적용.
- 테스트는 `tests/test_routes.py`, `tests/test_stores.py`, `tests/test_database.py` 중심으로 라우트 흐름, AI validation, request id 전파, SSE one-shot event, store contract, database persistence를 검증.

## 강점
1. 엔진/라우트/유틸 책임 분리가 비교적 명확함.
2. AI 응답 헤더/슬로우 로그 등 운영 가시성이 이미 있음.
3. 멀티 동기화에서 `sv` unchanged payload, 실패 backoff, SSE PoC가 반영됨.

## 이번 반영 내용
1. `/api/recommend` 입력 검증 강화
   - JSON 객체가 아닌 요청은 400으로 응답.
   - `dice`, `kept`, `rolls_left`, `scorecard`에서 bool/소수/범위 밖 값을 차단.
   - scorecard는 카테고리별 가능한 점수 범위를 검증.

2. 멀티 동기화 polling 단기 개선
   - visible/hidden 기본 polling 간격 유지.
   - sync 실패가 누적되면 polling 간격을 최대 4배까지 backoff.
   - 탭 전환/온라인 복귀 시 polling timer가 중복 생성되지 않도록 generation guard 적용.

3. 테스트 범위 확장
   - AI validation 오류 케이스 추가: 잘못된 dice 길이, 비정상 scorecard, mode, rolls_left, bool/소수 dice, non-JSON body.
   - recommendation cache 테스트가 테스트 간 상태에 흔들리지 않도록 캐시 초기화.
   - `X-Request-ID` 전파 테스트 추가.

4. 관측성 보강
   - `utils/observability.py` 추가.
   - 요청마다 `X-Request-ID` 생성/전파.
   - AI slow recommend 로그를 사람이 읽는 문자열 대신 JSON 구조화 로그로 전환.

5. 상태 저장소 경계 도입
   - `utils/room_store.py` 추가.
   - `utils/presence_store.py` 추가.
   - `InMemoryRoomStore`를 기본 backend로 사용.
   - `InMemoryPresenceStore`를 기본 backend로 사용.
   - `YACHT_ROOM_BACKEND=redis`, `YACHT_REDIS_URL`로 Redis backend 선택 가능.
   - `YACHT_PRESENCE_BACKEND=redis`로 lobby/presence Redis backend 선택 가능.
   - room 단위 lock과 atomic create를 도입해 Redis backend의 lost update 위험을 줄임.
   - 라우트의 주요 room mutation 뒤 `save` 경계를 명시해 Redis backend에서도 상태가 저장되도록 정리.

6. SSE PoC 및 OpenTelemetry 옵션
   - `/api/rooms/<code>/events?once=1`로 현재 room state를 SSE 형식으로 받을 수 있음.
   - 일반 SSE 요청은 최대 25초 동안 version 변화와 heartbeat를 스트리밍.
   - `YACHT_OTEL_ENABLED=1`이면 Flask instrumentation + OTLP trace exporter 활성화.

7. 데이터 저장 안정성 개선
   - `database.py` 저장을 임시 파일 + `os.replace` 기반 atomic write로 변경.
   - 로드 시 users/games/single leaderboard schema를 정규화.
   - 점수 값을 0~1000 정수로 검증/정규화.
   - `YACHT_DATA_FILE`로 데이터 파일 경로를 분리 가능.
   - `/api/save-game`, `/api/leaderboard/single` 입력 검증을 강화.

8. AI 결론 리포트 추가
   - `/api/recommend` 응답에 `decision_report`를 추가해 결론, method, confidence, 핵심 근거, 비교 포인트를 구조화.
   - 싱글/멀티 AI 패널에서 결론 리포트와 학습 메모를 표시.
   - 작은 Yacht 상태공간에서는 exact solver가 teacher이고, ML/DL은 distillation/self-play/value model 확장에 쓰는 구조로 문서화.

## 우선 개선 제안

### 1) 상태 저장소 외부화 (우선순위: 매우 높음, 부분 완료)
`rooms`는 `RoomStore`, `lobby_clients`는 `PresenceStore` 경계와 Redis backend flag가 도입됨. 기본 실행은 여전히 in-memory이며, Redis backend는 실제 Redis 인스턴스와 배포 환경에서 검증 필요.

권장 접근:
- Redis staging smoke: 방 생성/참가/굴림/sync/leave/rematch 흐름을 실제 Redis로 검증.
- 다중 worker 환경에서 room 단위 lock의 timeout, 장애 복구, latency 영향을 측정.
- 더 높은 동시성이 필요하면 Redis transaction/Lua/CAS로 lock 범위를 줄이는 전략 검토.

### 2) `/api/recommend` 입력 검증 강화 (우선순위: 높음, 완료)
scorecard/dice/rolls_left/body validation을 명시화했고, invalid input은 400으로 반환.

### 3) 멀티 동기화 전송 계층 개선 (우선순위: 높음, 부분 완료)
단기 backoff와 SSE endpoint PoC는 적용 완료. 클라이언트는 아직 polling을 기본으로 사용하므로, 다음 단계는 SSE를 점진적으로 구독 경로에 붙이는 것.

### 4) 테스트 범위 확장 (우선순위: 중간, 부분 완료)
AI 입력 validation, request id, SSE one-shot event 테스트는 추가 완료. 다음 테스트 후보는 Redis backend contract test, 만료/forfeit/heartbeat edge case, 캐시 헤더 정책, 멀티 polling/SSE 클라이언트 회귀.

### 5) 관측성(OpenTelemetry/구조화 로그) 도입 (우선순위: 중간, 부분 완료)
request id, AI slow JSON log, optional OpenTelemetry OTLP exporter는 적용 완료. 추후 과제는 배포 환경에서 collector endpoint 연결, trace sampling, room/session attribute 표준화.

## 제안 실행 순서
1. Redis dependency 설치 및 실제 Redis backend smoke
2. 다중 worker 환경에서 room lock timeout/latency 측정
3. 멀티 클라이언트에 SSE 구독 경로 점진 적용, polling fallback 유지
4. 만료/forfeit/heartbeat, database corruption recovery, 실제 Redis backend contract 테스트 강화
5. OpenTelemetry collector 연결과 운영 dashboard 구성

## 검증 결과
- `python -m unittest tests.test_routes tests.test_stores tests.test_database`: 14 tests OK
- `python -m compileall routes yacht_ai tests database.py app_state.py server.py utils`: OK
- `node --check static/js/ai_panel.js`: OK
- `python scripts/check_ai_golden.py`: 7 cases OK
- 로컬 서버 smoke:
  - `/health`: 200, `room_backend: memory`, `presence_backend: memory`
  - 정상 `/api/recommend`: 200
  - 정상 `/api/recommend`: `decision_report.method.label=Exact solver`, `confidence_text=계산 확정`
  - 잘못된 dice 소수 입력: 400
  - `/api/save-game` 정상 입력: 200
  - `/api/save-game` 범위 밖 점수: 400
  - 방 생성/참가: 200
  - `/api/rooms/<code>/events?once=1`: `text/event-stream`, `Cache-Control: no-cache`, `room_phase: playing`
  - smoke는 `YACHT_DATA_FILE=/tmp/yacht_smoke_game_data.json`으로 분리 실행.
- Redis smoke:
  - 현재 로컬 환경에는 `redis-server`/`redis-cli` 및 `redis` Python package가 없어 실제 Redis backend smoke는 미실행.
  - `requirements.txt`에는 Redis dependency가 추가되어 있으므로, 배포/스테이징 환경에서 `pip install -r requirements.txt` 후 `YACHT_ROOM_BACKEND=redis`, `YACHT_PRESENCE_BACKEND=redis`, `YACHT_REDIS_URL`로 검증 필요.
