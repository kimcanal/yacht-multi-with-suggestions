# Changelog

## AI 추천 흐름 — 어떻게 바뀌어 왔나

처음엔 족보별 성공 확률표를 미리 계산해두고 그 위에서 추천을 돌렸다. safe / aggressive 파라미터로 보정하긴 했지만 결국 "이 족보가 얼마나 될 것 같냐"를 보는 구조였고, 한계가 명확했다.

가장 크게 바뀐 건 turn DP 도입이었다. 남은 reroll을 고려해서 "지금 기록"과 "한 번 더 굴리기"를 같은 선택지로 비교하게 됐고, 이때 focused / cover 모드도 나눴다. cover는 여러 하단 족보 중 하나라도 성공할 확률(union probability)로 keep을 고른다.

그다음에는 score stage에 맥락을 더 붙였다. Upper Bonus 압박, Yacht Bonus 가치, 이 칸 지금 닫으면 남은 칸들의 기대치 변화까지 utility에 들어갔다. 지금은 이 exact solver 결과를 teacher로 삼아 MLP distillation 실험을 돌리는 중이다. confidence가 낮거나 exact 해와 차이가 크면 solver로 fallback하는 구조.

> 확률표 → exact DP → score-stage utility → distillation

---

## 릴리즈 히스토리

### 2026-04-17 — 서버 라우트 분리 + 문서 정합성 정리

`server.py`에 몰려 있던 설정/상태/라우트를 `config.py`, `app_state.py`, `routes/`, `utils/`로 나눴다. Flask app entry는 얇게 두고, 로비/AI/리더보드/방 로직을 blueprint 단위로 분리한 쪽.

같이 문서도 현재 동작 기준으로 맞췄다. `API.md`에서 사라진 `POST /api/login` 설명을 걷어내고, `focused` / `cover` 모드, `/api/leaderboard/multi`, room heartbeat, 현재 프로젝트 구조를 반영했다.

검증은 다시 돌렸다 — `py_compile`, Flask test client 스모크, golden check, soak warm/cold. 서버 분리 때문에 런타임 동작이 깨진 건 확인되지 않았다.

### 2026-04-12 — AI 패키지 분리 + ML prep

`yacht_engine.py` 하나에 다 들어 있던 걸 `yacht_ai/` 패키지로 분리했다. scoring, solver, advice, constants로 역할을 나눴고, golden check / soak / benchmark 스크립트도 이때 추가됐다. VDI 실험용 teacher data generator도 같이 들어갔다.

score-stage utility도 이 시기에 강화됐다 — fresh-turn EV, closing cost, upper bonus pressure, Yacht bonus 가치 반영. roll-stage MLP 학습/평가 스크립트랑 VDI hosting flow 정리도 같이 들어갔다.

### 2026-04-08 — AI 개편

AI 추천 설명을 확률표 중심에서 전략 모드(focused / cover) 중심으로 바꿨다. 소개 페이지랑 스크린샷도 이때 추가됐고, 성능 로드맵 문서도 올렸다.

### 2026-04-06 — 멀티플레이 안정화

멀티플레이 보안/presence 처리 강화하고, 프론트 공통 코드를 `ai_panel.js`, `dom_utils.js`, `game_state.js`, `score_utils.js`, `winprob.js`로 쪼갰다. 이전까지 한 파일에 다 몰려 있던 게 여기서 정리됐다.

### 2026-01-25 즈음 — 멀티 UX 정리

spectator 오류 잡고 로비 UI를 꽤 많이 뜯어고쳤다. 이 시기에 변경이 많았는데 커밋이 좀 지저분하게 쌓여 있어서 정확한 날짜는 애매하다.

### 2026-01-10 — 첫 커밋

Flask로 싱글/멀티 요트 게임 올렸다. 리더보드, 서버 상태 모니터링, 기본 AI 추천까지 같이 들어갔고, README에 "확률 계산 기반 AI"라고 써둔 게 이 시기다. 주사위 조합 점수 캐시랑 reroll outcome 열거 기반으로 추천 내놓는 구조였다.

싱글/멀티 템플릿 분리하면서 한동안 레이아웃 손보는 작업이 이어졌다. 반응형 주사위/점수판, 타이머, auto-roll, tooltip 같은 것들.
