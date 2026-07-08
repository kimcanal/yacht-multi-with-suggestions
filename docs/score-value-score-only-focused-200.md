# Score Value Mode Full-game A/B

- Mode: `focused`
- Games: `200` paired seeds
- Seed: `20260708`
- Value table: `artifacts/value/endgame-value-table-open4.json`

## Summary

- heuristic: avg 177.635, stdev 44.5676, upper bonus 0.345, yacht bonus avg 0.03, delta +0.0000
- value_score_only: avg 177.65, stdev 44.7589, upper bonus 0.39, yacht bonus avg 0.03, delta +0.0150

## value_score_only Details

- Win/loss/tie vs heuristic: 0.21 / 0.28 / 0.51
- Avg score-stage exact table hits per game: 5.0
- Avg score-stage learned hits per game: 0.0
- Avg score-stage fallback turns per game: 7.0
- Delta range: -77 to 104

### Worst Paired Games

- seed 20310149: delta -77, heuristic 297 vs value_score_only 220, value_score_only scorecard `[2, 2, 9, 4, 10, 24, 20, 28, 26, 15, 30, 50]`
- seed 20434256: delta -72, heuristic 185 vs value_score_only 113, value_score_only scorecard `[0, 8, 3, 4, 10, 18, 15, 10, 0, 15, 30, 0]`
- seed 20277861: delta -40, heuristic 182 vs value_score_only 142, value_score_only scorecard `[0, 4, 9, 12, 15, 18, 21, 7, 11, 15, 30, 0]`

### Best Paired Games

- seed 20450400: delta +104, heuristic 222 vs value_score_only 326, value_score_only scorecard `[1, 6, 12, 20, 15, 18, 25, 29, 0, 15, 0, 150]`
- seed 20409031: delta +49, heuristic 136 vs value_score_only 185, value_score_only scorecard `[3, 4, 12, 12, 15, 18, 23, 0, 18, 15, 30, 0]`
- seed 20338401: delta +43, heuristic 150 vs value_score_only 193, value_score_only scorecard `[3, 6, 6, 16, 20, 18, 20, 0, 24, 15, 30, 0]`
