# Yacht Game API

현재 작업 트리 기준 운영/프론트 연동용 API 문서입니다.

## Base

- Local: `http://127.0.0.1:8080`
- Production: Cloudflare 뒤 원본 도메인

모든 JSON API는 `Content-Type: application/json` 기준입니다.

```bash
BASE_URL="http://127.0.0.1:8080"
```

## Identity

현재 서버에는 `POST /api/login` 엔드포인트가 없습니다.

닉네임은 프론트에서 검증한 뒤 브라우저 `localStorage`에 저장하고, 각 API 요청에서 `username`을 함께 보냅니다.

## AI Recommendation

### `POST /api/recommend`

현재 주사위와 점수판을 기준으로 keep / reroll / score 추천을 반환합니다.

Request:

```json
{
  "dice": [1, 2, 3, 4, 6],
  "rolls_left": 1,
  "scorecard": [null, null, null, null, null, null, null, null, null, null, null, null],
  "strategy_mode": "focused"
}
```

Response:

```json
{
  "stage": "roll",
  "message": "[1, 2, 3, 4] Keep (Large Straight 업그레이드)",
  "keep_indices": [0, 1, 2, 3],
  "expected_value": 19.95,
  "strategy_mode": "focused",
  "primary_target": "Large Straight",
  "summary": "집중 공략 추천: Large Straight 16.67%, 실패해도 Small Straight 유지",
  "decision_report": {
    "title": "AI 결론 리포트",
    "conclusion": "집중 공략 추천: Large Straight 16.67%, 실패해도 Small Straight 유지",
    "decision": {
      "stage": "roll",
      "mode": "focused",
      "target": "Large Straight",
      "action": "[1, 2, 3, 4] Keep (Large Straight 업그레이드)",
      "expected_value": 19.95
    },
    "method": {
      "source": "exact",
      "label": "Exact solver",
      "confidence_text": "계산 확정",
      "note": "현재 Yacht 상태공간은 작아서 모든 합리적 keep 후보를 동적계획법으로 직접 비교할 수 있습니다."
    },
    "why": ["Large Straight 업그레이드 · 16.67%: Large Straight 16.7%를 노리되, 실패해도 Small Straight는 유지됩니다."],
    "tradeoffs": [],
    "learning_note": "이 결정에는 ML/DL 모델이 꼭 필요하지 않습니다. 지금 게임처럼 상태공간이 작으면 exact solver가 teacher 역할을 하며, 모델은 그 결정을 빠르게 근사하거나 상대/승률 같은 더 큰 맥락을 학습할 때 가치가 커집니다."
  },
  "dice_recommendations": [
    { "index": 0, "value": 1, "action": "keep", "confidence": 100 },
    { "index": 1, "value": 2, "action": "keep", "confidence": 100 },
    { "index": 2, "value": 3, "action": "keep", "confidence": 100 },
    { "index": 3, "value": 4, "action": "keep", "confidence": 100 },
    { "index": 4, "value": 6, "action": "reroll", "confidence": 100 }
  ],
  "breakdown": [
    {
      "name": "Large Straight 업그레이드",
      "type": "hand",
      "prob": 0.1667,
      "val_str": "16.67%",
      "keep_str": "[1, 2, 3, 4] keep → 실패해도 Small Straight 유지",
      "reason": "Large Straight 16.7%를 노리되, 실패해도 Small Straight는 유지됩니다.",
      "keep_indices": [0, 1, 2, 3]
    }
  ]
}
```

Notes:

- `strategy_mode`: `focused` 또는 `cover`
- 레거시 별칭 `safe`, `aggressive`는 서버에서 `focused`로 정규화됩니다.
- `scorecard`: 12칸 배열, 비어 있는 칸은 `null`
- `rolls_left = 0`이면 `stage = "score"`로 기록 추천을 반환하고, `keep_indices`는 빈 배열입니다.
- `decision_report`: AI 결론을 UI/로그에서 사람이 읽을 수 있게 만든 설명 객체입니다. exact solver 또는 학습 정책 모델 중 어떤 방식으로 결정했는지, confidence, 핵심 근거, 비교 포인트, ML/DL 모델의 역할 설명을 포함합니다.

Example:

