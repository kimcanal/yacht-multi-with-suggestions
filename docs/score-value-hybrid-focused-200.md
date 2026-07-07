# Score Value Mode Full-game A/B

- Mode: `focused`
- Games: `200` paired seeds
- Seed: `20260708`
- Value table: `artifacts/value/endgame-value-table-open4.json`
- Learned model: `artifacts/models/scorecard-value-linear-v1.json`
- Learned guard: validation MAE <= `25.0`, next turns >= `5`

## Summary

- heuristic: avg 177.635, stdev 44.5676, upper bonus 0.345, yacht bonus avg 0.03, delta +0.0000
- hybrid: avg 168.895, stdev 43.5269, upper bonus 0.365, yacht bonus avg 0.025, delta -8.7400

## hybrid Details

- Win/loss/tie vs heuristic: 0.39 / 0.565 / 0.045
- Avg score-stage exact table hits per game: 5.0
- Avg score-stage learned hits per game: 3.0
- Avg score-stage fallback turns per game: 4.0
- Delta range: -150 to 146
