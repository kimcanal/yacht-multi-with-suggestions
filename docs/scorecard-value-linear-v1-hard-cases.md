# Value baseline hard cases for scorecard-value-linear-v1

이 문서는 scorecard state -> remaining score baseline이 크게 빗나간 상태를 모은 것이다.
목적은 모델 운영 투입이 아니라, score-stage 휴리스틱이 실제 self-play 결과와 어긋나는 구간을 찾는 것이다.

## Summary

- Examples: 3072
- MAE: 22.945553
- RMSE: 32.180033
- Mean error: 0.045724
- R2: 0.755043

## Error By Turn

- turns_completed=0: n=256, MAE=35.0179, mean_target=177.464844
- turns_completed=1: n=256, MAE=33.302797, mean_target=157.5
- turns_completed=2: n=256, MAE=32.669542, mean_target=138.105469
- turns_completed=3: n=256, MAE=29.925968, mean_target=118.855469
- turns_completed=4: n=256, MAE=27.428816, mean_target=100.496094
- turns_completed=5: n=256, MAE=24.638865, mean_target=84.578125
- turns_completed=6: n=256, MAE=20.79306, mean_target=68.820312
- turns_completed=7: n=256, MAE=19.081133, mean_target=53.511719
- turns_completed=8: n=256, MAE=16.546367, mean_target=39.269531
- turns_completed=9: n=256, MAE=14.733367, mean_target=26.808594
- turns_completed=10: n=256, MAE=11.656097, mean_target=13.527344
- turns_completed=11: n=256, MAE=9.552728, mean_target=5.082031

## Worst Absolute Errors

### 1. line 2557 - abs error 194.5174

- Turn: `0` completed, current total `0`
- Target remaining: `372.0`, predicted `177.4826`, error `-194.5174`
- Upper: `0` / gap `63`, yacht bonus active `False`
- Open categories: Ones, Twos, Threes, Fours, Fives, Sixes, Choice, 4 of a Kind, Full House, Small Straight, Large Straight, Yacht
- Next scored: Large Straight 30점
- Scorecard: `[None, None, None, None, None, None, None, None, None, None, None, None]`

### 2. line 2247 - abs error 189.5226

- Turn: `2` completed, current total `36`
- Target remaining: `304.0`, predicted `114.4774`, error `-189.5226`
- Upper: `12` / gap `51`, yacht bonus active `False`
- Open categories: Ones, Twos, Threes, Fours, Fives, 4 of a Kind, Full House, Small Straight, Large Straight, Yacht
- Next scored: Yacht 50점
- Scorecard: `[None, None, None, None, None, 12, 24, None, None, None, None, None]`

### 3. line 1357 - abs error 189.5174

- Turn: `0` completed, current total `0`
- Target remaining: `367.0`, predicted `177.4826`, error `-189.5174`
- Upper: `0` / gap `63`, yacht bonus active `False`
- Open categories: Ones, Twos, Threes, Fours, Fives, Sixes, Choice, 4 of a Kind, Full House, Small Straight, Large Straight, Yacht
- Next scored: Yacht 50점
- Scorecard: `[None, None, None, None, None, None, None, None, None, None, None, None]`

### 4. line 2558 - abs error 185.6957

- Turn: `1` completed, current total `30`
- Target remaining: `342.0`, predicted `156.3043`, error `-185.6957`
- Upper: `0` / gap `63`, yacht bonus active `False`
- Open categories: Ones, Twos, Threes, Fours, Fives, Sixes, Choice, 4 of a Kind, Full House, Small Straight, Yacht
- Next scored: Threes 12점
- Scorecard: `[None, None, None, None, None, None, None, None, None, None, 30, None]`

### 5. line 2560 - abs error 178.6766

- Turn: `3` completed, current total `50`
- Target remaining: `322.0`, predicted `143.3234`, error `-178.6766`
- Upper: `20` / gap `43`, yacht bonus active `False`
- Open categories: Ones, Fours, Fives, Sixes, Choice, 4 of a Kind, Full House, Small Straight, Yacht
- Next scored: Yacht 50점
- Scorecard: `[None, 8, 12, None, None, None, None, None, None, None, 30, None]`

### 6. line 2559 - abs error 177.2423

