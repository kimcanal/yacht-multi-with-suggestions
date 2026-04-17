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

### `GET /api/leaderboard`

멀티 전적 리더보드 조회. 현재는 `/api/leaderboard/multi`와 같은 데이터를 반환합니다.

### `GET /api/leaderboard/multi`

로비에서 사용하는 멀티 전적 리더보드 조회 엔드포인트입니다.

### `GET /api/leaderboard/single`

싱글 점수 리더보드 조회

### `POST /api/leaderboard/single`

싱글 점수 저장

Request:

```json
{
  "username": "Player01",
  "score": 211
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
  -d '{"username":"Player01","score":211}'
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

게임 종료 결과 저장

Request:

```json
{
  "player1": "Player01",
  "score1": 211,
  "player2": "Player02",
  "score2": 183
}
```

Response:

```json
{
  "status": "success"
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
- 관전자는 `roll`/`sync`를 호출하면 `403`을 받습니다.
- 정적 파일은 장기 캐시, API 응답은 `no-store` 헤더를 사용합니다.
