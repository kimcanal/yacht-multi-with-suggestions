# Yacht Game

Flask 기반 웹 요트 다이스 게임입니다. 싱글플레이, 실시간 1:1 멀티플레이, 관전 모드, 리더보드, AI 추천 기능을 제공합니다.

라이브: https://app.yatch-game.cloud/

---

추가 문서들:
- API 상세: [API.md](./API.md)
- 변경 이력: [CHANGELOG.md](./CHANGELOG.md)
- 게임 소개 페이지: [`/intro`](https://app.yatch-game.cloud/intro)
- AI 수식 설명: [docs/ai-math.md](./docs/ai-math.md)
- 성능 계획: [docs/performance-roadmap.md](./docs/performance-roadmap.md)

## 실제 화면

현재 빌드 기준입니다. 규칙이랑 AI 추천 방식 설명은 [`/intro`](https://app.yatch-game.cloud/intro)에 있어요.

### 로비

<img src="./docs/screenshots/lobby.png" width="900" alt="Yacht lobby screenshot" />

### 게임 소개 페이지

<img src="./docs/screenshots/intro.png" width="900" alt="Yacht intro page screenshot" />

### 싱글플레이 + AI 추천 / VS AI

<img src="./docs/screenshots/single-cover.png" width="900" alt="Yacht single player AI recommendation screenshot" />

### 멀티 로비 + 대기실

<img src="./docs/screenshots/multi-live.png" width="900" alt="Yacht multiplayer lobby and waiting room screenshot" />

## 기능 목록

기본 플레이 쪽은 이렇습니다.

- 싱글: 솔로 챌린지, VS AI, AI 코치 ON/OFF 전환
- 멀티: 실시간 1:1 대전. 방 코드로 초대
- 관전: 멀티 경기 링크 공유 가능
- 리더보드: 싱글/멀티 기록 저장
- 싱글 랭킹 정책: 코치 OFF 솔로 기록만 메인 랭킹에 반영
- 최근 경기 히스토리: 로비에서 방금 끝난 대전 기록 확인 가능
- 플레이어 전적 스포트라이트: 멀티 리더보드에서 유저별 승률, 평균 점수, 최근 폼 확인
- 재대결: 게임 종료 후 두 플레이어가 모두 동의하면 같은 방에서 즉시 다음 판 시작
- 서버 상태 패널: CPU, RAM, 접속자 수, 활성 방 수
- 턴 타이머: 제한 시간 안에 행동 없으면 자동 roll

AI 추천 쪽은 이렇습니다.

- 현재 주사위, 남은 roll, 열린 점수칸을 보고 keep / reroll 추천
- 추천 패널 표시를 게임 중에 바로 ON/OFF 가능
- **집중 공략**: 가장 유망한 족보 하나를 끝까지 미는 추천. 지금 기록이 더 유리하면 그것도 같이 알려줌. Small Straight가 잡혀 있으면 Large Straight 업그레이드 가능성도 같이 봄
- **커버 플레이**: 하단 족보 여러 개 중 하나 이상 터질 확률(exact union)과 전부 실패할 확률을 같이 보여주는 추천
- Yacht Bonus 반영: 이미 Yacht 확보한 뒤 또 Yacht 나오면 +100 가치까지 추천에 반영
- 점수 기록 추천: 굴림 끝나면 희생 칸 포함해서 기록 우선순위도 제안
- VS AI: 같은 추천 엔진을 쓰는 `Yacht Bot`과 번갈아 12턴 대전

## AI 추천은 어떻게 동작하냐면

굴림 단계에서는 남은 roll 수랑 현재 점수판 상태를 같이 봅니다. 수식 정리는 [docs/ai-math.md](./docs/ai-math.md)에 있고, `/intro` 소개 페이지에서도 볼 수 있어요.

엔진은 한 턴 안의 reroll을 exact DP로 계산하고, 점수 기록 단계는 즉시 점수 + 장기 압력을 같이 반영한 utility로 처리합니다. 운영 환경에서는 이 exact 결과를 teacher로 써서 경량 MLP로 distillation하는 실험도 들어가 있어요. 학생 모델이 자신 없거나 exact 해와 차이가 크면 바로 fallback합니다.

**집중 공략**은 매번 "지금 기록"과 "한 번 더 굴리기"를 비교합니다. 지금 점수가 더 좋으면 기록 추천을 먼저 보여줘요. 가장 유망한 족보를 목표로 keep을 고르고, Small Straight가 잡혀 있으면 Large Straight 업그레이드 경로도 같이 확인합니다. 패널에는 추천 근거, 지금 멈추기 비교, 차선책 비교도 나옵니다.

**커버 플레이**는 4 of a Kind, Full House, Small Straight, Large Straight, Yacht 중 열린 하단 족보를 묶어서 하나 이상 성공할 확률을 최대화합니다. 전부 실패할 확률도 exact로 같이 보여줘요. 한 족보를 깊게 갈지 여러 족보를 열어둘지 판단할 때 유용합니다.

점수 기록 단계에서는 즉시 점수, Upper Bonus 흐름과 도달 확률 변화, Yacht Bonus 가치, 새 턴 기준 기대치, 이 칸 닫을 때 줄어드는 장기 부담을 같이 고려합니다. UI의 "장기 가치" 줄이 이걸 보여줍니다.

## 설치 및 실행

```bash
pip3 install -r requirements.txt
python3 server.py
```

기본은 `http://localhost:8080`에서 뜹니다.

운영 환경이라면 gunicorn 쓰세요.

```bash
gunicorn -c gunicorn.conf.py wsgi:application
```

AI 계산 기준치 측정:

```bash
python3 scripts/benchmark_ai.py --repeats 3
```

회귀/soak 검증:

```bash
python3 scripts/check_ai_golden.py
python3 scripts/soak_ai.py --cases 250
python3 scripts/verify_ai.py --benchmark-repeats 1 --warm-cases 120 --cold-cases 40
```

VDI에서 ML 실험용 teacher data 뽑을 때:

```bash
python3 scripts/generate_teacher_data.py --all-dice --contexts-per-dice 4 --output artifacts/teacher_data.jsonl --overwrite
```

roll stage MLP 학습:

```bash
python3 scripts/train_roll_policy.py \
  --data artifacts/teacher_data.jsonl \
  --output artifacts/roll_policy_model.json
```

학습 정책을 서버에서 켜려면 모델 경로를 환경 변수로 넘기면 됩니다. score stage는 exact 추천 그대로 쓰고, roll stage만 confidence 기준으로 학습 정책 우선 사용. confidence 낮거나 exact랑 차이 크면 자동 fallback합니다.

```bash
export YACHT_AI_POLICY_MODEL=artifacts/roll_policy_model.json
export YACHT_AI_POLICY_MIN_CONFIDENCE=0.95
python3 server.py
```

학습 품질 재점검할 때:

```bash
python3 scripts/eval_roll_policy.py \
  --data artifacts/teacher_roll_32768.jsonl \
  --model artifacts/roll_policy_model.json
```

희생 칸 장기 손실 재보정:

```bash
python3 scripts/estimate_closing_costs.py \
  --trials 12 \
  --workers 8 \
  --output artifacts/closing_costs_12.json
```

## 게임 규칙 요약

주사위 5개 굴려서 12개 카테고리에 한 번씩 기록하고 합계로 경쟁하는 게임입니다.

**Upper Section** — Ones~Sixes는 해당 숫자 합계. 63점 이상이면 Upper Bonus +35.

**Lower Section**
- Choice: 주사위 5개 총합
- 4 of a Kind: 같은 숫자 4개 이상일 때 총합
- Full House: 3개+2개 조합일 때 총합
- Small Straight: 연속 4개, 고정 15점
- Large Straight: 연속 5개, 고정 30점
- Yacht: 5개 동일, 고정 50점
- Yacht Bonus: Yacht 기록한 뒤 또 Yacht 나오면 다른 칸에 기록할 때 +100

## 기술 스택

- Backend: Python 3, Flask
- Frontend: HTML, CSS, JavaScript (프레임워크 없음)
- Game Engine: exact turn-DP + early-stop comparison + future-pressure heuristic
- Monitoring: psutil

## 주요 API 목록

- `POST /api/recommend` — AI 추천
- `GET /health` — 서버 상태
- `GET /api/online-users` — 로비/게임중 유저 목록
- `GET /api/system-status` — 운영 상태와 AI 메트릭
- `GET /api/rooms` — 방 목록
- `POST /api/rooms` — 방 생성
- `POST /api/rooms/<code>/join` — 방 입장
- `POST /api/rooms/<code>/observe` — 관전 입장
- `POST /api/rooms/<code>/heartbeat` — 방 참가자/관전자 heartbeat
- `POST /api/rooms/<code>/roll` — 주사위 굴리기
- `POST /api/rooms/<code>/rematch` — 게임 종료 후 재대결 동의 / 시작
- `POST /api/rooms/<code>/sync` — 상태 동기화
- `POST /api/rooms/<code>/leave` — 방 이탈 / 부전승
- `GET /api/leaderboard` — 멀티 리더보드 별칭
- `GET /api/leaderboard/multi` — 로비에서 쓰는 멀티 리더보드
- `GET /api/leaderboard/recent` — 최근 멀티 경기 기록
- `GET /api/leaderboard/single` — 싱글 리더보드
- `GET /api/leaderboard/users/<username>` — 특정 유저 멀티 전적 요약
- `POST /api/leaderboard/single` — 싱글 점수 저장

요청/응답 예시는 [API.md](./API.md) 참고.

## 프로젝트 구조

```
yacht_game/
├── API.md
├── README.md
├── app_state.py
├── config.py
├── database.py
├── docs/
│   ├── ai-math.md
│   ├── performance-roadmap.md
│   └── screenshots/
│       ├── intro.png
│       ├── lobby.png
│       ├── multi-live.png
│       └── single-cover.png
├── game_data.json
├── gunicorn.conf.py
├── requirements.txt
├── routes/
│   ├── ai.py
│   ├── leaderboard.py
│   ├── lobby.py
│   └── rooms.py
├── scripts/
│   ├── benchmark_ai.py
│   ├── check_ai_golden.py
│   ├── soak_ai.py
│   └── verify_ai.py
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
├── utils/
│   ├── ai_utils.py
│   ├── room_utils.py
│   └── validation.py
├── yacht-hosting.sh
├── yacht_ai/
│   ├── __init__.py
│   ├── advice.py
│   ├── constants.py
│   ├── scoring.py
│   └── solver.py
├── wsgi.py
└── yacht_engine.py
```

## 라이선스

MIT
