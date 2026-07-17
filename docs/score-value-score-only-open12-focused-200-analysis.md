# Score Value Paired-case Analysis

- Source report: `artifacts/reference/reports/score-value-score-only-open12-focused-200.json`
- Mode: `focused`
- Games: `200` paired seeds
- Seed: `20260708`
- Value table: `artifacts/runtime/value/endgame-value-table-open12.npz`
- Random source: `stream`

## value_score_only

- Full-run average: heuristic 175.52 vs value_score_only 184.56 (+9.0400); win/loss/tie: 0.585 / 0.31 / 0.105
- Paired delta uncertainty: n=200, sample stdev 40.48, stderr 2.8624, normal 95% CI [3.4298, 14.6502]
- Objective tests: z=3.1582, one-sided normal p=0.000794, two-sided normal p=0.001587, effect dz=0.2233
- Sign test: win/loss/tie counts 117 / 62 / 21; one-sided p=2.39e-05, two-sided p=4.79e-05
- Upper bonus rate: heuristic 0.42 vs value_score_only 0.54; avg exact table hits per game 12.0

### Saved Worst Cases

- Cases: 5; avg delta -98.4000; range -114 to -82
- Upper bonus delta sum -2; Yacht bonus delta sum -2; avg zero-category delta +0.8000
- First split turns: 1 (2), 3 (1), 2 (1), 6 (1)
- First split pairs: Choice -> Small Straight (2), Choice -> Twos (1), Fives -> Ones (1), Choice -> Ones (1)

- seed 20383806: delta -114, heuristic 250 vs value_score_only 136; first split turn 1 Choice(23) -> Small Straight(15); upper bonus delta -1, yacht bonus delta +0
- seed 20374725: delta -100, heuristic 337 vs value_score_only 237; first split turn 3 Choice(24) -> Small Straight(15); upper bonus delta +0, yacht bonus delta -1
- seed 20337392: delta -98, heuristic 248 vs value_score_only 150; first split turn 1 Choice(14) -> Twos(4); upper bonus delta +0, yacht bonus delta +0
- seed 20447373: delta -98, heuristic 232 vs value_score_only 134; first split turn 2 Fives(10) -> Ones(1); upper bonus delta -1, yacht bonus delta +0
- seed 20450400: delta -82, heuristic 368 vs value_score_only 286; first split turn 6 Choice(15) -> Ones(1); upper bonus delta +0, yacht bonus delta -1

### Saved Best Cases

- Cases: 5; avg delta +146.0000; range 114 to 182
- Upper bonus delta sum +2; Yacht bonus delta sum +5; avg zero-category delta -0.4000
- First split turns: 1 (1), 2 (1), 7 (1), 3 (1), 6 (1)
- First split pairs: Choice -> Small Straight (1), Choice -> Ones (1), Twos -> Full House (1), Sixes -> Full House (1), Threes -> Ones (1)

- seed 20333356: delta +182, heuristic 174 vs value_score_only 356; first split turn 1 Choice(24) -> Small Straight(15); upper bonus delta +1, yacht bonus delta +1
- seed 20332347: delta +169, heuristic 202 vs value_score_only 371; first split turn 2 Choice(14) -> Ones(2); upper bonus delta +0, yacht bonus delta +1
- seed 20362617: delta +141, heuristic 204 vs value_score_only 345; first split turn 7 Twos(2) -> Full House(0); upper bonus delta +1, yacht bonus delta +1
- seed 20304095: delta +124, heuristic 221 vs value_score_only 345; first split turn 3 Sixes(18) -> Full House(28); upper bonus delta +0, yacht bonus delta +1
- seed 20399950: delta +114, heuristic 202 vs value_score_only 316; first split turn 6 Threes(3) -> Ones(0); upper bonus delta +0, yacht bonus delta +1
