# Score Value Mode Full-game A/B

- Mode: `focused`
- Games: `200` paired seeds
- Seed: `20260708`
- Value table: `artifacts/value/endgame-value-table-open4.json`
- Random source: `indexed`

## Summary

- heuristic: avg 168.195, stdev 41.3702, upper bonus 0.235, yacht bonus avg 0.04, delta +0.0000
- value_score_only: avg 170.57, stdev 41.0715, upper bonus 0.305, yacht bonus avg 0.035, delta +2.3750

## value_score_only Details

- Win/loss/tie vs heuristic: 0.305 / 0.255 / 0.44
- Avg score-stage exact table hits per game: 5.0
- Avg score-stage learned hits per game: 0.0
- Avg score-stage fallback turns per game: 7.0
- Delta range: -98 to 53

### Worst Paired Games

- seed 20329320: delta -98, heuristic 298 vs value_score_only 200, value_score_only scorecard `[2, 8, 12, 8, 10, 18, 23, 0, 24, 15, 30, 50]`
- seed 20392887: delta -28, heuristic 215 vs value_score_only 187, value_score_only scorecard `[0, 6, 9, 8, 20, 18, 15, 24, 22, 15, 0, 50]`
- seed 20391878: delta -27, heuristic 317 vs value_score_only 290, value_score_only scorecard `[1, 0, 6, 16, 15, 12, 25, 0, 20, 15, 30, 150]`

### Best Paired Games

- seed 20331338: delta +53, heuristic 148 vs value_score_only 201, value_score_only scorecard `[0, 4, 3, 12, 20, 6, 22, 22, 17, 15, 30, 50]`
- seed 20446364: delta +47, heuristic 138 vs value_score_only 185, value_score_only scorecard `[1, 6, 6, 12, 15, 24, 23, 0, 18, 15, 30, 0]`
- seed 20387842: delta +45, heuristic 206 vs value_score_only 251, value_score_only scorecard `[0, 6, 9, 16, 15, 18, 19, 25, 13, 15, 30, 50]`
