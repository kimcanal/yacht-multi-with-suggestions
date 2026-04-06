# Yacht Game API

간단한 운영 및 프론트 연동용 API 문서입니다.

## Base

- Local: `http://127.0.0.1:8080`
- Production: Cloudflare 뒤 원본 도메인

모든 JSON API는 `Content-Type: application/json` 기준입니다.

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

## Leaderboard

### `GET /api/leaderboard`

멀티 전적 리더보드 조회

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
    "status": "waiting"
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

Response:

```json
{
  "code": "AB12CD",
  "observers": ["Watcher01"],
  "players": ["Host01", "Guest01"],
  "state": {}
}
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

## 운영 메모

- 플레이어 조작 API는 `player_token`이 필요합니다.
- 관전자는 `roll`/`sync`를 호출해도 `403`을 받습니다.
- 정적 파일은 버전 쿼리로 캐시를 갱신합니다.