```bash
curl -s "$BASE_URL/api/recommend" \
  -H "Content-Type: application/json" \
  -d '{
    "dice": [1, 2, 3, 4, 6],
    "rolls_left": 1,
    "scorecard": [null, null, null, null, null, null, null, null, null, null, null, null],
    "strategy_mode": "focused"
  }'
```

## Leaderboard

## Ranked Single Session

싱글 랭킹 저장용 서버 검증 세션입니다. 솔로/AI 코치 OFF 기록만 세션을 만들 수 있고, 서버가 roll과 score를 처리한 완료 세션만 `/api/leaderboard/single`에 저장할 수 있습니다.

### `POST /api/single/start`

Request:

```json
{
  "username": "Player01",
  "mode": "solo",
  "coach_enabled": false
}
```

Response:

```json
{
  "session_id": "ranked-session-id",
  "session_token": "ranked-session-token",
  "state": {
    "dice": [1, 1, 1, 1, 1],
    "kept": [0, 0, 0, 0, 0],
    "rolls_left": 3,
    "scorecard": [null, null, null, null, null, null, null, null, null, null, null, null],
    "finished": false,
    "final_score": null
  }
}
```

### `POST /api/single/roll`

Request:

```json
{
  "session_id": "ranked-session-id",
  "session_token": "ranked-session-token",
  "kept": [0, 1, 0, 0, 1]
}
```

Response:

```json
{
  "state": {
    "dice": [2, 1, 6, 4, 1],
    "kept": [0, 1, 0, 0, 1],
    "rolls_left": 2,
    "scorecard": [null, null, null, null, null, null, null, null, null, null, null, null],
    "finished": false,
    "final_score": null
  }
}
```

### `POST /api/single/score`

Request:

```json
{
  "session_id": "ranked-session-id",
  "session_token": "ranked-session-token",
  "category_idx": 6
}
```

Response:

```json
{
  "score": 14,
  "bonus": 0,
  "total_gain": 14,
  "state": {
    "dice": [1, 1, 1, 1, 1],
    "kept": [0, 0, 0, 0, 0],
    "rolls_left": 3,
    "scorecard": [null, null, null, null, null, null, 14, null, null, null, null, null],
    "finished": false,
    "final_score": null
  }
}
```

### `GET /api/leaderboard`

멀티 전적 리더보드 조회. 현재는 `/api/leaderboard/multi`와 같은 데이터를 반환합니다.

### `GET /api/leaderboard/multi`

로비에서 사용하는 멀티 전적 리더보드 조회 엔드포인트입니다.

### `GET /api/leaderboard/recent`

최근 저장된 경기 기록 조회.

Query:

- `limit` — 기본 `8`, 최대 `50`
- `username` — 넣으면 해당 유저가 포함된 경기만 필터

Example response:

```json
[
  {
    "player1": "alpha1",
    "score1": 190,
    "player2": "gamma34",
    "score2": 190,
    "winner": "DRAW",
    "timestamp": "2026-04-17T14:22:31.123456",
    "is_multiplayer": true,
    "margin": 0
  }
]
```

### `GET /api/leaderboard/single`

싱글 점수 리더보드 조회

### `GET /api/leaderboard/users/<username>`

특정 유저의 멀티 전적 요약 조회.

Query:

- `recent_limit` — 같이 내려주는 최근 경기 수, 기본 `5`, 최대 `10`

Example response:

```json
{
  "username": "alpha1",
  "rank": 1,
  "wins": 2,
  "draws": 1,
  "losses": 0,
  "games_played": 3,
  "total_score": 606,
  "avg_score": 202.0,
  "win_rate": 66.7,
  "last_played_at": "2026-04-17T14:22:31.123456",
  "current_streak": { "type": "draw", "count": 1 },
  "recent_form": ["D", "W", "W"],
  "recent_games": [
    {
      "username": "alpha1",
      "opponent": "gamma34",
      "score": 190,
      "opponent_score": 190,
      "result": "draw",
      "timestamp": "2026-04-17T14:22:31.123456"
    }
  ]
}
```

### `POST /api/leaderboard/single`

싱글 점수 저장. 서버는 솔로 모드이면서 AI 코치 OFF인 기록만 받습니다.

Request:

```json
{
  "username": "Player01",
  "score": 211,
  "mode": "solo",
  "coach_enabled": false,
  "session_id": "ranked-session-id",
  "session_token": "ranked-session-token"
}
```

