# AI Decision Regret vs Exact Optimal

- Games per policy: `100`
- Seed: `20260709` / random source: `indexed`
- Value table: `artifacts/value/endgame-value-table-open12.npz`
- Metric: regret = Q*(best action) - Q*(chosen action), in expected final-score points

## Summary

| policy | avg score | avg regret/game | roll match | score match | roll avg regret | score avg regret |
|---|---|---|---|---|---|---|
| focused | 176.01 | 20.8927 | 0.705 | 0.7975 | 0.4129 | 0.9234 |

## focused

- Avg regret per game: 20.8927 (median 20.7992)
- Roll decisions: 2376, match 0.705, avg mistake size 1.3996, max 9.9884
- Score decisions: 1200, match 0.7975, avg mistake size 4.5602, max 29.8054
- Regret by turn: {'1': 1.028, '2': 1.1414, '3': 0.8467, '4': 0.93, '5': 0.6022, '6': 0.6084, '7': 0.5479, '8': 0.5094, '9': 0.2888, '10': 0.3078, '11': 0.1653, '12': 0.0292}

### Worst Decisions

- turn 10 score (rolls_left 0): dice [6, 6, 5, 5, 6], chosen `Threes`, optimal `4 of a Kind`, regret 29.8054, scorecard `[2, 6, None, 16, 15, 18, 22, None, 24, 15, None, 0]`
- turn 2 score (rolls_left 0): dice [1, 4, 5, 1, 6], chosen `Sixes`, optimal `Ones`, regret 17.2119, scorecard `[None, None, None, None, None, None, 24, None, None, None, None, None]`
- turn 4 score (rolls_left 0): dice [6, 5, 3, 6, 1], chosen `Sixes`, optimal `Ones`, regret 14.5993, scorecard `[None, None, None, 16, 15, None, 21, None, None, None, None, None]`
- turn 7 score (rolls_left 0): dice [1, 5, 5, 6, 3], chosen `Fives`, optimal `Yacht`, regret 14.3543, scorecard `[None, None, 12, 12, None, 18, 20, 10, None, 15, None, None]`
- turn 8 score (rolls_left 0): dice [5, 2, 5, 5, 5], chosen `Twos`, optimal `4 of a Kind`, regret 13.5912, scorecard `[None, None, 12, 12, 20, 18, 21, None, None, 15, None, 50]`
