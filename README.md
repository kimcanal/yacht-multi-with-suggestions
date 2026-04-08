# Yacht Game

Flask 기반 웹 요트 다이스 게임입니다. 싱글플레이, 실시간 1 vs 1 멀티플레이, 관전 모드, 리더보드, 그리고 확률 기반 AI 추천 기능을 제공합니다.

라이브 서비스: https://app.yatch-game.cloud/

추가 문서:

- API 문서: [API.md](./API.md)
- 게임 소개 페이지: [`/intro`](https://app.yatch-game.cloud/intro)

## 실제 화면

현재 빌드 기준 실제 화면 캡처입니다. README에는 빠르게 훑어볼 수 있는 장면만 넣고, 규칙과 AI 추천 기준의 자세한 설명은 웹 소개 페이지 [`/intro`](https://app.yatch-game.cloud/intro) 에서 보는 구성을 권장합니다.

### 로비

<img src="./docs/screenshots/lobby.png" width="900" alt="Yacht lobby screenshot" />

### 게임 소개 페이지

<img src="./docs/screenshots/intro.png" width="900" alt="Yacht intro page screenshot" />

### 싱글플레이 + AI 추천

<img src="./docs/screenshots/single-cover.png" width="900" alt="Yacht single player AI recommendation screenshot" />

### 멀티플레이 실시간 경기

<img src="./docs/screenshots/multi-live.png" width="900" alt="Yacht multiplayer live match screenshot" />

위 화면처럼 README는 실제 플레이 장면을 미리 보여주고, 상세 게임 설명은 HTML 소개 페이지에서 이어서 확인하는 흐름으로 보는 것이 가장 자연스럽습니다.

## 주요 기능

- 싱글플레이: 브라우저에서 바로 플레이 가능
- 멀티플레이: 실시간 1 vs 1 대전
- 관전 모드: 멀티 경기 관전 링크 공유 가능
- 게임 소개 페이지: 규칙, 점수 방식, AI 추천 기준을 한 페이지에서 확인
- AI 추천: 현재 주사위, 남은 roll, 열린 점수칸 기준으로 keep / reroll 추천
- 추천 모드
  - `집중 공략`: 가장 유망한 한 족보를 끝까지 밀고, 가능한 업그레이드 경로도 함께 보는 추천
  - `커버 플레이`: 여러 하단 족보 중 하나 이상 성공할 exact union 확률과 전부 실패 확률을 같이 보여주는 추천
- Yacht Bonus 반영: 이미 Yacht를 확보한 뒤 다시 Yacht가 나오면 `+100` 가치까지 추천에 반영
- 점수 기록 추천: 굴림이 끝난 뒤 희생 칸까지 포함한 기록 우선순위 제안
- 리더보드: 싱글 / 멀티 결과 저장
- 서버 상태 패널: CPU, RAM, 접속자 수, 활성 방 수 표시
- 턴 타이머: 제한 시간 내 행동이 없으면 자동 roll 진행

## AI 추천 설명

굴림 단계에서는 남은 roll 수와 현재 점수판을 함께 고려합니다. 웹 UI에서는 버튼 아래 설명 카드와 동일한 기준으로 두 모드를 구분하고, 소개 페이지 `/intro` 에서도 같은 설명을 확인할 수 있습니다.

- `집중 공략`
  - 지금 손패에서 가장 유망한 한 족보를 목표로 두고 성공 확률이 가장 좋은 keep을 찾습니다.
  - 이미 `Small Straight`가 잡혀 있다면, 같은 keep으로 `Large Straight` 업그레이드를 노릴 수 있는지도 함께 봅니다.
- `커버 플레이`
  - `4 of a Kind`, `Full House`, `Small Straight`, `Large Straight`, `Yacht` 중 열린 하단 족보를 묶어서
    `하나 이상 성공할 확률`을 최대화합니다.
  - 함께 `전부 실패할 확률`도 exact 계산으로 보여줍니다.
  - 애매한 턴에서 "한 족보를 깊게 갈지, 여러 족보를 동시에 열어둘지" 판단할 때 특히 유용합니다.

점수 기록 단계에서는 이번 턴 즉시 점수, Upper Bonus 흐름, Yacht Bonus 가치, 희생 칸 우선순위를 같이 고려합니다.

## 설치 및 실행

```bash
pip3 install flask psutil
python3 server.py
```

기본 실행 주소는 `http://localhost:8080` 입니다.

## 게임 규칙 요약

주사위 5개를 굴려 12개 카테고리에 한 번씩 기록하고, 최종 합계를 경쟁합니다.

### Upper Section

- `Ones ~ Sixes`: 해당 숫자의 합
- Upper 합계가 `63점 이상`이면 `Upper Bonus +35`

### Lower Section

- `Choice`: 주사위 5개의 총합
- `4 of a Kind`: 같은 숫자 4개 이상일 때, 주사위 5개의 총합
- `Full House`: 같은 숫자 3개 + 2개일 때, 주사위 5개의 총합
- `Small Straight`: 연속된 숫자 4개 이상, 고정 `15점`
- `Large Straight`: 연속된 숫자 5개, 고정 `30점`
- `Yacht`: 같은 숫자 5개, 고정 `50점`
- `Yacht Bonus`: 이미 Yacht를 기록한 뒤 다시 Yacht가 나오면, 다른 칸에 0이 아닌 점수를 적을 때 추가 `+100점`

## 기술 스택

- Backend: Python 3, Flask
- Frontend: HTML, CSS, JavaScript
- Game Engine: Python exact turn-DP + score-stage heuristic
- Monitoring: psutil

## 주요 API

- `POST /api/recommend`: 현재 주사위 기준 AI 추천
- `GET /api/rooms`: 활성 방 목록
- `POST /api/rooms`: 방 생성
- `POST /api/rooms/<code>/join`: 방 입장
- `POST /api/rooms/<code>/observe`: 관전 입장
- `POST /api/rooms/<code>/roll`: 주사위 굴리기
- `POST /api/rooms/<code>/sync`: 상태 동기화
- `POST /api/rooms/<code>/leave`: 방 이탈 / 부전승 처리
- `GET /api/leaderboard`: 멀티 리더보드
- `GET /api/leaderboard/single`: 싱글 리더보드 조회
- `POST /api/leaderboard/single`: 싱글 리더보드 저장

자세한 요청 / 응답 예시는 [API.md](./API.md) 참고

## 프로젝트 구조

```text
yacht_game/
├── API.md
├── README.md
├── database.py
├── docs/
│   └── screenshots/
│       ├── intro.png
│       ├── lobby.png
│       ├── multi-live.png
│       └── single-cover.png
├── game_data.json
├── server.py
├── static/
│   ├── favicon.ico
│   └── js/
│       ├── ai_panel.js
│       ├── dom_utils.js
│       ├── game_state.js
│       ├── score_utils.js
│       ├── winprob.js
│       └── yacht_game.js
├── templates/
│   ├── intro.html
│   ├── lobby.html
│   ├── multi-game.html
│   └── single-game.html
└── yacht_engine.py
```

## 라이선스

MIT License
