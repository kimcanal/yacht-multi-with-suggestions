# AI Decision Framework

추천 엔진은 남은 reroll을 exact하게 계산하고, "지금 기록으로 넘어가기"도 같은 선택지로 비교한다. 점수 기록 단계는 점수판 상태와 새 턴 기준 기대치를 함께 반영하는 휴리스틱으로 처리한다.

수식과 상태 정의가 더 필요하면 [ai-math.md](./ai-math.md) 참고.

---

## Roll Stage

굴림 단계에서 엔진이 내리는 판단은 크게 여섯 가지 패턴으로 나뉜다.

**Free Upgrade** — Small Straight를 이미 잡아둔 상태에서 주사위 하나둘만 더 굴려 Large Straight를 노리는 경우. 실패해도 15점은 유지되니 사실상 공짜 시도에 가깝다.

**Stop Now** — Large Straight 30, 높은 4 of a Kind, Yacht Bonus cash-in처럼 지금 점수가 너무 좋을 때. 더 굴려봐야 얻을 게 없으니 기록 추천을 먼저 보여준다.

**Focused Chase** — pair + pair, triple, four in a row처럼 특정 족보로 이어지는 구조가 강할 때. Full House, 4 of a Kind, Yacht가 주요 대상. UI에는 해당 족보 완성 확률, keep 이유, 추천 근거, 지금 멈추기 비교, 차선책 비교가 함께 나온다.

**Cover Play** — 한 keep으로 4 of a Kind, Full House, Straight, Yacht 중 여러 개가 동시에 열릴 때. 이 상황에서는 특정 족보 하나의 성공률보다 하나라도 터질 확률, 전부 실패할 확률이 더 중요한 지표가 된다.

**Upper Bonus Push** — 상단 합이 63 근처라 특정 숫자를 keep하면 보너스 흐름이 좋아지는 상황. Sixes를 잡으면 이번 턴이나 가까운 턴에 +35를 확보할 수 있는 경우가 여기 해당한다. Upper Bonus 도달 확률 변화도 utility에 반영된다.

**Reset** — 현재 패가 어떤 족보로도 잘 이어지지 않고, 특정 숫자를 모으는 것도 애매할 때. 억지로 keep을 찾기보다 전체 reroll이 낫다.

---

## Score Stage

굴림이 끝나고 어디에 기록할지 판단하는 단계다.

**Immediate High Value** — Large Straight 30, Yacht 50, 높은 Choice나 4 of a Kind처럼 즉시 점수가 충분히 커서 그냥 확정하는 게 나은 경우.

**Bonus Finish** — 상단 점수를 기록하면 Upper Bonus +35를 바로 챙길 수 있을 때. 점수 자체보다 보너스 확보 가치가 더 클 때가 있다.

**Low-Risk Settle** — 완벽한 고점은 아니어도 손해 없이 턴을 마감할 수 있을 때. Choice 23, Fives 10, Sixes 12 같은 경우. 현재 점수만이 아니라 그 칸의 새 턴 기준 기대치와 비교해서 이번 기록이 좋은지 나쁜지도 같이 본다.

**Sacrifice** — 이번 턴에 제대로 기록할 점수가 거의 없을 때. 보통 Ones, Twos, Yacht처럼 새 턴 기준 기대치가 낮은 칸부터 희생 후보가 된다. Upper Bonus 압력, 열린 칸의 미래 기대치, 보너스 확률 하락폭을 같이 보고 결정한다.

**Yacht Bonus Cash-In** — 이미 Yacht를 확보한 상태에서 이번 턴도 Yacht가 나와 다른 칸에 적으면 +100이 붙는 경우. 다른 어떤 판단보다 이걸 우선한다.

---

## Fresh-Turn Baselines

희생 칸을 고를 때 "새 턴 하나를 온전히 쓴다면 이 카테고리에서 얼마나 기대할 수 있나"를 기준선으로 쓴다. "이 칸은 절대 못 버린다"는 의미가 아니라, 망한 턴에서 어느 칸부터 비우면 덜 아픈지를 가늠하는 참고선이다.

- Ones 2.1, Twos 4.2, Threes 6.3, Fours 8.4, Fives 10.5, Sixes 12.6
- Choice 23.3
- 4 of a Kind 5.6, Full House 7.0
- Small Straight 9.2, Large Straight 7.8
- Yacht 2.3

---

## Long-Run Closing Cost

별도로 rollout 기반으로 "이 칸을 0으로 닫고 게임을 시작하면 최종 점수가 평균 얼마나 깎이는지"도 추정해 쓴다.

- 대략 Yacht 1.5, Threes 5.8, Ones/Twos 8점대, Choice 10점대
- Small Straight 12.8, Sixes 14.8, Full House 18.9
- Fours 22.8, Large Straight 29.6

엔진은 이 장기 손실 추정치를 희생 판단에 일부 섞고, 상단 보너스 확률 변화도 같이 본다. score stage utility에는 이번 점수와 새 턴 기준 기대치의 차이, 그리고 이 점수를 지금 기록하면 그 칸을 닫는 장기 부담이 얼마나 줄어드는지도 보수적으로 반영된다. UI의 "장기 가치" 줄이 이 부분이다.

---

## 현재 엔진이 아직 못 하는 것

남은 reroll과 지금 멈추기는 exact하게 계산하지만, 이번 턴이 끝난 뒤 남은 전체 경기 기대값을 full-game DP로 계산하지는 않는다. score stage가 "장기 가치 일부 반영"까지는 왔지만, 남은 경기 전체 최적화는 아직이다.

더 강한 AI를 원한다면 기록 단계 action을 "현재 점수 + 미래 기대값" 기준으로 다시 학습하거나 value table로 올리는 게 가장 큰 업그레이드가 될 것 같다.
