# Changelog

## AI 추천 흐름 — 어떻게 바뀌어 왔나

처음엔 족보별 성공 확률표를 미리 계산해두고 그 위에서 추천을 돌렸다. safe / aggressive 파라미터로 보정하긴 했지만 결국 "이 족보가 얼마나 될 것 같냐"를 보는 구조였고, 한계가 명확했다.

가장 크게 바뀐 건 turn DP 도입이었다. 남은 reroll을 고려해서 "지금 기록"과 "한 번 더 굴리기"를 같은 선택지로 비교하게 됐고, 이때 focused / cover 모드도 나눴다. cover는 여러 하단 족보 중 하나라도 성공할 확률(union probability)로 keep을 고른다.

그다음에는 score stage에 맥락을 더 붙였다. Upper Bonus 압박, Yacht Bonus 가치, 이 칸 지금 닫으면 남은 칸들의 기대치 변화까지 utility에 들어갔다. 지금은 이 exact solver 결과를 teacher로 삼아 MLP distillation 실험을 돌리는 중이다. confidence가 낮거나 exact 해와 차이가 크면 solver로 fallback하는 구조.

> 확률표 → exact DP → score-stage utility → distillation

---

## 릴리즈 히스토리

### 2026-10-12 — 멀티플레이 polling 경로 최적화, LICENSE 추가, 캐시 안전성 수정

서버 권한 라우트의 쓰기 비용을 줄였다. 플레이어/관전자 하트비트는 방 전체를 매 요청 다시 쓰던 것에서, 구조적 변경(강제퇴장·턴 만료·상태 동기화)은 그대로 즉시 저장하고, 하트비트만 `YACHT_ROOM_PRESENCE_SAVE_INTERVAL`(기본 10초) 주기로 저장하며 그 사이에는 Redis TTL만 갱신한다. in-memory 백엔드는 프로세스 내 상태가 살아있으므로 의미가 같다. 유휴 강제퇴장은 최대 `PLAYER_ROOM_TIMEOUT` + 이 간격 뒤에 발생한다.

Redis room/presence store의 `items()`를 키별 GET(N+1)에서 배치 `mget`으로 바꿨고, `touch()`로 TTL만 갱신하는 경로를 추가했다. JSON 결과 저장소는 정규화된 데이터를 프로세스 내에서 캐시하고(파일 경로+mtime으로 외부 작성 무효화), 저장 시 중복 정규화를 건너뛴다. SSE 슬롯 기본값이 `GUNICORN_THREADS`에서 자동 조정된다(스레드 하나가 스트림 하나를 잡고 있으므로 슬롯은 스레드 예산 아래로 유지된다).

`/api/recommend` 웜 경로도 함께 줄였다. 캐시 히트 시 deepcopy를 얕은 복사로 대체(~80µs)하고, 캐시 키에 이미 포함된 입력으로 만든 `decision_report` 재계산을 건너뛴다(~10µs). `/api/recommend`의 catch-all 핸들러가 내부 예외 메시지(`str(e)`)를 그대로 클라이언트에 노출하던 것도 고쳐서, 이제 서버 로그에만 기록하고 클라이언트에는 `internal_error`만 돌려준다.

이 배치는 코드 리뷰로 한 번 더 검증했고, 그 과정에서 자체 점검 목록에 없던 버그 3개를 찾아 함께 고쳤다: JSON 결과 저장소가 쓰기 실패 시 캐시를 직접 mutate해서, 실패한 쓰기가 다음에 성공하는 무관한 쓰기에 묻어 디스크에 영구 반영될 수 있었던 문제(이제 성공 후에만 캐시를 교체), `RedisPresenceStore.items()`가 같은 diff의 `RedisRoomStore`와 달리 배치 없이 통짜 `mget`을 쓰던 불일치, `GUNICORN_THREADS`에 잘못된 값이 들어오면 SSE 설정을 건드리지 않은 운영자의 앱도 기동 시점에 죽던 문제(방어적 파싱으로 교체).

