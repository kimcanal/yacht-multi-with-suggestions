# API 호출 현황 보고서

- 작성일: 2026-04-07
- 조사 대상: `yacht_game` 현재 작업 트리
- 조사 목적: "내가 정리 작업을 하기 전에도 API 호출이 있었는가?"를 코드 기준으로 확인

참고:

- 이 문서는 최초 조사 시점의 스냅샷 성격이다.
- 같은 날짜 후속 안정화 작업으로 멀티 연결 유지를 위한 `POST /api/rooms/<code>/heartbeat` 경로와 관련 클라이언트 보강이 추가되었다.

## 1. 결론

현재 코드 기준으로 보면, API 호출은 정리 작업 전부터 이미 존재했다.

- 이번 정리 작업에서 변경한 것은 `.gitignore`, `README.md`, 캐시/로그/백업 파일 정리뿐이다.
- `server.py`, `templates/*.html`, `static/js/*.js`의 API 호출 로직은 이번 정리 과정에서 수정하지 않았다.
- 프론트엔드에는 총 18개의 `fetch(...)` 호출 지점이 있다.
- 추가로 멀티플레이 퇴장 처리에는 `navigator.sendBeacon(...)` 사용 경로도 있다.
- 현재 API 호출은 모두 `templates/*.html` 내부에 있으며, `static/js/*.js`에는 직접적인 API 호출이 없다.

## 2. 화면별 호출 현황

### 2-1. 로비 화면

파일: `templates/lobby.html`

| 호출 시점 | 메서드 | 엔드포인트 | 용도 |
| --- | --- | --- | --- |
| 방 생성 버튼 | `POST` | `/api/rooms` | 멀티 방 생성 |
| 방 코드 참가 | `POST` | `/api/rooms/<code>/join` | 멀티 방 참가 |
| 관전 버튼 | `POST` | `/api/rooms/<code>/observe` | 관전자 입장 |
| 접속자 목록 갱신 | `GET` | `/api/online-users` | 로비/게임중 유저 목록 조회 |
| 방 목록 갱신 | `GET` | `/api/rooms` | 활성 방 목록 조회 |
| 랭킹 탭 갱신 | `GET` | `/api/leaderboard/multi` 또는 `/api/leaderboard/single` | 멀티/싱글 리더보드 조회 |
| 시스템 상태 갱신 | `GET` | `/api/system-status` | CPU, 메모리, 활성 방 수 조회 |
| 로비 heartbeat | `POST` | `/api/lobby-heartbeat` | 로비 접속 유지 |

동작 특이사항:

- 로그인은 API 호출이 아니라 `localStorage`에 닉네임을 저장하는 방식이다.
- `startPolling()`에서 다음 주기로 반복 호출한다.
- `loadLobbyUsers`, `loadRoomList`, `loadSystemStatus`: 3초마다
- `sendHeartbeat`: 10초마다
- 싱글 시작은 `/game/single` 페이지 이동만 수행하며 별도 API 호출은 없다.

### 2-2. 싱글 게임 화면

파일: `templates/single-game.html`

| 호출 시점 | 메서드 | 엔드포인트 | 용도 |
| --- | --- | --- | --- |
| 게임 종료 후 랭킹 저장 | `POST` | `/api/leaderboard/single` | 싱글 점수 저장 |
| 주사위 굴린 뒤 AI 요청 | `POST` | `/api/recommend` | 추천/확률 분석 요청 |
| 게임 종료 후 결과 저장 | `POST` | `/api/save-game` | 결과 기록 저장 |

동작 특이사항:

- 싱글 모드는 서버 동기화 API를 사용하지 않는다.
- `pushState`, `fetchRoomState`, `startSyncPolling`는 빈 함수로 남아 있다.
- `askAI()`는 첫 굴림 이후(`rollsLeft < 3`)에만 호출된다.

### 2-3. 멀티 게임 화면

파일: `templates/multi-game.html`

| 호출 시점 | 메서드 | 엔드포인트 | 용도 |
| --- | --- | --- | --- |
| 관전자 모드 진입 시 | `POST` | `/api/rooms/<code>/observe` | 관전 등록 |
| 초기 진입 및 주기적 폴링 | `GET` | `/api/rooms/<code>?u=...&pt=...` | 방 상태 조회 |
| KEEP/턴/점수판 상태 반영 | `POST` | `/api/rooms/<code>/sync` | 클라이언트 상태 동기화 |
| 주사위 굴리기 | `POST` | `/api/rooms/<code>/roll` | 서버에서 실제 굴림 수행 |
| 내 턴 AI 요청 | `POST` | `/api/recommend` | 추천/확률 분석 요청 |
| 게임 종료 후 결과 저장 | `POST` | `/api/save-game` | 결과 기록 저장 |
| 방 나가기 | `POST` | `/api/rooms/<code>/leave` | 퇴장 및 부전승 처리 |

동작 특이사항:

- 멀티는 초기 진입 후 `fetchRoomState()`를 한 번 호출한 뒤, `startSyncPolling()`으로 1.2초마다 상태를 다시 가져온다.
- 플레이어는 `player_token`으로 인증되고, 관전자는 토큰 없이 조회한다.
- 퇴장 시에는 `navigator.sendBeacon(...)`을 우선 사용하고, 실패 시 `fetch(..., { keepalive: true })`로 폴백한다.

