# Hard cases for model-20260630-roll-policy-v2.json

이 문서는 teacher top-1 accuracy가 아니라, 모델이 teacher와 다른 keep을 골랐을 때의 추가 EV 손실이 큰 케이스를 모은 것이다.
서버 runtime에서는 confidence gate와 exact gap guard를 통과하지 못하면 exact solver로 fallback한다.

## Summary

- Evaluated examples: 6554
- Top-1 accuracy: 0.9852
- Mean excess EV gap: 0.080825
- p99 excess EV gap: 0.038058
- Max excess EV gap: 69.344027

## Worst Cases

### 1. sample 2913 - excess EV gap 69.344027

- Dice: `1, 1, 1, 1, 1`
- Rolls left: `1`
- Mode: `cover`
- Open categories: Ones, Twos, Threes, Sixes, 4 of a Kind, Full House, Small Straight, Large Straight, Yacht
- Teacher keep: `1, 1, 1, 1, 1` -> 핸드 하나 이상 성공
- Model keep: `1, 1, 1, 1` -> 핸드 하나 이상 성공
- Model confidence: `0.508639`
- Teacher objective gap: `0.0`
- Model objective gap: `69.344027`

### 2. sample 1793 - excess EV gap 45.714258

- Dice: `5, 5, 5, 5, 5`
- Rolls left: `2`
- Mode: `cover`
- Open categories: Ones, Twos, Threes, Fours, Sixes, 4 of a Kind, Full House, Yacht
- Teacher keep: `5, 5, 5, 5, 5` -> 핸드 하나 이상 성공
- Model keep: `5, 5, 5, 5` -> 핸드 하나 이상 성공
- Model confidence: `0.988609`
- Teacher objective gap: `0.0`
- Model objective gap: `45.714258`

### 3. sample 2787 - excess EV gap 25.41955

- Dice: `2, 3, 3, 3, 3`
- Rolls left: `1`
- Mode: `cover`
- Open categories: 4 of a Kind, Large Straight, Yacht
- Teacher keep: `3, 3, 3, 3` -> 핸드 하나 이상 성공
- Model keep: `3, 3, 3` -> 핸드 하나 이상 성공
- Model confidence: `0.858842`
- Teacher objective gap: `0.0`
- Model objective gap: `25.41955`

### 4. sample 65 - excess EV gap 24.529142

- Dice: `5, 5, 5, 5, 6`
- Rolls left: `1`
- Mode: `focused`
- Open categories: 4 of a Kind
- Teacher keep: `5, 5, 5, 5, 6` -> 4 of a Kind
- Model keep: `5, 5, 5` -> 4 of a Kind
- Model confidence: `0.976432`
- Teacher objective gap: `0.0`
- Model objective gap: `24.529142`

### 5. sample 2968 - excess EV gap 21.679436

- Dice: `4, 4, 4, 4, 6`
- Rolls left: `1`
- Mode: `focused`
- Open categories: 4 of a Kind
- Teacher keep: `4, 4, 4, 4, 6` -> 4 of a Kind
- Model keep: `4, 4, 4` -> 4 of a Kind
- Model confidence: `0.998938`
- Teacher objective gap: `0.0`
- Model objective gap: `21.679436`

### 6. sample 2806 - excess EV gap 18.343359

- Dice: `1, 2, 2, 2, 2`
- Rolls left: `2`
- Mode: `focused`
- Open categories: Ones, Twos, Fours, 4 of a Kind, Small Straight, Large Straight, Yacht
- Teacher keep: `2, 2, 2, 2` -> Twos
- Model keep: `2, 2, 2` -> 4 of a Kind
- Model confidence: `0.996037`
- Teacher objective gap: `0.0`
- Model objective gap: `18.343359`

### 7. sample 4009 - excess EV gap 18.087039

- Dice: `4, 4, 4, 5, 5`
- Rolls left: `1`
- Mode: `cover`
- Open categories: Full House, Small Straight, Large Straight
- Teacher keep: `4, 4, 4, 5, 5` -> 핸드 하나 이상 성공
- Model keep: `4, 4, 5, 5` -> 핸드 하나 이상 성공
- Model confidence: `0.987291`
- Teacher objective gap: `0.0`
- Model objective gap: `18.087039`

### 8. sample 3288 - excess EV gap 16.61026

- Dice: `4, 6, 6, 6, 6`
- Rolls left: `2`
- Mode: `cover`
- Open categories: 4 of a Kind
- Teacher keep: `4, 6, 6, 6, 6` -> 핸드 하나 이상 성공
- Model keep: `6, 6, 6` -> 핸드 하나 이상 성공
- Model confidence: `0.717907`
- Teacher objective gap: `0.254234`
- Model objective gap: `16.864494`

### 9. sample 3328 - excess EV gap 16.564459

- Dice: `1, 4, 4, 4, 4`
- Rolls left: `1`
- Mode: `focused`
- Open categories: 4 of a Kind
- Teacher keep: `1, 4, 4, 4, 4` -> 4 of a Kind
- Model keep: `4, 4, 4` -> 4 of a Kind
- Model confidence: `0.999997`
- Teacher objective gap: `2.562538`
- Model objective gap: `19.126997`

### 10. sample 1252 - excess EV gap 15.669418

- Dice: `1, 6, 6, 6, 6`
- Rolls left: `2`
- Mode: `focused`
- Open categories: Ones, Twos, Threes, Fours, 4 of a Kind, Full House, Small Straight, Yacht
- Teacher keep: `1, 6, 6, 6, 6` -> 4 of a Kind
- Model keep: `6, 6, 6` -> 4 of a Kind
- Model confidence: `0.908614`
- Teacher objective gap: `8.284948`
- Model objective gap: `23.954366`