README에 MIT `LICENSE` 파일을 추가하고 링크했으며, 문서 몇 곳의 오래된 상호참조와 시나리오 불일치도 정리했다.

### 2026-10-08 — Redis 실환경 검증, 멀티 UI 버그 수정, roll-stage 개선

Redis room/presence/session backend를 실제 Redis 인스턴스와 gunicorn 멀티 worker로 돌려 검증했다. 그 과정에서 `RedisSingleSessionStore`의 global lock 키가 세션 데이터와 같은 prefix를 써서, lock을 쥔 채로 `clear()`를 호출하면 lock 키 자체가 지워지는 버그를 발견해 lock을 별도 `-lock:` 네임스페이스로 분리했다.

멀티플레이 UI에서 세 가지를 고쳤다. 재대결 신청은 `state.version`을 올리지 않아 SSE 경로에서 상대방이 신청 사실을 전혀 알 수 없었던 문제(별도의 rematch 시그니처를 SSE room_state 이벤트에 추가해 해결), 게임이 끝난 뒤에도 판세 분석 패널이 "상대 입장 대기 중" 문구를 그대로 보여주던 문제, 모바일 한 컬럼 레이아웃에서 `position: fixed` 리액션 패널이 AI 전략 카드를 가려버리던 문제(기본 접힘 상태로 변경). AI 추천 패널에는 추천된 keep 조합을 한 번에 적용하는 버튼을 추가했고, 좁은 화면에서 상태 카드 텍스트가 단어 중간에 줄바꿈되던 것도 고쳤다.

Roll-stage 추천 로직에서 `choose_target_keep`의 tie-break가 "이미 성공이 확정된 족보"(예: 이미 4 of a Kind 완성)일 때도 가장 긴 kept_tuple을 선호해 공짜 재굴림 기회를 버리던 버그를 수정했다. 100게임 decision-regret 재측정으로 검증(10.3907 → 10.2988점/게임, roll match 70.11% → 70.35%). 같은 세션에서 시도한 다른 두 가지 수정은 전체 regret을 오히려 악화시켜 되돌렸다 — 자세한 내용과 남은 과제는 [AI 품질 지표](./docs/ai-quality-metrics.md)에 기록.

### 2026-07-11 — 정확한 판세 전망과 멀티 모바일 안정화

멀티 판세 패널의 고정 카테고리 합산식을 제거하고, exact value table 예상 최종점수와 캐시된 백그라운드 Monte Carlo 승률을 연결했다. 승률에는 샘플 수와 표본 오차를 함께 표시한다.

승률 UI는 30샘플 빠른 추정을 먼저 보여준 뒤 같은 상태를 100샘플로 자동 보정한다. Upper Bonus는 상단 요약에서 `63점 달성 시 +35점`으로 설명하고 점수판 내부의 중복 Subtotal/Bonus 행은 제거했다. 멀티 채팅은 OpenMoji 기반의 여섯 가지 감정표현으로 교체했으며, 상대 화면에 큰 이모지와 짧은 효과음을 전용 `reaction` SSE event로 전달한다.

점수표의 Upper와 Upper Bonus 요약 카드에 마우스를 올리거나 키보드 포커스·모바일 터치를 하면 상단 도움말 영역에 63점 기준과 35점 보너스, 현재 남은 점수가 표시된다.

참가자 토큰을 URL 쿼리에서 `X-Player-Token` 헤더/POST body로 옮겼고, 상태 동기화는 SSE 우선 + polling fallback으로 바꿨다. 모바일에서는 굴리기 전 주사위를 placeholder로 표시하고 rolling 큐브를 축소해 겹침을 막았으며, 감정표현 버튼의 터치 높이와 하단 여백을 보강했다.

싱글/멀티에 중복된 주사위 3D CSS와 판세 패널 CSS는 `static/css/base.css`로 합쳤다.

### 2026-04-17 — 게임 UI 전면 개선

레이아웃을 전면적으로 다시 짰다. 싱글/멀티 모두 좌측 게임 영역 + 우측 점수판·AI 패널의 2단 그리드 구조로 바뀌었고, 모바일에선 자동으로 단일 컬럼으로 내려온다.

