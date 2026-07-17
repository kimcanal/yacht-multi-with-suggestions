# AI Decision Regret vs Exact Optimal

- Games per policy: `100`
- Seed: `20260709` / random source: `indexed`
- Value table: `artifacts/runtime/value/endgame-value-table-open12.npz`
- Metric: regret = Q*(best action) - Q*(chosen action), in expected final-score points

## Summary

| policy | avg score | avg regret/game | roll match | score match | roll avg regret | score avg regret |
|---|---|---|---|---|---|---|
| focused | 177.77 | 19.4909 | 0.7009 | 0.81 | 0.4386 | 0.7554 |
| value_score_only | 187.48 | 10.3907 | 0.7011 | 1.0 | 0.4368 | 0.0 |

## focused

- Avg regret per game: 19.4909 (median 18.7215)
- Roll decisions: 2377, match 0.7009, avg mistake size 1.4664, max 9.9884
- Score decisions: 1200, match 0.81, avg mistake size 3.9756, max 13.5912
- Regret by turn: {'1': 0.9026, '2': 0.9687, '3': 0.7972, '4': 0.7676, '5': 0.6335, '6': 0.5914, '7': 0.4658, '8': 0.573, '9': 0.3836, '10': 0.2489, '11': 0.1742, '12': 0.0295}

### Worst Decisions

- turn 8 score (rolls_left 0): dice [5, 2, 5, 5, 5], chosen `Twos`, optimal `4 of a Kind`, regret 13.5912, scorecard `[None, None, 12, 12, 20, 18, 21, None, None, 15, None, 50]`
- turn 6 score (rolls_left 0): dice [6, 6, 5, 5, 6], chosen `Sixes`, optimal `Full House`, regret 13.4707, scorecard `[None, None, 3, None, 15, None, 24, None, None, 15, 30, None]`
- turn 10 score (rolls_left 0): dice [2, 6, 3, 1, 3], chosen `Threes`, optimal `Yacht`, regret 13.3815, scorecard `[2, 2, None, 8, 20, 24, 22, None, 22, 15, 30, None]`
- turn 3 score (rolls_left 0): dice [6, 6, 5, 5, 6], chosen `Sixes`, optimal `Full House`, regret 13.0735, scorecard `[None, None, None, None, 15, None, 15, None, None, None, None, None]`
- turn 3 score (rolls_left 0): dice [5, 6, 6, 6, 5], chosen `Sixes`, optimal `Full House`, regret 12.883, scorecard `[2, None, None, None, 15, None, None, None, None, None, None, None]`

## value_score_only

- Avg regret per game: 10.3907 (median 10.2293)
- Roll decisions: 2379, match 0.7011, avg mistake size 1.4614, max 7.8718
- Score decisions: 1200, match 1.0, avg mistake size 0.0, max 0.0
- Regret by turn: {'1': 0.4285, '2': 0.4286, '3': 0.4019, '4': 0.4755, '5': 0.4011, '6': 0.3077, '7': 0.2735, '8': 0.2852, '9': 0.1783, '10': 0.1345, '11': 0.1285, '12': 0.0403}

### Worst Decisions

- turn 9 roll (rolls_left 2): dice [5, 6, 6, 5, 5], chosen `[6, 6] Keep`, optimal `지금 기록, 지금 기록`, regret 7.8718, scorecard `[1, 6, 6, 12, 15, None, 26, None, None, 15, 30, None]`
- turn 3 roll (rolls_left 1): dice [2, 1, 6, 2, 2], chosen `[6] Keep`, optimal `[2, 2, 2] Keep`, regret 7.7977, scorecard `[None, None, None, 12, None, None, None, None, None, None, 30, None]`
- turn 2 roll (rolls_left 1): dice [3, 5, 3, 3, 4], chosen `[3, 4, 5] Keep`, optimal `[3, 3, 3] Keep`, regret 7.7326, scorecard `[1, None, None, None, None, None, None, None, None, None, None, None]`
- turn 7 roll (rolls_left 2): dice [4, 1, 6, 1, 1], chosen `[6] Keep`, optimal `[1, 1, 1] Keep`, regret 7.6445, scorecard `[None, None, 12, 12, 20, None, 21, None, None, 15, None, 50]`
- turn 6 roll (rolls_left 1): dice [6, 6, 3, 1, 6], chosen `[3] Keep`, optimal `[6, 6, 6] Keep`, regret 7.5902, scorecard `[4, 8, None, 16, 15, 18, None, None, None, None, None, None]`
