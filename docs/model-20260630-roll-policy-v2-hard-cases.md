# Hard cases for model-20260630-roll-policy-v2.json

이 문서는 teacher top-1 accuracy가 아니라, 모델이 teacher와 다른 keep을 골랐을 때의 추가 EV 손실이 큰 케이스를 모은 것이다.
서버 runtime에서는 confidence gate와 exact gap guard를 통과하지 못하면 exact solver로 fallback한다.

## Summary

- Evaluated examples: 6554
- Top-1 accuracy: 0.9852
- Mean excess EV gap: 0.023701
- p99 excess EV gap: 0.0
- Max excess EV gap: 10.145227

## Worst Cases

### 1. sample 2583 - excess EV gap 10.145227

- Dice: `1, 1, 4, 5, 6`
- Rolls left: `2`
- Mode: `cover`
- Open categories: Sixes
- Teacher keep: `6` -> Sixes
- Model keep: `4` -> None
- Model confidence: `0.78765`
- Teacher objective gap: `0.0`
- Model objective gap: `10.145227`

### 2. sample 3550 - excess EV gap 8.795276

- Dice: `2, 2, 2, 4, 4`
- Rolls left: `1`
- Mode: `cover`
- Open categories: Ones, Threes, 4 of a Kind, Small Straight, Large Straight, Yacht
- Teacher keep: `2, 2, 2` -> 핸드 하나 이상 성공
- Model keep: `2, 2, 2, 4, 4` -> None
- Model confidence: `0.891294`
- Teacher objective gap: `0.0`
- Model objective gap: `8.795276`

### 3. sample 3950 - excess EV gap 8.454355

- Dice: `1, 3, 4, 5, 6`
- Rolls left: `2`
- Mode: `cover`
- Open categories: Sixes
- Teacher keep: `6` -> Sixes
- Model keep: `-` -> None
- Model confidence: `0.988233`
- Teacher objective gap: `0.0`
- Model objective gap: `8.454355`

### 4. sample 3667 - excess EV gap 7.886291

- Dice: `4, 5, 5, 6, 6`
- Rolls left: `2`
- Mode: `focused`
- Open categories: Fours
- Teacher keep: `4` -> Fours
- Model keep: `6, 6` -> None
- Model confidence: `0.765442`
- Teacher objective gap: `0.0`
- Model objective gap: `7.886291`

### 5. sample 50 - excess EV gap 7.75637

- Dice: `3, 4, 5, 5, 5`
- Rolls left: `2`
- Mode: `cover`
- Open categories: Large Straight
- Teacher keep: `3, 4, 5` -> 핸드 하나 이상 성공
- Model keep: `3, 5, 5, 5` -> 핸드 하나 이상 성공
- Model confidence: `0.657452`
- Teacher objective gap: `0.0`
- Model objective gap: `7.75637`

### 6. sample 3827 - excess EV gap 6.37303

- Dice: `1, 4, 4, 4, 5`
- Rolls left: `1`
- Mode: `focused`
- Open categories: Ones, Twos, Threes, Fives, Full House, Small Straight, Yacht
- Teacher keep: `4, 5` -> Small Straight
- Model keep: `4, 4, 4` -> Full House
- Model confidence: `0.853051`
- Teacher objective gap: `1.447898`
- Model objective gap: `7.820928`

### 7. sample 3204 - excess EV gap 5.426667

- Dice: `1, 3, 3, 5, 6`
- Rolls left: `1`
- Mode: `focused`
- Open categories: Ones, Threes, Fours, Full House, Yacht
- Teacher keep: `3, 3` -> Full House
- Model keep: `3` -> Full House
- Model confidence: `0.999361`
- Teacher objective gap: `0.0`
- Model objective gap: `5.426667`

### 8. sample 1310 - excess EV gap 5.424389

- Dice: `1, 1, 1, 4, 5`
- Rolls left: `1`
- Mode: `cover`
- Open categories: 4 of a Kind
- Teacher keep: `1, 1, 1` -> 핸드 하나 이상 성공
- Model keep: `1, 1` -> 핸드 하나 이상 성공
- Model confidence: `0.897592`
- Teacher objective gap: `0.0`
- Model objective gap: `5.424389`

### 9. sample 2689 - excess EV gap 5.320692

- Dice: `1, 1, 1, 3, 3`
- Rolls left: `2`
- Mode: `cover`
- Open categories: Ones, Twos, Threes, Fours, Fives, Choice, 4 of a Kind, Small Straight, Large Straight, Yacht
- Teacher keep: `1, 1, 1` -> 핸드 하나 이상 성공
- Model keep: `1, 1, 1, 3, 3` -> Threes
- Model confidence: `0.99827`
- Teacher objective gap: `0.915873`
- Model objective gap: `6.236565`

### 10. sample 2936 - excess EV gap 4.896698

- Dice: `2, 2, 2, 2, 5`
- Rolls left: `2`
- Mode: `cover`
- Open categories: Large Straight
- Teacher keep: `2, 5` -> 핸드 하나 이상 성공
- Model keep: `2, 2, 2, 2, 5` -> None
- Model confidence: `0.975655`
- Teacher objective gap: `0.0`
- Model objective gap: `4.896698`
