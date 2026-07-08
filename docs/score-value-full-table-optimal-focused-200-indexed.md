# Score Value Mode Full-game A/B

- Mode: `focused`
- Games: `200` paired seeds
- Seed: `20260708`
- Value table: `artifacts/value/endgame-value-table-open12.npz`
- Random source: `indexed`

## Summary

- heuristic: avg 168.195, stdev 41.3702, upper bonus 0.235, yacht bonus avg 0.04, delta +0.0000
- value: avg 182.6, stdev 52.7507, upper bonus 0.43, yacht bonus avg 0.055, delta +14.4050
- value_optimal: avg 198.645, stdev 54.5957, upper bonus 0.66, yacht bonus avg 0.08, delta +30.4500

## value Details

- Win/loss/tie vs heuristic: 0.63 / 0.365 / 0.005
- Avg score-stage exact table hits per game: 12.0
- Avg score-stage learned hits per game: 0.0
- Avg score-stage fallback turns per game: 0.0
- Delta range: -105 to 167

### Worst Paired Games

- seed 20397932: delta -105, heuristic 271 vs value 166, value scorecard `[1, 4, 6, 8, 20, 18, 17, 23, 24, 15, 30, 0]`
- seed 20300059: delta -102, heuristic 286 vs value 184, value scorecard `[1, 4, 6, 12, 10, 18, 20, 10, 8, 15, 30, 50]`
- seed 20329320: delta -100, heuristic 298 vs value 198, value scorecard `[4, 4, 12, 16, 10, 18, 21, 25, 8, 15, 30, 0]`

### Best Paired Games

- seed 20382797: delta +167, heuristic 208 vs value 375, value scorecard `[2, 2, 6, 12, 20, 24, 27, 22, 30, 15, 30, 150]`
- seed 20264744: delta +151, heuristic 205 vs value 356, value scorecard `[2, 8, 6, 12, 15, 30, 25, 9, 19, 15, 30, 150]`
- seed 20309140: delta +140, heuristic 336 vs value 476, value scorecard `[1, 8, 9, 12, 25, 18, 19, 30, 24, 15, 30, 250]`

## value_optimal Details

- Win/loss/tie vs heuristic: 0.775 / 0.22 / 0.005
- Avg score-stage exact table hits per game: 12.0
- Avg score-stage learned hits per game: 0.0
- Avg score-stage fallback turns per game: 0.0
- Delta range: -86 to 225

### Worst Paired Games

- seed 20329320: delta -86, heuristic 298 vs value_optimal 212, value_optimal scorecard `[4, 8, 9, 12, 10, 18, 14, 18, 24, 15, 30, 50]`
- seed 20452418: delta -55, heuristic 158 vs value_optimal 103, value_optimal scorecard `[2, 4, 6, 16, 0, 24, 18, 0, 18, 15, 0, 0]`
- seed 20362617: delta -54, heuristic 194 vs value_optimal 140, value_optimal scorecard `[2, 4, 9, 8, 15, 18, 25, 14, 0, 15, 30, 0]`

### Best Paired Games

- seed 20290978: delta +225, heuristic 126 vs value_optimal 351, value_optimal scorecard `[0, 4, 15, 12, 20, 18, 23, 13, 16, 15, 30, 150]`
- seed 20419121: delta +191, heuristic 153 vs value_optimal 344, value_optimal scorecard `[1, 10, 12, 8, 20, 12, 26, 25, 0, 15, 30, 150]`
- seed 20382797: delta +172, heuristic 208 vs value_optimal 380, value_optimal scorecard `[1, 8, 6, 12, 20, 24, 27, 22, 30, 15, 30, 150]`
