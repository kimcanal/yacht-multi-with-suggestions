# AI Decision Regret vs Exact Optimal

- Games per policy: `100`
- Seed: `20260709` / random source: `indexed`
- Value table: `artifacts/value/endgame-value-table-open12.npz`
- Metric: regret = Q*(best action) - Q*(chosen action), in expected final-score points

## Summary

| policy | avg score | avg regret/game | roll match | score match | roll avg regret | score avg regret |
|---|---|---|---|---|---|---|
| focused | 176.38 | 20.563 | 0.7058 | 0.7983 | 0.4116 | 0.8986 |

## focused

- Avg regret per game: 20.563 (median 20.7424)
- Roll decisions: 2376, match 0.7058, avg mistake size 1.3991, max 9.9884
- Score decisions: 1200, match 0.7983, avg mistake size 4.4559, max 17.2119
- Regret by turn: {'1': 1.028, '2': 1.1414, '3': 0.8467, '4': 0.93, '5': 0.6022, '6': 0.6084, '7': 0.5479, '8': 0.5094, '9': 0.2888, '10': 0.2078, '11': 0.1547, '12': 0.0292}

### Worst Decisions

- turn 2 score (rolls_left 0): dice [1, 4, 5, 1, 6], chosen `Sixes`, optimal `Ones`, regret 17.2119, scorecard `[None, None, None, None, None, None, 24, None, None, None, None, None]`
- turn 4 score (rolls_left 0): dice [6, 5, 3, 6, 1], chosen `Sixes`, optimal `Ones`, regret 14.5993, scorecard `[None, None, None, 16, 15, None, 21, None, None, None, None, None]`
- turn 7 score (rolls_left 0): dice [1, 5, 5, 6, 3], chosen `Fives`, optimal `Yacht`, regret 14.3543, scorecard `[None, None, 12, 12, None, 18, 20, 10, None, 15, None, None]`
- turn 8 score (rolls_left 0): dice [5, 2, 5, 5, 5], chosen `Twos`, optimal `4 of a Kind`, regret 13.5912, scorecard `[None, None, 12, 12, 20, 18, 21, None, None, 15, None, 50]`
- turn 3 score (rolls_left 0): dice [6, 6, 5, 5, 6], chosen `Sixes`, optimal `Full House`, regret 13.0735, scorecard `[None, None, None, None, 15, None, 23, None, None, None, None, None]`