## 3. 서버 엔드포인트와 실제 사용 여부

파일: `server.py`

| 엔드포인트 | 서버 구현 | 현재 프론트 사용 | 비고 |
| --- | --- | --- | --- |
| `POST /api/lobby-heartbeat` | 있음 | 사용 중 | 로비 heartbeat |
| `GET /api/online-users` | 있음 | 사용 중 | 로비 접속자 목록 |
| `GET /api/lobby-users` | 있음 | 미사용 | 구버전 호환성용 |
| `GET /api/system-status` | 있음 | 사용 중 | 운영 상태 패널 |
| `POST /api/recommend` | 있음 | 사용 중 | 싱글/멀티 공용 |
| `GET /api/leaderboard` | 있음 | 미사용 | 사실상 멀티 리더보드 별칭 |
| `GET /api/leaderboard/single` | 있음 | 사용 중 | 싱글 랭킹 조회 |
| `POST /api/leaderboard/single` | 있음 | 사용 중 | 싱글 랭킹 저장 |
| `GET /api/leaderboard/multi` | 있음 | 사용 중 | 로비 멀티 랭킹 탭 |
| `POST /api/leaderboard/reset` | 있음 | 미사용 | 관리자용 |
| `POST /api/save-game` | 있음 | 사용 중 | 싱글/멀티 종료 저장 |
| `GET /api/rooms` | 있음 | 사용 중 | 방 목록 |
| `POST /api/rooms` | 있음 | 사용 중 | 방 생성 |
| `POST /api/rooms/<code>/join` | 있음 | 사용 중 | 방 참가 |
| `POST /api/rooms/<code>/observe` | 있음 | 사용 중 | 로비 관전, 멀티 재진입 |
| `GET /api/rooms/<code>` | 있음 | 사용 중 | 멀티 상태 조회 |
| `POST /api/rooms/<code>/sync` | 있음 | 사용 중 | 멀티 상태 동기화 |
| `POST /api/rooms/<code>/roll` | 있음 | 사용 중 | 멀티 주사위 굴림 |
| `POST /api/rooms/<code>/leave` | 있음 | 사용 중 | 멀티 방 이탈 |
| `GET /api/rooms/<code>/leave` | 있음 | 간접 사용 | 구현은 허용하지만 문서에는 주로 `POST`로 설명 |

## 4. 문서와 실제 구현의 차이

### 4-1. `POST /api/login`은 문서에만 있고 실제 구현은 없다

`API.md`에는 `POST /api/login`이 문서화되어 있지만, 현재 `server.py`에는 해당 라우트가 없다.

실제 로그인 동작은 아래와 같다.

- `templates/lobby.html`의 `submitLogin()`이 닉네임을 검사한다.
- 통과하면 `localStorage.setItem('yacht_username', name)`으로 브라우저 저장소에 저장한다.
- 즉, 현재 로그인은 서버 API 기반이 아니라 클라이언트 저장소 기반이다.

### 4-2. 멀티 리더보드 실제 호출 경로는 `/api/leaderboard/multi`다

문서에는 `GET /api/leaderboard`가 멀티 리더보드로 설명되어 있다.
하지만 현재 로비 화면은 실제로 `GET /api/leaderboard/multi`를 호출한다.

즉, 현재 프론트 기준의 실제 경로는 다음과 같다.

- 멀티 랭킹: `/api/leaderboard/multi`
- 싱글 랭킹: `/api/leaderboard/single`

### 4-3. `GET /api/lobby-users`는 현재 프론트에서 쓰지 않는다

`server.py`에는 기존 호환성 유지용으로 `GET /api/lobby-users`가 남아 있다.
하지만 현재 로비 화면은 이 엔드포인트 대신 `GET /api/online-users`를 사용한다.

### 4-4. 방 이탈은 구현상 `GET`, `POST` 모두 허용된다

문서에서는 `POST /api/rooms/<code>/leave` 중심으로 설명하지만, 실제 서버 구현은 `GET`, `POST`를 모두 받는다.
프론트에서는 주로 `sendBeacon` 또는 `fetch` 기반 퇴장 처리에 맞춰 사용된다.

## 5. 확인한 주요 코드 위치

### 프론트엔드 호출 위치

- `templates/lobby.html`: 방 생성/참가/관전, 접속자/방/랭킹/시스템 상태 조회, heartbeat
- `templates/single-game.html`: 싱글 랭킹 저장, AI 추천, 게임 결과 저장
- `templates/multi-game.html`: 방 상태 조회, 관전 등록, 상태 동기화, 주사위 굴림, AI 추천, 결과 저장, 퇴장

### 서버 구현 위치

- `server.py`: 모든 `/api/*` 라우트 구현

## 6. 최종 판단

질문에 대한 짧은 답은 다음과 같다.

- "내가 정리하기 전에는 API 호출이 없었나?" -> 아니다.
- 정리 이전에도 프론트엔드와 서버 사이의 API 호출은 이미 다수 존재했다.
- 이번에 정리하면서 API 호출이 새로 생긴 것은 아니다.