Response:

```json
{
  "success": true
}
```

Example:

```bash
curl -s "$BASE_URL/api/leaderboard/single" \
  -H "Content-Type: application/json" \
  -d '{"username":"Player01","score":211,"mode":"solo","coach_enabled":false,"session_id":"ranked-session-id","session_token":"ranked-session-token"}'
```

### `POST /api/leaderboard/reset`

전체 기록 초기화. 관리자 토큰 필요.

Header:

```text
X-Admin-Token: <YACHT_ADMIN_TOKEN>
```

Response:

```json
{
  "status": "reset"
}
```

## Game Result

### `POST /api/save-game`

Deprecated. 멀티 게임 결과는 `/api/rooms/<code>/sync`에서 서버가 점수판 변경을 검증한 뒤 자동 저장합니다.

Response:

```json
{
  "error": "deprecated",
  "message": "멀티 결과는 방 상태 검증 후 서버에서 자동 저장됩니다."
}
```

## Lobby / Presence

### `POST /api/lobby-heartbeat`

로비 접속 유지 heartbeat

Request:

```json
{
  "client_id": "browser-tab-id",
  "username": "Player01"
}
```

Response:

```json
{
  "status": "ok",
  "active_clients": 3
}
```

### `GET /api/online-users`

대기중 / 게임중 유저 통합 목록 조회

Example response:

```json
[
  { "username": "Player01", "status": "대기중" },
  { "username": "Player02", "status": "게임중", "room": "AB12CD" }
]
```

### `GET /api/lobby-users`

구버전 호환성용 로비 heartbeat 목록

### `GET /api/system-status`

CPU, 메모리, 접속자 수, 활성 방 수, AI 캐시/지연 메트릭 조회

## Rooms

### `GET /api/rooms`

활성 방 목록 조회

Response:

```json
[
  {
    "code": "AB12CD",
    "host": "Host01",
    "players": ["Host01"],
    "status": "waiting",
    "room_phase": "waiting",
    "observer_count": 0
  }
]
```

### `POST /api/rooms`

방 생성

Request:

```json
{
  "username": "Host01"
}
```

Response:

```json
{
  "code": "AB12CD",
  "players": ["Host01"],
  "player_token": "secret-token"
}
```

### `POST /api/rooms/<code>/join`

방 입장

Request:

```json
{
  "username": "Guest01"
}
```

Response:

```json
{
  "code": "AB12CD",
  "players": ["Host01", "Guest01"],
  "state": {},
  "observers": [],
  "player_token": "secret-token"
}
```

### `POST /api/rooms/<code>/observe`

관전자 입장

Request:

```json
{
  "username": "Watcher01"
}
```

### `GET /api/rooms/<code>`

방 상태 조회

Query:

- `u`: 유저명
- `pt`: 플레이어 토큰
- `sv`: 마지막으로 본 state version. 같으면 `unchanged: true`와 최소 상태만 반환

Response:

```json
{
  "code": "AB12CD",
  "host": "Host01",
  "players": ["Host01", "Guest01"],
  "observers": ["Watcher01"],
  "observer_count": 1,
  "room_phase": "playing",
  "state": {
    "dice": [1, 1, 1, 1, 1],
    "kept": [0, 0, 0, 0, 0],
    "rolls_left": 3,
    "scores": {},
    "turn": "Host01",
    "game_over": false,
    "turn_left_seconds": 30
  },
  "player1": "Host01",
  "player2": "Guest01"
}
```

게임이 타임아웃 또는 퇴장으로 종료된 경우 `state`에 아래 필드가 추가될 수 있습니다.

- `winner`
- `loser`
- `end_reason`: `timeout`, `leave`, `system`

### `GET /api/rooms/<code>/events`

방 상태 변경을 SSE 형식으로 구독하는 PoC endpoint입니다. 기존 polling 클라이언트를 대체하기 전 점진 전환용으로 추가되었습니다.

Query:

- `sv`: 마지막으로 본 state version
- `once`: `1`이면 현재 상태 이벤트 1개만 반환하고 종료
- `interval_ms`: 변경 확인 간격. 서버에서 500~5000ms 범위로 제한

Response:

