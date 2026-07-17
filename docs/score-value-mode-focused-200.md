# Score Value Mode Full-game A/B

- Mode: `focused`
- Games: `200` paired seeds
- Seed: `20260708`
- Value table: `artifacts/runtime/value/endgame-value-table-open4.json`

## Summary

- heuristic: avg 177.635, stdev 44.5676, upper bonus 0.345, yacht bonus avg 0.03, delta +0.0000
- value: avg 178.44, stdev 47.9419, upper bonus 0.405, yacht bonus avg 0.035, delta +0.8050

## value Details

- Win/loss/tie vs heuristic: 0.305 / 0.37 / 0.325
- Avg score-stage exact table hits per game: 5.0
- Avg score-stage learned hits per game: 0.0
- Avg score-stage fallback turns per game: 7.0
- Delta range: -72 to 193

### Worst Paired Games

- seed 20310149: delta -72, heuristic 297 vs value 225, value scorecard `[1, 4, 9, 8, 10, 24, 20, 28, 26, 15, 30, 50]`
- seed 20434256: delta -72, heuristic 185 vs value 113, value scorecard `[0, 8, 3, 4, 10, 18, 15, 10, 0, 15, 30, 0]`
- seed 20285933: delta -71, heuristic 192 vs value 121, value scorecard `[1, 2, 6, 12, 20, 18, 17, 0, 0, 15, 30, 0]`

### Best Paired Games

- seed 20339410: delta +193, heuristic 263 vs value 456, value scorecard `[3, 0, 9, 12, 15, 24, 30, 25, 8, 15, 30, 250]`
- seed 20415085: delta +55, heuristic 131 vs value 186, value scorecard `[3, 8, 9, 12, 15, 18, 25, 0, 16, 15, 30, 0]`
- seed 20361608: delta +51, heuristic 161 vs value 212, value scorecard `[2, 6, 12, 16, 10, 18, 20, 22, 26, 15, 30, 0]`