점수판은 Upper / Lower를 2열로 나란히 보여주는 compact 카드 형태로 새로 만들었다. 칸에 마우스를 올리면 현재 주사위 기준 예상 점수가 바로 표시되고, 클릭 가능한 칸은 호버 스타일로 구분된다. 멀티에서는 나와 상대 점수를 좌우로 나란히 비교하는 compare-board가 추가됐다.

AI 패널도 레이아웃을 바꿨다. 추천 대상을 pill 형태로 굵게 표시하고 현재 단계(굴림/기록)와 전략 모드(집중/커버) 칩을 상단에 띄운다. 추천 항목은 2열 카드 그리드로 보여주며, 기본은 상위 2개만 표시하고 "상세" 버튼으로 최대 5개까지 펼칠 수 있다. 접힌/펼쳐진 상태는 localStorage에 저장된다.

### 2026-04-17 — 서버 라우트 분리 + 문서 정합성 정리

`server.py`에 몰려 있던 설정/상태/라우트를 `config.py`, `app_state.py`, `routes/`, `utils/`로 나눴다. Flask app entry는 얇게 두고, 로비/AI/리더보드/방 로직을 blueprint 단위로 분리한 쪽.

같이 문서도 현재 동작 기준으로 맞췄다. `API.md`에서 사라진 `POST /api/login` 설명을 걷어내고, `focused` / `cover` 모드, `/api/leaderboard/multi`, room heartbeat, 현재 프로젝트 구조를 반영했다.

검증은 다시 돌렸다 — `py_compile`, Flask test client 스모크, golden check, soak warm/cold. 서버 분리 때문에 런타임 동작이 깨진 건 확인되지 않았다.

추가로 GitHub Actions `AI Validation` 워크플로도 현재 구조에 맞게 손봤다. branch push / PR에서 `verify_ai.py`와 `yacht-hosting.sh` 문법 체크가 같이 돌고, `py_compile` 대상에도 분리된 `routes/`, `utils/`, `config.py`, `app_state.py`가 들어간 상태다.

이후 라우트 통합 테스트도 붙였다. Flask `test_client` 기반으로 로비 presence, AI 추천/health, 멀티 방 생성-입장-관전-heartbeat-sync-leave, 리더보드 저장/리셋까지 `unittest`로 검증하고, GitHub Actions에서도 같이 돌게 연결했다.

로비 쪽 기능도 한 번 더 보강했다. 멀티 전적은 원래 파일에 계속 쌓이고 있었는데 화면에선 거의 못 쓰고 있어서, 최근 경기 기록 API와 플레이어 상세 전적 API를 추가했다. 승률, 평균 점수, 최근 폼, 연승/연패 요약이 내려오고 로비 리더보드에서도 바로 볼 수 있다.

정적인 Game Tip 패널은 최근 경기 패널로 바꿨고, 리더보드는 초기 1회 로드만 하던 상태에서 주기 갱신되도록 정리했다. 덕분에 방금 끝난 대전 결과가 로비에 바로 반영되고, 상위권 유저 클릭해서 전적을 확인할 수 있다.

멀티 게임 종료 뒤에는 재대결도 바로 이어지게 했다. 두 플레이어가 같은 방에서 `rematch`를 누르면 서버가 동의 상태를 추적하고, 둘 다 확인되는 순간 같은 room state를 새 경기로 리셋한다. 토큰이나 관전 링크를 다시 만들 필요가 없어서 흐름이 훨씬 매끄럽다.

싱글 쪽도 이번에 다시 손봤다. 로비에서 `솔로`와 `VS AI`를 바로 고를 수 있게 했고, 게임 안에서는 AI 코치 패널을 ON/OFF로 즉시 전환할 수 있다. `VS AI`에서는 같은 추천 엔진을 쓰는 `Yacht Bot`이 번갈아 턴을 진행하고, 코치를 켠 연습 모드나 `VS AI` 결과는 메인 싱글 랭킹에 섞이지 않게 정리했다.

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