- Turn: `2` completed, current total `42`
- Target remaining: `330.0`, predicted `152.7577`, error `-177.2423`
- Upper: `12` / gap `51`, yacht bonus active `False`
- Open categories: Ones, Twos, Fours, Fives, Sixes, Choice, 4 of a Kind, Full House, Small Straight, Yacht
- Next scored: Twos 8점
- Scorecard: `[None, None, 12, None, None, None, None, None, None, None, 30, None]`

### 7. line 2413 - abs error 172.5174

- Turn: `0` completed, current total `0`
- Target remaining: `350.0`, predicted `177.4826`, error `-172.5174`
- Upper: `0` / gap `63`, yacht bonus active `False`
- Open categories: Ones, Twos, Threes, Fours, Fives, Sixes, Choice, 4 of a Kind, Full House, Small Straight, Large Straight, Yacht
- Next scored: Yacht 50점
- Scorecard: `[None, None, None, None, None, None, None, None, None, None, None, None]`

### 8. line 722 - abs error 171.0799

- Turn: `1` completed, current total `25`
- Target remaining: `318.0`, predicted `146.9201`, error `-171.0799`
- Upper: `0` / gap `63`, yacht bonus active `False`
- Open categories: Ones, Twos, Threes, Fours, Fives, Sixes, 4 of a Kind, Full House, Small Straight, Large Straight, Yacht
- Next scored: Fours 16점
- Scorecard: `[None, None, None, None, None, None, 25, None, None, None, None, None]`

### 9. line 2246 - abs error 168.966

- Turn: `1` completed, current total `24`
- Target remaining: `316.0`, predicted `147.034`, error `-168.966`
- Upper: `0` / gap `63`, yacht bonus active `False`
- Open categories: Ones, Twos, Threes, Fours, Fives, Sixes, 4 of a Kind, Full House, Small Straight, Large Straight, Yacht
- Next scored: Sixes 12점
- Scorecard: `[None, None, None, None, None, None, 24, None, None, None, None, None]`

### 10. line 721 - abs error 165.5174

- Turn: `0` completed, current total `0`
- Target remaining: `343.0`, predicted `177.4826`, error `-165.5174`
- Upper: `0` / gap `63`, yacht bonus active `False`
- Open categories: Ones, Twos, Threes, Fours, Fives, Sixes, Choice, 4 of a Kind, Full House, Small Straight, Large Straight, Yacht
- Next scored: Choice 25점
- Scorecard: `[None, None, None, None, None, None, None, None, None, None, None, None]`


## Over-predictions

### 1. line 2474 - abs error 92.9767

- Turn: `1` completed, current total `50`
- Target remaining: `117.0`, predicted `209.9767`, error `92.9767`
- Upper: `0` / gap `63`, yacht bonus active `True`
- Open categories: Ones, Twos, Threes, Fours, Fives, Sixes, Choice, 4 of a Kind, Full House, Small Straight, Large Straight
- Next scored: Sixes 12점
- Scorecard: `[None, None, None, None, None, None, None, None, None, None, None, 50]`

### 2. line 2977 - abs error 86.4826

- Turn: `0` completed, current total `0`
- Target remaining: `91.0`, predicted `177.4826`, error `86.4826`
- Upper: `0` / gap `63`, yacht bonus active `False`
- Open categories: Ones, Twos, Threes, Fours, Fives, Sixes, Choice, 4 of a Kind, Full House, Small Straight, Large Straight, Yacht
- Next scored: Choice 23점
- Scorecard: `[None, None, None, None, None, None, None, None, None, None, None, None]`

### 3. line 2523 - abs error 86.4363

- Turn: `2` completed, current total `80`
- Target remaining: `98.0`, predicted `184.4363`, error `86.4363`
- Upper: `0` / gap `63`, yacht bonus active `True`
- Open categories: Ones, Twos, Threes, Fours, Fives, Sixes, Choice, 4 of a Kind, Full House, Small Straight
- Next scored: Small Straight 15점
- Scorecard: `[None, None, None, None, None, None, None, None, None, None, 30, 50]`

### 4. line 1249 - abs error 84.4826

