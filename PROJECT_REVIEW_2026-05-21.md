# 프로젝트 리뷰 (2026-05-21)

## 현재 구조 요약
- Flask 단일 앱에서 Blueprint(`lobby`, `ai`, `leaderboard`, `rooms`)로 라우트 분리.
- AI 추천은 `/api/recommend`에서 policy model 우선 호출 후 exact solver fallback.
- 멀티플레이는 in-memory room state + polling 기반 동기화.
- 테스트는 `tests/test_routes.py` 중심으로 라우트 흐름 검증.

## 강점
1. 엔진/라우트/유틸 책임 분리가 비교적 명확함.
2. AI 응답 헤더/슬로우 로그 등 운영 가시성이 이미 있음.
3. 멀티 동기화에서 `sv` unchanged payload 최적화가 반영됨.

## 우선 개선 제안

### 1) 상태 저장소 외부화 (우선순위: 매우 높음)
현재 `rooms`, `lobby_clients`가 프로세스 메모리에 있어 다중 worker/재시작 시 상태 유실 위험이 큼. Redis 같은 외부 저장소로 이전 필요.

### 2) `/api/recommend` 입력 검증 강화 (우선순위: 높음)
현재 scorecard/dice의 길이·범위 검증이 약해 오류를 500으로 흘릴 가능성이 있음. 400 validation 응답을 명시적으로 반환하도록 표준화 권장.

### 3) 멀티 동기화 전송 계층 개선 (우선순위: 높음)
현재 polling 중심이므로 동시 접속 증가 시 비효율. 단기적으로 interval backoff, 중기적으로 SSE 전환, 장기적으로 WebSocket 통합 권장.

### 4) 테스트 범위 확장 (우선순위: 중간)
현재는 라우트 happy-path 비중이 높음. AI 입력 validation, 만료/forfeit/heartbeat edge case, 캐시 헤더 정책 회귀 테스트 추가 권장.

### 5) 관측성(OpenTelemetry/구조화 로그) 도입 (우선순위: 중간)
현재 print 기반 슬로우 로그를 JSON 구조화 로그로 전환하고 request id를 전파하면 장애 분석 속도 개선.

## 제안 실행 순서
1. Redis room backend 설계 + feature flag 이중화
2. API validation schema(Pydantic/Marshmallow 등) 도입
3. sync 채널 SSE PoC
4. 테스트/벤치 CI 파이프라인 강화
5. 관측성 스택 연동
