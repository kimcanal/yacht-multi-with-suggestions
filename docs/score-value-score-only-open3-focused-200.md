# Score Value Mode Full-game A/B

- Mode: `focused`
- Games: `200` paired seeds
- Seed: `20260708`
- Value table: `artifacts/runtime/value/endgame-value-table-open3.json`

## Summary

- heuristic: avg 177.635, stdev 44.5676, upper bonus 0.345, yacht bonus avg 0.03, delta +0.0000
- value_score_only: avg 177.155, stdev 42.6245, upper bonus 0.355, yacht bonus avg 0.025, delta -0.4800

## value_score_only Details

- Win/loss/tie vs heuristic: 0.095 / 0.22 / 0.685
- Avg score-stage exact table hits per game: 4.0
- Avg score-stage learned hits per game: 0.0
- Avg score-stage fallback turns per game: 8.0
- Delta range: -77 to 49

### Worst Paired Games

- seed 20310149: delta -77, heuristic 297 vs value_score_only 220, value_score_only scorecard `[2, 2, 9, 4, 10, 24, 20, 28, 26, 15, 30, 50]`
- seed 20416094: delta -52, heuristic 212 vs value_score_only 160, value_score_only scorecard `[1, 6, 6, 12, 15, 18, 21, 0, 16, 15, 0, 50]`
- seed 20449391: delta -30, heuristic 340 vs value_score_only 310, value_score_only scorecard `[2, 8, 6, 20, 15, 12, 24, 23, 0, 15, 0, 150]`

### Best Paired Games

- seed 20409031: delta +49, heuristic 136 vs value_score_only 185, value_score_only scorecard `[3, 4, 12, 12, 15, 18, 23, 0, 18, 15, 30, 0]`
- seed 20338401: delta +43, heuristic 150 vs value_score_only 193, value_score_only scorecard `[3, 6, 6, 16, 20, 18, 20, 0, 24, 15, 30, 0]`
- seed 20361608: delta +39, heuristic 161 vs value_score_only 200, value_score_only scorecard `[2, 6, 12, 16, 10, 18, 20, 22, 14, 15, 30, 0]`