```text
event: room_state
id: 2
data: {"code":"AB12CD","room_phase":"playing","players":["Host01","Guest01"],"observer_count":1,"version":2,"turn":"Host01","game_over":false}
```

변경이 없을 때 장시간 연결에서는 `heartbeat` event가 전송될 수 있습니다.

### `POST /api/rooms/<code>/heartbeat`

가벼운 접속 유지용 heartbeat. 멀티 플레이어와 관전자 상태를 안정적으로 유지할 때 사용합니다.

Player Request:

```json
{
  "username": "Host01",
  "player_token": "secret-token"
}
```

Observer Request:

```json
{
  "username": "Watcher01"
}
```

Response:

```json
{
  "status": "ok",
  "room_phase": "playing",
  "observer_count": 1
}
```

### `POST /api/rooms/<code>/roll`

현재 턴 플레이어가 주사위를 굴립니다.

Request:

```json
{
  "username": "Host01",
  "player_token": "secret-token",
  "kept": [0, 1, 1, 0, 0]
}
```

Response:

```json
{
  "dice": [2, 3, 3, 5, 1],
  "rolls_left": 2,
  "state": {}
}
```

### `POST /api/rooms/<code>/rematch`

게임 종료 후 재대결 신청. 두 플레이어가 모두 동의하면 같은 방 상태가 새 경기로 리셋됩니다.

Request:

```json
{
  "username": "Host01",
  "player_token": "secret-token"
}
```

Waiting response:

```json
{
  "status": "waiting",
  "rematch_pending_players": ["Host01"],
  "rematch_waiting_for": ["Guest01"]
}
```

Started response:

```json
{
  "status": "started",
  "players": ["Host01", "Guest01"],
  "rematch_pending_players": [],
  "rematch_waiting_for": [],
  "state": {
    "turn": "Guest01",
    "game_over": false,
    "scores": {
      "Host01": [null, null, null, null, null, null, null, null, null, null, null, null],
      "Guest01": [null, null, null, null, null, null, null, null, null, null, null, null]
    }
  }
}
```

### `POST /api/rooms/<code>/sync`

턴 종료 또는 상태 동기화

Request:

```json
{
  "username": "Host01",
  "player_token": "secret-token",
  "dice": [2, 3, 3, 5, 1],
  "kept": [0, 1, 1, 0, 0],
  "rolls_left": 2,
  "scores": {
    "Host01": [null, null, 9, null, null, null, null, null, null, null, null, null]
  },
  "turn": "Guest01",
  "game_over": false
}
```

Response:

```json
{
  "state": {}
}
```

### `POST /api/rooms/<code>/leave`

방 이탈. 게임 도중 1:1에서 한 명이 나가면 남은 플레이어가 부전승 처리됩니다.

Request:

```json
{
  "username": "Guest01",
  "player_token": "secret-token"
}
```

Response:

```json
{
  "status": "left",
  "players": ["Host01"]
}
```

참고로 서버 구현은 `GET /api/rooms/<code>/leave`도 호환성 차원에서 허용합니다.

## Common Errors

### 잘못된 닉네임

```json
{
  "error": "닉네임은 2~12자(한글/영문/숫자/_)만 가능합니다"
}
```

### 플레이어 인증 실패

```json
{
  "error": "참가자 인증 실패"
}
```

### 상대 턴에 조작 시도

```json
{
  "error": "상대 턴"
}
```

## 운영 메모

- 플레이어 조작 API는 `player_token`이 필요합니다.
- `GET /api/rooms/<code>`에서 플레이어 presence 갱신 시 `pt` query 파라미터를 사용합니다.
- `GET /api/rooms/<code>/events`는 SSE PoC입니다. 현재 클라이언트 기본 경로는 polling이며, SSE는 점진 전환용으로 유지합니다.
- room backend는 방 단위 lock과 atomic create를 지원합니다. Redis 사용 시 `YACHT_ROOM_BACKEND=redis`, `YACHT_REDIS_URL`을 설정합니다.
- lobby/presence backend도 Redis로 분리할 수 있습니다. Redis 사용 시 `YACHT_PRESENCE_BACKEND=redis`를 설정합니다.
- 관전자는 `roll`/`sync`를 호출하면 `403`을 받습니다.
- 정적 파일은 장기 캐시, API 응답은 `no-store` 헤더를 사용합니다.
