# AI Decision Framework

현재 추천 엔진은 "이번 턴 안의 남은 reroll"을 exact하게 보고, `지금 멈추고 점수 기록`까지 같은 액션 후보로 비교한다. 점수 기록 단계는 점수판 상태와 `새 턴 기준 기대치`를 함께 반영한 휴리스틱으로 정리한다. 추천 문구를 읽을 때는 아래 기준으로 해석하는 것이 가장 자연스럽다.

## Roll Stage

1. Free Upgrade
   - 이미 `Small Straight`는 지키고 있고, 남은 주사위 하나나 둘만 굴려 `Large Straight`를 노리는 경우
   - 실패해도 15점을 유지하므로 사실상 공짜 업그레이드 시도에 가깝다

2. Stop Now
   - 이미 `Large Straight`, 높은 `4 of a Kind`, `Yacht Bonus cash-in`처럼 지금 확정 점수가 너무 좋을 때
   - 이 경우는 "한 번 더 굴릴 확률"보다 `지금 기록 추천`이 먼저 뜨는 편이 맞다

3. Focused Chase
   - `pair + pair`, `triple`, `four in a row`처럼 특정 족보로 이어지는 구조가 강할 때
   - 예: `Full House`, `4 of a Kind`, `Yacht`
   - UI에는 해당 족보 완성 확률과 keep 이유가 같이 보여야 한다
   - 최근 빌드에서는 여기에 `추천 근거`, `지금 멈추기 비교`, `차선책 비교`도 같이 보여준다

4. Cover Play
   - 한 keep으로 `4 of a Kind`, `Full House`, `Straight`, `Yacht` 중 여러 개가 동시에 열릴 때
   - 이때는 특정 족보 하나보다 `하나 이상 성공 확률`과 `전부 실패 확률`이 더 중요하다

5. Upper Bonus Push
   - 상단 합이 `63` 근처이고 특정 숫자를 keep하면 보너스 흐름이 좋아지는 경우
   - 예: `Sixes`를 잡으면 이번 턴 또는 가까운 턴에 `+35`를 확보할 수 있는 상황
   - 현재 엔진은 여기서 `Upper Bonus 도달 확률`이 얼마나 오르거나 떨어지는지도 utility에 반영한다

6. Reset
   - 현재 손패가 어떤 족보로도 잘 이어지지 않고, 특정 숫자를 모으는 쪽도 애매할 때
   - 이 경우는 억지 keep보다 전체 reroll이 낫다

## Score Stage

1. Immediate High Value
   - `Large Straight 30`, `Yacht 50`, 높은 `Choice`, 높은 `4 of a Kind`
   - 즉시 점수 자체가 커서 그냥 확정하는 편이 좋은 경우

2. Bonus Finish
   - 상단 점수 기록으로 `Upper Bonus +35`를 바로 얻을 수 있을 때
   - 즉시 점수보다 보너스 확보 가치가 더 큰 경우가 있다

3. Low-Risk Settle
   - 완벽한 고점은 아니더라도 손해 없이 턴을 마감할 수 있을 때
   - 예: `Choice 23`, `Fives 10`, `Sixes 12`
   - 단순 현재 점수만이 아니라, 그 칸의 `새 턴 기준 기대치` 대비 이번 기록이 좋은지 나쁜지도 함께 본다

4. Sacrifice
   - 이번 턴에 제대로 기록할 점수가 거의 없을 때
   - 보통 `Ones`, `Twos`, `Yacht`처럼 새 턴 기준 기대치가 낮은 칸부터 희생 후보가 된다
   - 현재 엔진은 고정 우선순위만 보지 않고, `Upper Bonus` 압력과 열린 칸의 미래 기대치, 그리고 보너스 확률 하락폭을 함께 본다

5. Yacht Bonus Cash-In
   - 이미 `Yacht`를 확보했고 이번 턴도 Yacht가 떠서 다른 칸에 적으면 `+100`이 붙는 경우
   - 일반적인 점수 판단보다 훨씬 우선순위가 높다

## Fresh-Turn Baselines

점수칸 희생 판단은 "새 턴 하나를 온전히 투자했을 때" 카테고리 기대치가 어느 정도인지도 참고한다.

- `Ones 2.1`, `Twos 4.2`, `Threes 6.3`, `Fours 8.4`, `Fives 10.5`, `Sixes 12.6`
- `Choice 23.3`
- `4 of a Kind 5.6`, `Full House 7.0`
- `Small Straight 9.2`, `Large Straight 7.8`
- `Yacht 2.3`

이 숫자는 "그 칸을 절대 버리면 안 된다"는 뜻이 아니라, 망한 턴에서 무엇을 먼저 비우면 덜 아픈지를 가늠하는 보조선이다.

## Long-Run Closing Cost

별도로 rollout 기반으로 "그 칸을 아예 0으로 닫고 게임을 시작하면 평균 점수가 얼마나 깎이는지"도 추정할 수 있다.

- 대략 `Yacht 1.5`, `Threes 5.8`, `Ones/Twos 8점대`, `Choice 10점대`
- `Small Straight 12.8`, `Sixes 14.8`, `Full House 18.9`
- `Fours 22.8`, `Large Straight 29.6`

현재 엔진은 이런 장기 손실 추정치를 희생 판단에 일부 섞고, 여기에 현재 상단 보너스 확률 변화까지 함께 본다.

추가로 현재 build는 score stage에서

- `이번 점수 - 새 턴 기준 기대치` 차이
- 이번 기록이 좋아서 `그 칸을 닫는 장기 부담`이 얼마나 줄어드는지

를 utility에 보수적으로 반영한다. UI의 `장기 가치` 줄은 이 부분을 풀어쓴 것이다.

## What This Engine Still Does Not Fully Solve

- 현재 추천은 `남은 reroll`과 `지금 멈추기`까지는 exact하게 본다
- 하지만 `이번 턴이 끝난 뒤 남은 전체 경기 기대값`까지 완전한 full-game DP로 계산하지는 않는다
- 그래서 score stage는 "장기 가치 일부 반영"에서 한 단계 더 나아갔지만, 여전히 "남은 경기 전체 최적화" 자체는 아니다

다음 단계에서 더 강한 AI를 원하면, 기록 단계 action을 `현재 점수 + 미래 기대값` 기준으로 다시 학습하거나 value table로 올리는 것이 가장 큰 업그레이드가 된다.
