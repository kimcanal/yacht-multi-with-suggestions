# Yacht Game

Flask 기반 웹 요트 다이스 게임입니다. 싱글플레이, 실시간 1:1 멀티플레이, 관전 모드, 리더보드, AI 추천 기능을 제공합니다.

라이브: https://app.yatch-game.cloud/

---

## AI/검증 하이라이트

- 한 턴 안의 keep/reroll은 exact tree/DP로 계산하고, 전체 12턴 장기 가치는 score-stage utility와 별도 simulation으로 검증합니다.
- Roll-policy v2는 teacher split 기준 top-1 98.5200%, teacher 대비 raw 평균 추가 EV 손실 0.023701점입니다.
- 모델 단독 사용은 safety override 뒤에도 exact보다 낮습니다. 100게임 기준 v2 model-only 평균은 exact 대비 -3.33점이었습니다.
- 서버 운영 방식은 confidence 0.95 + exact gap guard 0.25를 통과한 경우만 모델을 쓰고, 나머지는 exact solver로 fallback합니다.
- Runtime guard 포함 검증에서는 모델 채택률 46.9637%, 채택 구간 정확도 99.3827%, fallback 포함 추가 EV 손실 mean/max 0점을 확인했습니다.

추가 문서들:
- API 상세: [API.md](./API.md)
- 변경 이력: [CHANGELOG.md](./CHANGELOG.md)
- 게임 소개 페이지: [`/intro`](https://app.yatch-game.cloud/intro)
- AI 포트폴리오 요약: [docs/portfolio-ai-summary.md](./docs/portfolio-ai-summary.md)
- AI 수식 설명: [docs/ai-math.md](./docs/ai-math.md)
- AI 학습/리포트 로드맵: [docs/ai-learning-roadmap.md](./docs/ai-learning-roadmap.md)
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
- 싱글 랭킹 정책: 서버 발급 세션으로 진행한 코치 OFF 솔로 기록만 메인 랭킹에 반영
- 멀티 랭킹 정책: 서버가 현재 주사위/점수판으로 점수 기록을 재계산하고, 게임 완료 결과를 한 번만 저장
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
- AI 결론 리포트: 추천 결론, 계산 방식, confidence, 핵심 근거, 비교 포인트, 학습 모델이 필요한지에 대한 설명을 함께 표시
- VS AI: 같은 추천 엔진을 쓰는 `Yacht Bot`과 번갈아 12턴 대전

## AI 추천은 어떻게 동작하냐면

굴림 단계에서는 남은 roll 수랑 현재 점수판 상태를 같이 봅니다. 수식 정리는 [docs/ai-math.md](./docs/ai-math.md)에 있고, `/intro` 소개 페이지에서도 볼 수 있어요.

엔진은 한 턴 안의 reroll을 exact DP로 계산하고, 점수 기록 단계는 즉시 점수 + 장기 압력을 같이 반영한 utility로 처리합니다. 운영 환경에서는 이 exact 결과를 teacher로 써서 경량 MLP로 distillation하는 실험도 들어가 있어요. 학생 모델이 자신 없거나 exact 해와 차이가 크면 바로 fallback합니다.

작은 Yacht 상태공간에서는 ML/DL 모델이 반드시 필요하지 않습니다. exact solver가 이미 최선 후보를 직접 비교할 수 있고, 이 결과가 teacher 역할을 합니다. 모델은 이 결정을 빠르게 근사하거나 self-play, 상대 모델링, 승률/value model처럼 더 큰 맥락을 학습할 때 붙이는 쪽이 자연스럽습니다. `/api/recommend` 응답의 `decision_report`와 게임 안 AI 패널은 이 결론을 사람이 읽을 수 있게 보여줍니다.

**집중 공략**은 매번 "지금 기록"과 "한 번 더 굴리기"를 비교합니다. 지금 점수가 더 좋으면 기록 추천을 먼저 보여줘요. 가장 유망한 족보를 목표로 keep을 고르고, Small Straight가 잡혀 있으면 Large Straight 업그레이드 경로도 같이 확인합니다. 패널에는 추천 근거, 지금 멈추기 비교, 차선책 비교도 나옵니다.

**커버 플레이**는 4 of a Kind, Full House, Small Straight, Large Straight, Yacht 중 열린 하단 족보를 묶어서 하나 이상 성공할 확률을 최대화합니다. 전부 실패할 확률도 exact로 같이 보여줘요. 한 족보를 깊게 갈지 여러 족보를 열어둘지 판단할 때 유용합니다.

점수 기록 단계에서는 즉시 점수, Upper Bonus 흐름과 도달 확률 변화, Yacht Bonus 가치, 새 턴 기준 기대치, 이 칸 닫을 때 줄어드는 장기 부담을 같이 고려합니다. UI의 "장기 가치" 줄이 이걸 보여줍니다.

### AI가 추천할 때 실제로 보는 것

추천 엔진은 "이번에 몇 점을 먹을 수 있나"만 보지 않습니다. 현재 주사위, 남은 reroll 수, 열린 점수칸, 보너스 가능성, 실패했을 때 남는 선택지를 함께 봅니다.

- 현재 주사위와 남은 reroll 수: 첫 굴림 뒤에는 보통 두 번의 선택 기회가 남고, 마지막 reroll 전에는 한 번만 남습니다.
- 가능한 keep 조합 전체: 주사위 5개에서 나올 수 있는 keep 후보를 모두 비교합니다.
- 다음 주사위 결과 확률: keep한 뒤 나올 수 있는 모든 reroll 결과를 확률별로 합산합니다.
- 지금 기록 vs 더 굴리기: 이미 좋은 점수가 나오면 더 굴리는 선택보다 지금 적는 쪽을 추천할 수 있습니다.
- 열린 점수칸: Large Straight가 이미 닫혔는지, Sixes가 아직 열려 있는지 같은 점수판 상태에 따라 같은 주사위도 다르게 평가합니다.
- Upper Bonus: Ones~Sixes 합계 63점 보너스(+35)를 바로 확보하거나, 앞으로 확보할 확률이 올라가는 선택을 높게 봅니다.
- Yacht Bonus: Yacht 50점을 이미 확보한 뒤 다시 Yacht가 나오면 다른 칸에 적으며 +100을 얻는 선택을 강하게 반영합니다.
- 희생 칸 장기 손실: 망한 턴에는 앞으로 손실이 작은 칸을 먼저 비우도록 평가합니다.
- Choice 사용 타이밍: Choice는 낮은 점수에 너무 빨리 쓰면 손해라, 즉시 점수와 미래 기회를 같이 비교합니다.
- Focused / Cover 전략: Focused는 한 목표를 깊게 밀고, Cover는 여러 하단 족보 중 하나 이상 성공할 확률을 exact union으로 봅니다.

탐색 깊이는 남은 reroll 수를 넘지 않습니다.

```text
rolls_left = 2: keep 선택 -> reroll 결과 -> 다시 keep 선택 -> 마지막 reroll 결과 -> score 평가
rolls_left = 1: keep 선택 -> 마지막 reroll 결과 -> score 평가
rolls_left = 0: score 평가
```

그래서 한 턴 안의 keep/reroll은 exact tree/DP로 계산하지만, 전체 12턴 미래를 끝까지 완전 탐색하지는 않습니다. 점수 기록 단계는 즉시 점수, Upper/Yacht Bonus, 남은 칸의 future pressure를 섞은 평가 함수로 장기 가치를 근사합니다.

### AI 계산 검증

계산 로직은 아래 검증 스크립트로 회귀 확인합니다.

- `scripts/check_ai_golden.py`: 대표 상황의 기대 추천, EV, breakdown 순서를 고정해 회귀 검증
- `scripts/soak_ai.py`: 랜덤 상태에서 확률 범위, cover 성공/실패 보완 관계, 결정성 검증
- `scripts/verify_ai.py`: `py_compile`, golden, benchmark, warm/cold soak를 한 번에 실행

현재 작업 트리 기준 검증 결과:

- Golden cases 7개, 실패 0
- warm soak 120 cases, 실패 0
- cold soak 40 cases, 실패 0
- route/store/database unittest 16개 통과

검증으로 확인하는 대표 케이스는 Large Straight 업그레이드, Full House, Cover mode, Yacht Bonus cash-in, Upper Bonus 마감입니다. 특히 Cover mode는 "하나 이상 성공"과 "전부 실패" 확률이 0~1 범위에 있고 두 값이 서로 보완 관계를 유지하는지 계속 확인합니다.

### 12턴 value DP 실험

전체 게임을 더 정확히 보려면 점수판 상태별 남은 기대점수 `V(mask, upper_total, yacht_bonus)`를 오프라인으로 계산할 수 있습니다. 실험 스크립트는 [`scripts/build_value_table.py`](./scripts/build_value_table.py)에 있습니다.

```bash
python3 scripts/build_value_table.py \
  --open Fives,Sixes,Yacht \
  --upper-total 35 \
  --max-exact-open 3
```

상태는 닫힌 점수칸 bitmask, 63점으로 cap한 상단 합계, Yacht Bonus 가능 여부로 압축합니다. 후반 1~3칸 exact endgame은 이 Xeon 환경에서 빠르게 계산되지만, 4칸 exact도 약 30초 수준이라 전체 12턴 full DP를 운영 요청마다 직접 계산하는 방식은 맞지 않습니다. 다음 단계는 이 스크립트로 value table을 오프라인 샤딩/캐싱하고, score stage의 휴리스틱을 `즉시 점수 + V(next_state)`와 비교하는 실험입니다.

### Roll policy 모델 버전

roll-stage MLP는 exact solver가 만든 keep 선택을 빠르게 흉내 내는 distillation 모델입니다. 모델 파일은 날짜와 역할을 이름에 넣어서 `model-YYYYMMDD-roll-policy-vN.json` 형태로 구분합니다. 현재 최신 모델은 `v2`이고, `v1`은 비교용 baseline으로 남겨둡니다.

- 최신 모델: `artifacts/models/model-20260630-roll-policy-v2.json`
- 최신 평가 리포트: `artifacts/reports/model-20260630-roll-policy-v2.eval.json`
- baseline 모델: `artifacts/models/model-20260630-roll-policy-v1.json`
- teacher data: `artifacts/teacher_roll_32768.jsonl`
- 구조: input 41개 feature, hidden 96, keep-count class 462개
- v2 학습: 120 epochs, seed `20260701`, best epoch 107
- v2 held-out 평가: top-1 98.5200%, top-3 99.7559%
- v2 confidence 0.95 기준: coverage 96.4297%, covered accuracy 99.2880%
- v2 raw EV gap: teacher 대비 평균 추가 손실 0.023701점, p95 0점, max 10.145227점
- v2 runtime guard: confidence 0.95 + gap guard 0.25 적용 시 채택률 46.9637%, 채택 구간 정확도 99.3827%, fallback 포함 추가 EV 손실 0점
- full-game simulation(100 games, focused): exact 평균 152.21점, v2 runtime 평균 155.70점, v2 model-only 평균 148.88점
- v1 대비: top-1/coverage는 v1이 근소하게 높고, raw 평균 추가 EV 손실과 100게임 runtime 평균은 v2가 더 좋음

자세한 학습 설정과 해석은 [docs/model-20260630-roll-policy-v2.md](./docs/model-20260630-roll-policy-v2.md)와 [docs/model-20260630-roll-policy-v1.md](./docs/model-20260630-roll-policy-v1.md)에 정리했습니다.

이 모델은 score stage를 대신 판단하지 않습니다. 서버에서 켜면 roll stage에서만 먼저 제안하고, confidence가 낮거나 exact solver의 순수 objective guard와 차이가 크면 exact 추천으로 fallback합니다. 그래서 raw 모델 단독 worst-case는 존재하지만, 운영 안전성은 exact fallback이 계속 잡고, 모델은 빠른 근사와 실험용 비교 대상으로 둡니다.

## 설치 및 실행

```bash
pip3 install -r requirements.txt
python3 server.py
```

기본은 `http://localhost:8080`에서 뜹니다.

리더보드/게임 결과 JSON 파일 경로는 필요하면 바꿀 수 있습니다.

```bash
export YACHT_DATA_FILE=/path/to/game_data.json
```

운영 환경이라면 gunicorn 쓰세요.

```bash
gunicorn -c gunicorn.conf.py wsgi:application
```

멀티 room/presence 상태는 기본적으로 in-memory backend를 씁니다. Redis로 바꾸려면 아래 환경 변수를 설정합니다.

```bash
export YACHT_ROOM_BACKEND=redis
export YACHT_PRESENCE_BACKEND=redis
export YACHT_REDIS_URL=redis://localhost:6379/0
python3 server.py
```

room backend는 방 단위 lock과 atomic create를 사용해 다중 worker에서 같은 방을 동시에 갱신할 때의 lost update 위험을 줄입니다.
싱글 랭킹은 `/api/single/start`로 발급한 rankable session에서 서버가 roll/score를 처리한 완료 기록만 저장합니다.
멀티 점수 기록은 room sync 시점에 서버가 이전 주사위 상태로 재계산합니다. 공개 `/api/save-game` 직접 저장은 막고, 정상 종료/기권/타임아웃 결과만 서버에서 저장합니다.

OpenTelemetry trace exporter는 opt-in입니다. Collector endpoint는 표준 OTEL 환경 변수를 사용합니다.

```bash
export YACHT_OTEL_ENABLED=1
export OTEL_SERVICE_NAME=yacht-multi
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
python3 server.py
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

12턴 value DP 실험:

```bash
python3 scripts/build_value_table.py --open Fours,Fives,Sixes,Yacht --upper-total 30 --max-exact-open 4
```

VDI에서 ML 실험용 teacher data 뽑을 때:

```bash
python3 scripts/generate_teacher_data.py \
  --all-dice \
  --contexts-per-dice 4 \
  --stage roll \
  --mode both \
  --output artifacts/teacher_roll_20260630_1008_exact_teacher.jsonl \
  --overwrite
```

roll stage MLP 학습:

```bash
python3 scripts/train_roll_policy.py \
  --data artifacts/teacher_roll_32768.jsonl \
  --output artifacts/models/model-20260630-roll-policy-v2.json \
  --seed 20260701 \
  --model-id model-20260630-roll-policy-v2 \
  --created-date 2026-06-30
```

학습 정책을 서버에서 켜려면 모델 경로를 환경 변수로 넘기면 됩니다. score stage는 exact 추천 그대로 쓰고, roll stage만 confidence 기준으로 학습 정책 우선 사용. confidence 낮거나 exact랑 차이 크면 자동 fallback합니다.

```bash
export YACHT_AI_POLICY_MODEL=artifacts/models/model-20260630-roll-policy-v2.json
export YACHT_AI_POLICY_MIN_CONFIDENCE=0.95
python3 server.py
```

학습 품질 재점검할 때:

```bash
python3 scripts/eval_roll_policy.py \
  --data artifacts/teacher_roll_32768.jsonl \
  --model artifacts/models/model-20260630-roll-policy-v2.json \
  --seed 20260701 \
  --output artifacts/reports/model-20260630-roll-policy-v2.eval.json
```

teacher 일치율이 아니라 실제 추가 EV 손실을 볼 때:

```bash
python3 scripts/eval_roll_policy_ev_gap.py \
  --data artifacts/teacher_roll_32768.jsonl \
  --model artifacts/models/model-20260630-roll-policy-v2.json \
  --seed 20260701 \
  --output artifacts/reports/model-20260630-roll-policy-v2.ev-gap.json
```

서버 운영 방식처럼 confidence gate와 exact fallback guard까지 포함해 볼 때:

```bash
python3 scripts/eval_roll_policy_runtime.py \
  --data artifacts/teacher_roll_32768.jsonl \
  --model artifacts/models/model-20260630-roll-policy-v2.json \
  --seed 20260701 \
  --min-confidence 0.95 \
  --guard-gap 0.25 \
  --output artifacts/reports/model-20260630-roll-policy-v2.runtime.json
```

전체 게임 단위로 비교할 때:

```bash
python3 scripts/simulate_roll_policy_games.py \
  --games 100 \
  --seed 20260630 \
  --mode focused \
  --output artifacts/reports/roll-policy-full-game-focused-100.json
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
- `POST /api/single/start` — 싱글 랭킹용 서버 검증 세션 시작
- `POST /api/single/roll` — 싱글 랭킹 세션 주사위 굴림
- `POST /api/single/score` — 싱글 랭킹 세션 점수 기록
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
