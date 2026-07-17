# AI Decision Regret vs Exact Optimal

- Games per policy: `100`
- Seed: `20260709` / random source: `indexed`
- Value table: `artifacts/runtime/value/endgame-value-table-open12.npz`
- Metric: regret = Q*(best action) - Q*(chosen action), in expected final-score points

## Summary

| policy | avg score | avg regret/game | roll match | score match | roll avg regret | score avg regret |
|---|---|---|---|---|---|---|
| focused | 175.12 | 22.4147 | 0.7066 | 0.79 | 0.4136 | 1.049 |
| cover | 154.15 | 37.9171 | 0.5996 | 0.71 | 0.8427 | 1.5164 |
| optimal | 192.94 | 0.0 | 1.0 | 1.0 | 0.0 | 0.0 |

## focused

- Avg regret per game: 22.4147 (median 21.7167)
- Roll decisions: 2376, match 0.7066, avg mistake size 1.4098, max 9.9884
- Score decisions: 1200, match 0.79, avg mistake size 4.9954, max 29.9449
- Regret by turn: {'1': 1.028, '2': 1.1414, '3': 0.8467, '4': 0.93, '5': 0.6022, '6': 0.6084, '7': 0.6448, '8': 0.5969, '9': 0.3904, '10': 0.5386, '11': 0.1553, '12': 0.0345}

### Worst Decisions

- turn 9 score (rolls_left 0): dice [2, 3, 4, 4, 6], chosen `Threes`, optimal `Yacht`, regret 29.9449, scorecard `[1, 6, None, 12, 15, 24, 23, 27, None, 15, None, None]`
- turn 10 score (rolls_left 0): dice [6, 6, 5, 5, 6], chosen `Threes`, optimal `4 of a Kind`, regret 29.8054, scorecard `[2, 6, None, 16, 15, 18, 22, None, 24, 15, None, 0]`
- turn 8 score (rolls_left 0): dice [5, 5, 5, 5, 5], chosen `Fives`, optimal `Yacht`, regret 29.6726, scorecard `[None, 6, None, 16, None, 18, 16, None, 28, 15, 30, None]`
- turn 10 score (rolls_left 0): dice [2, 4, 1, 2, 5], chosen `Ones`, optimal `Yacht`, regret 26.2238, scorecard `[None, 2, 9, 12, 20, 18, 20, None, 9, 15, 30, None]`
- turn 7 score (rolls_left 0): dice [5, 4, 5, 3, 5], chosen `Threes`, optimal `Yacht`, regret 18.9486, scorecard `[None, None, None, 16, 15, 18, 16, None, None, 15, 30, None]`

## cover

- Avg regret per game: 37.9171 (median 37.3152)
- Roll decisions: 2340, match 0.5996, avg mistake size 2.1046, max 20.1797
- Score decisions: 1200, match 0.71, avg mistake size 5.229, max 33.0085
- Regret by turn: {'1': 1.8558, '2': 1.5836, '3': 1.6281, '4': 1.6007, '5': 1.1978, '6': 1.0366, '7': 1.188, '8': 0.6655, '9': 0.9685, '10': 0.58, '11': 0.5053, '12': 0.0926}

### Worst Decisions

- turn 9 score (rolls_left 0): dice [4, 5, 4, 4, 3], chosen `Fives`, optimal `Yacht`, regret 33.0085, scorecard `[3, 6, 12, 16, None, 18, 12, None, 21, 15, None, None]`
- turn 9 score (rolls_left 0): dice [2, 6, 4, 4, 2], chosen `Threes`, optimal `4 of a Kind`, regret 30.8706, scorecard `[3, 6, None, 16, 15, 18, 20, None, None, 15, None, 0]`
- turn 7 score (rolls_left 0): dice [2, 5, 5, 6, 4], chosen `Sixes`, optimal `Yacht`, regret 23.1061, scorecard `[None, 6, None, 16, 15, None, 17, None, 14, 15, None, None]`
- turn 7 score (rolls_left 0): dice [4, 6, 5, 5, 4], chosen `Sixes`, optimal `Ones`, regret 22.6709, scorecard `[None, 8, None, 8, 20, None, 13, None, 9, None, 30, None]`
- turn 8 score (rolls_left 0): dice [6, 4, 2, 5, 4], chosen `Fives`, optimal `Ones`, regret 22.6618, scorecard `[None, 8, 12, 16, None, None, 18, None, 24, 15, 30, None]`

## optimal

- Avg regret per game: 0.0 (median 0.0)
- Roll decisions: 2365, match 1.0, avg mistake size 0.0, max 0.0
- Score decisions: 1200, match 1.0, avg mistake size 0.0, max 0.0
- Regret by turn: {'1': 0.0, '2': 0.0, '3': 0.0, '4': 0.0, '5': 0.0, '6': 0.0, '7': 0.0, '8': 0.0, '9': 0.0, '10': 0.0, '11': 0.0, '12': 0.0}

### Worst Decisions

- turn 1 roll (rolls_left 2): dice [5, 5, 3, 6, 6], chosen `[6, 6] Keep`, optimal `[6, 6] Keep`, regret 0.0, scorecard `[None, None, None, None, None, None, None, None, None, None, None, None]`
- turn 1 roll (rolls_left 1): dice [1, 1, 5, 6, 6], chosen `[6, 6] Keep`, optimal `[6, 6] Keep`, regret 0.0, scorecard `[None, None, None, None, None, None, None, None, None, None, None, None]`
- turn 1 score (rolls_left 0): dice [3, 5, 4, 6, 6], chosen `Small Straight`, optimal `Small Straight`, regret 0.0, scorecard `[None, None, None, None, None, None, None, None, None, None, None, None]`
- turn 2 roll (rolls_left 2): dice [2, 2, 6, 5, 5], chosen `[5, 5] Keep`, optimal `[5, 5] Keep`, regret 0.0, scorecard `[None, None, None, None, None, None, None, None, None, 15, None, None]`
- turn 2 roll (rolls_left 1): dice [1, 2, 5, 5, 5], chosen `[5, 5, 5] Keep`, optimal `[5, 5, 5] Keep`, regret 0.0, scorecard `[None, None, None, None, None, None, None, None, None, 15, None, None]`
