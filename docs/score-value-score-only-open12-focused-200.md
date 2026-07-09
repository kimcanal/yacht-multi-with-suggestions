# Score Value Mode Full-game A/B

- Mode: `focused`
- Games: `200` paired seeds
- Seed: `20260708`
- Value table: `artifacts/value/endgame-value-table-open12.npz`
- Random source: `stream`

## Summary

- heuristic: avg 175.52, stdev 40.8211, upper bonus 0.42, yacht bonus avg 0.02, delta +0.0000
- value_score_only: avg 184.56, stdev 46.5765, upper bonus 0.54, yacht bonus avg 0.035, delta +9.0400

## value_score_only Details

- Win/loss/tie vs heuristic: 0.585 / 0.31 / 0.105
- Avg score-stage exact table hits per game: 12.0
- Avg score-stage learned hits per game: 0.0
- Avg score-stage fallback turns per game: 0.0
- Delta range: -114 to 182

### Worst Paired Games

- seed 20383806: delta -114, heuristic 250 vs value_score_only 136, value_score_only scorecard `[1, 4, 6, 8, 15, 18, 25, 0, 14, 15, 30, 0]`
- seed 20374725: delta -100, heuristic 337 vs value_score_only 237, value_score_only scorecard `[1, 4, 12, 12, 20, 18, 23, 17, 0, 15, 30, 50]`
- seed 20337392: delta -98, heuristic 248 vs value_score_only 150, value_score_only scorecard `[1, 4, 12, 8, 15, 24, 23, 0, 13, 15, 0, 0]`

### Best Paired Games

- seed 20333356: delta +182, heuristic 174 vs value_score_only 356, value_score_only scorecard `[1, 4, 6, 20, 15, 18, 22, 17, 23, 15, 30, 150]`
- seed 20332347: delta +169, heuristic 202 vs value_score_only 371, value_score_only scorecard `[2, 2, 15, 8, 20, 24, 23, 26, 21, 15, 30, 150]`
- seed 20362617: delta +141, heuristic 204 vs value_score_only 345, value_score_only scorecard `[2, 4, 15, 12, 20, 18, 22, 22, 0, 15, 30, 150]`