- Turn: `0` completed, current total `0`
- Target remaining: `93.0`, predicted `177.4826`, error `84.4826`
- Upper: `0` / gap `63`, yacht bonus active `False`
- Open categories: Ones, Twos, Threes, Fours, Fives, Sixes, Choice, 4 of a Kind, Full House, Small Straight, Large Straight, Yacht
- Next scored: Choice 18점
- Scorecard: `[None, None, None, None, None, None, None, None, None, None, None, None]`

### 5. line 2524 - abs error 80.756

- Turn: `3` completed, current total `95`
- Target remaining: `83.0`, predicted `163.756`, error `80.756`
- Upper: `0` / gap `63`, yacht bonus active `True`
- Open categories: Ones, Twos, Threes, Fours, Fives, Sixes, Choice, 4 of a Kind, Full House
- Next scored: Choice 21점
- Scorecard: `[None, None, None, None, None, None, None, None, None, 15, 30, 50]`

### 6. line 2341 - abs error 80.4826

- Turn: `0` completed, current total `0`
- Target remaining: `97.0`, predicted `177.4826`, error `80.4826`
- Upper: `0` / gap `63`, yacht bonus active `False`
- Open categories: Ones, Twos, Threes, Fours, Fives, Sixes, Choice, 4 of a Kind, Full House, Small Straight, Large Straight, Yacht
- Next scored: Choice 23점
- Scorecard: `[None, None, None, None, None, None, None, None, None, None, None, None]`

### 7. line 2978 - abs error 79.1479

- Turn: `1` completed, current total `23`
- Target remaining: `68.0`, predicted `147.1479`, error `79.1479`
- Upper: `0` / gap `63`, yacht bonus active `False`
- Open categories: Ones, Twos, Threes, Fours, Fives, Sixes, 4 of a Kind, Full House, Small Straight, Large Straight, Yacht
- Next scored: Twos 8점
- Scorecard: `[None, None, None, None, None, None, 23, None, None, None, None, None]`

### 8. line 1441 - abs error 78.4826

- Turn: `0` completed, current total `0`
- Target remaining: `99.0`, predicted `177.4826`, error `78.4826`
- Upper: `0` / gap `63`, yacht bonus active `False`
- Open categories: Ones, Twos, Threes, Fours, Fives, Sixes, Choice, 4 of a Kind, Full House, Small Straight, Large Straight, Yacht
- Next scored: Choice 23점
- Scorecard: `[None, None, None, None, None, None, None, None, None, None, None, None]`

### 9. line 2593 - abs error 78.4826

- Turn: `0` completed, current total `0`
- Target remaining: `99.0`, predicted `177.4826`, error `78.4826`
- Upper: `0` / gap `63`, yacht bonus active `False`
- Open categories: Ones, Twos, Threes, Fours, Fives, Sixes, Choice, 4 of a Kind, Full House, Small Straight, Large Straight, Yacht
- Next scored: Small Straight 15점
- Scorecard: `[None, None, None, None, None, None, None, None, None, None, None, None]`

### 10. line 2979 - abs error 77.7136

- Turn: `2` completed, current total `31`
- Target remaining: `60.0`, predicted `137.7136`, error `77.7136`
- Upper: `8` / gap `55`, yacht bonus active `False`
- Open categories: Ones, Threes, Fours, Fives, Sixes, 4 of a Kind, Full House, Small Straight, Large Straight, Yacht
- Next scored: Sixes 12점
- Scorecard: `[None, 8, None, None, None, None, 23, None, None, None, None, None]`


## Under-predictions

### 1. line 2557 - abs error 194.5174

- Turn: `0` completed, current total `0`
- Target remaining: `372.0`, predicted `177.4826`, error `-194.5174`
- Upper: `0` / gap `63`, yacht bonus active `False`
- Open categories: Ones, Twos, Threes, Fours, Fives, Sixes, Choice, 4 of a Kind, Full House, Small Straight, Large Straight, Yacht
- Next scored: Large Straight 30점
- Scorecard: `[None, None, None, None, None, None, None, None, None, None, None, None]`

### 2. line 2247 - abs error 189.5226

- Turn: `2` completed, current total `36`
- Target remaining: `304.0`, predicted `114.4774`, error `-189.5226`
- Upper: `12` / gap `51`, yacht bonus active `False`
- Open categories: Ones, Twos, Threes, Fours, Fives, 4 of a Kind, Full House, Small Straight, Large Straight, Yacht
- Next scored: Yacht 50점
- Scorecard: `[None, None, None, None, None, 12, 24, None, None, None, None, None]`

