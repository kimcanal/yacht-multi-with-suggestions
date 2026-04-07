# Yacht Game API

간단한 운영 및 프론트 연동용 API 문서입니다.

## Base

- Local: `http://127.0.0.1:8080`
- Production: Cloudflare 뒤 원본 도메인

모든 JSON API는 `Content-Type: application/json` 기준입니다.

빠르게 테스트할 때는 아래처럼 `curl` 기준으로 확인할 수 있습니다.

```bash
BASE_URL="http://127.0.0.1:8080"
```

## Auth / Identity

### `POST /api/login`

브라우저 세션에 닉네임을 저장합니다.

Request:

```json
{
  "username": "Player01"
}
```

Response:

```json
{
  "status": "ok",
  "username": "Player01"
}
```

## AI Recommendation

### `POST /api/recommend`

현재 주사위와 점수판을 기준으로 추천을 반환합니다.

Request:

```json
{
  "dice": [3, 3, 3, 4, 1],
  "rolls_left": 2,
  "scorecard": [0, 0, null, null, null, null, 0, null, null, null, null, null],
  "strategy_mode": "safe"
}
```

Response:

```json
{
  "message": "[4, 3] Keep (Small Straight 노리기)",
  "keep_indices": [0, 3],
  "strategy_mode": "safe",
  "primary_target": "Small Straight",
  "summary": "안전형 추천: Small Straight 확률 36.11%",
  "dice_recommendations": [
    { "index": 0, "value": 3, "action": "keep", "confidence": 100 }
  ],
  "breakdown": [
    {
      "name": "Small Straight",
      "type": "hand",
      "prob": 0.3611,
      "val_str": "36.11%",
      "keep_str": "[4, 3] keep → 15점 (확정)",
      "reason": "균형 선택: Small Straight 성공 확률 36.1%",
      "keep_indices": [0, 3]
    }
  ]
}
```

Notes:

- `strategy_mode`: `safe` 또는 `aggressive`
- `scorecard`: 12칸 배열, 비어 있는 칸은 `null`

Example:

```bash
curl -s "$BASE_URL/api/recommend" \
  -H "Content-Type: application/json" \
  -d '{
    "dice": [3, 3, 3, 4, 1],
    "rolls_left": 2,
    "scorecard": [0, 0, null, null, null, null, 0, null, null, null, null, null],
    "strategy_mode": "safe"
  }'
```

## Leaderboard

### `GET /api/leaderboard`

멀티 전적 리더보드 조회

Example:

```bash
curl -s "$BASE_URL/api/leaderboard"
```

### `GET /api/leaderboard/single`

싱글 점수 리더보드 조회

Example:

```bash
curl -s "$BASE_URL/api/leaderboard/single"
```

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

Example:

```bash
curl -s "$BASE_URL/api/save-game" \
  -H "Content-Type: application/json" \
  -d '{
    "player1": "Player01",
    "score1": 211,
    "player2": "Player02",
    "score2": 183
  }'
```

## Lobby / Presence

### `POST /api/lobby-heartbeat`

로비 접속 유지 heartbeat

### `GET /api/online-users`

대기중 / 게임중 유저 통합 목록

### `GET /api/lobby-users`

대기실 heartbeat 기준 유저 목록

### `GET /api/system-status`

CPU, 메모리, 로비 접속자 수 등 운영 상태 조회

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

Example:

```bash
curl -s "$BASE_URL/api/rooms"
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

Example:

```bash
curl -s "$BASE_URL/api/rooms" \
  -H "Content-Type: application/json" \
  -d '{"username":"Host01"}'
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
  "player_token": "secret-token"
}
```

Example:

```bash
curl -s "$BASE_URL/api/rooms/AB12CD/join" \
  -H "Content-Type: application/json" \
  -d '{"username":"Guest01"}'
```

### `POST /api/rooms/<code>/observe`

관전자 입장

Request:

```json
{
  "username": "Watcher01"
}
```

Response:

```json
{
  "code": "AB12CD",
  "observers": ["Watcher01"],
  "players": ["Host01", "Guest01"],
  "state": {}
}
```

Example:

```bash
curl -s "$BASE_URL/api/rooms/AB12CD/observe" \
  -H "Content-Type: application/json" \
  -d '{"username":"Watcher01"}'
```

### `GET /api/rooms/<code>`

방 상태 조회

Query:

- `u`: 유저명
- `pt`: 플레이어 토큰

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

- `winner`: 승리 처리된 플레이어
- `loser`: 탈락하거나 연결이 끊긴 플레이어
- `end_reason`: `timeout`, `leave`, `score` 중 하나

Example:

```bash
curl -s "$BASE_URL/api/rooms/AB12CD?u=Host01&pt=secret-token"
```

Observer Example:

```bash
curl -s "$BASE_URL/api/rooms/AB12CD?u=Watcher01"
```

### `POST /api/rooms/<code>/heartbeat`

가벼운 접속 유지용 heartbeat. 멀티 플레이어/관전자 상태를 안정적으로 유지할 때 사용합니다.

Request:

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

Example:

```bash
curl -s "$BASE_URL/api/rooms/AB12CD/heartbeat" \
  -H "Content-Type: application/json" \
  -d '{"username":"Host01","player_token":"secret-token"}'
```

### `POST /api/rooms/<code>/roll`

현재 턴 플레이어가 주사위를 굴립니다.

Request:

```json
{
  "username": "Host01",
  "player_token": "secret-token",
  "kept": [false, true, true, false, false]
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

Example:

```bash
curl -s "$BASE_URL/api/rooms/AB12CD/roll" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "Host01",
    "player_token": "secret-token",
    "kept": [0, 1, 1, 0, 0]
  }'
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
  "game_over": false,
  "winner": null,
  "loser": null,
  "end_reason": null
}
```

Response:

```json
{
  "state": {}
}
```

Example:

```bash
curl -s "$BASE_URL/api/rooms/AB12CD/sync" \
  -H "Content-Type: application/json" \
  -d '{
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
  }'
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

Example:

```bash
curl -s "$BASE_URL/api/rooms/AB12CD/leave" \
  -H "Content-Type: application/json" \
  -d '{"username":"Guest01","player_token":"secret-token"}'
```

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
- `GET /api/rooms/<code>`에서 플레이어 heartbeat 갱신 시 `pt` query 파라미터를 사용합니다.
- 관전자는 `roll`/`sync`를 호출해도 `403`을 받습니다.
- `observer_count`, `room_phase`는 로비/관전 UI에서 바로 쓸 수 있게 포함되어 있습니다.
- 정적 파일은 버전 쿼리로 캐시를 갱신합니다.
