# Decision Simulation Notes (2026-05-21)

요청사항: "전체 roll + 턴 기준으로 어떤 선택이 이득인지"를 확인하기 위해 시나리오 기반 시뮬레이션을 추가했다.

## 추가한 도구
- `scripts/simulate_turn_decisions.py`
  - 특정 dice / rolls_left / scorecard 상태에서 여러 keep 후보를 샘플링해 비교
  - AI 추천 결과와 함께 상위 keep 후보 EV 추정치를 출력

## 실행 예시
```bash
python3 scripts/simulate_turn_decisions.py --trials 80
```

## 관찰 포인트
1. 같은 주사위라도 scorecard(특히 upper bonus 근접도)에 따라 추천이 달라진다.
2. `[1,1,1,4,6]` 케이스는 빈 점수판에선 하단 노림(4-kind 계열) 성향이 나타날 수 있고,
   upper bonus 압력이 있을 때는 `Sixes` 쪽 keep으로 기울었다.
3. `small straight` 유지 + `large straight` 업그레이드 경로는 엔진이 이미 반영하고 있다.

## 중요한 해석 주의
- 이 스크립트의 EV는 "샘플링 기반 근사 비교"이며, 최종 의사결정 품질 평가는
  기존 golden/soak/verify와 함께 봐야 한다.