### 3. line 1357 - abs error 189.5174

- Turn: `0` completed, current total `0`
- Target remaining: `367.0`, predicted `177.4826`, error `-189.5174`
- Upper: `0` / gap `63`, yacht bonus active `False`
- Open categories: Ones, Twos, Threes, Fours, Fives, Sixes, Choice, 4 of a Kind, Full House, Small Straight, Large Straight, Yacht
- Next scored: Yacht 50점
- Scorecard: `[None, None, None, None, None, None, None, None, None, None, None, None]`

### 4. line 2558 - abs error 185.6957

- Turn: `1` completed, current total `30`
- Target remaining: `342.0`, predicted `156.3043`, error `-185.6957`
- Upper: `0` / gap `63`, yacht bonus active `False`
- Open categories: Ones, Twos, Threes, Fours, Fives, Sixes, Choice, 4 of a Kind, Full House, Small Straight, Yacht
- Next scored: Threes 12점
- Scorecard: `[None, None, None, None, None, None, None, None, None, None, 30, None]`

### 5. line 2560 - abs error 178.6766

- Turn: `3` completed, current total `50`
- Target remaining: `322.0`, predicted `143.3234`, error `-178.6766`
- Upper: `20` / gap `43`, yacht bonus active `False`
- Open categories: Ones, Fours, Fives, Sixes, Choice, 4 of a Kind, Full House, Small Straight, Yacht
- Next scored: Yacht 50점
- Scorecard: `[None, 8, 12, None, None, None, None, None, None, None, 30, None]`

### 6. line 2559 - abs error 177.2423

- Turn: `2` completed, current total `42`
- Target remaining: `330.0`, predicted `152.7577`, error `-177.2423`
- Upper: `12` / gap `51`, yacht bonus active `False`
- Open categories: Ones, Twos, Fours, Fives, Sixes, Choice, 4 of a Kind, Full House, Small Straight, Yacht
- Next scored: Twos 8점
- Scorecard: `[None, None, 12, None, None, None, None, None, None, None, 30, None]`

### 7. line 2413 - abs error 172.5174

- Turn: `0` completed, current total `0`
- Target remaining: `350.0`, predicted `177.4826`, error `-172.5174`
- Upper: `0` / gap `63`, yacht bonus active `False`
- Open categories: Ones, Twos, Threes, Fours, Fives, Sixes, Choice, 4 of a Kind, Full House, Small Straight, Large Straight, Yacht
- Next scored: Yacht 50점
- Scorecard: `[None, None, None, None, None, None, None, None, None, None, None, None]`

### 8. line 722 - abs error 171.0799

- Turn: `1` completed, current total `25`
- Target remaining: `318.0`, predicted `146.9201`, error `-171.0799`
- Upper: `0` / gap `63`, yacht bonus active `False`
- Open categories: Ones, Twos, Threes, Fours, Fives, Sixes, 4 of a Kind, Full House, Small Straight, Large Straight, Yacht
- Next scored: Fours 16점
- Scorecard: `[None, None, None, None, None, None, 25, None, None, None, None, None]`

### 9. line 2246 - abs error 168.966

- Turn: `1` completed, current total `24`
- Target remaining: `316.0`, predicted `147.034`, error `-168.966`
- Upper: `0` / gap `63`, yacht bonus active `False`
- Open categories: Ones, Twos, Threes, Fours, Fives, Sixes, 4 of a Kind, Full House, Small Straight, Large Straight, Yacht
- Next scored: Sixes 12점
- Scorecard: `[None, None, None, None, None, None, 24, None, None, None, None, None]`

### 10. line 721 - abs error 165.5174

- Turn: `0` completed, current total `0`
- Target remaining: `343.0`, predicted `177.4826`, error `-165.5174`
- Upper: `0` / gap `63`, yacht bonus active `False`
- Open categories: Ones, Twos, Threes, Fours, Fives, Sixes, Choice, 4 of a Kind, Full House, Small Straight, Large Straight, Yacht
- Next scored: Choice 25점
- Scorecard: `[None, None, None, None, None, None, None, None, None, None, None, None]`
