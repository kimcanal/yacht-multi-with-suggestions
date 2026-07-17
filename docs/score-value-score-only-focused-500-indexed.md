# Score Value Mode Full-game A/B

- Mode: `focused`
- Games: `500` paired seeds
- Seed: `20260708`
- Value table: `artifacts/runtime/value/endgame-value-table-open4.json`
- Random source: `indexed`

## Summary

- heuristic: avg 171.032, stdev 45.0653, upper bonus 0.25, yacht bonus avg 0.044, delta +0.0000
- value_score_only: avg 174.346, stdev 45.9242, upper bonus 0.338, yacht bonus avg 0.044, delta +3.3140

## value_score_only Details

- Win/loss/tie vs heuristic: 0.278 / 0.254 / 0.468
- Avg score-stage exact table hits per game: 5.0
- Avg score-stage learned hits per game: 0.0
- Avg score-stage fallback turns per game: 7.0
- Delta range: -98 to 156

### Worst Paired Games

- seed 20329320: delta -98, heuristic 298 vs value_score_only 200, value_score_only scorecard `[2, 8, 12, 8, 10, 18, 23, 0, 24, 15, 30, 50]`
- seed 20546255: delta -48, heuristic 175 vs value_score_only 127, value_score_only scorecard `[2, 4, 6, 8, 15, 24, 24, 29, 0, 15, 0, 0]`
- seed 20594687: delta -30, heuristic 231 vs value_score_only 201, value_score_only scorecard `[3, 6, 9, 8, 15, 24, 15, 0, 21, 15, 0, 50]`

### Best Paired Games

- seed 20654218: delta +156, heuristic 150 vs value_score_only 306, value_score_only scorecard `[3, 2, 3, 16, 15, 24, 23, 0, 20, 15, 0, 150]`
- seed 20747046: delta +57, heuristic 148 vs value_score_only 205, value_score_only scorecard `[0, 2, 6, 12, 15, 18, 21, 25, 11, 15, 30, 50]`
- seed 20615876: delta +53, heuristic 155 vs value_score_only 208, value_score_only scorecard `[1, 4, 9, 12, 20, 24, 17, 22, 19, 15, 30, 0]`
