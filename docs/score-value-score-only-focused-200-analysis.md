# Score Value Paired-case Analysis

- Source report: `artifacts/reference/reports/score-value-score-only-focused-200.json`
- Mode: `focused`
- Games: `200` paired seeds
- Seed: `20260708`
- Value table: `artifacts/runtime/value/endgame-value-table-open4.json`
- Random source: `stream`

## value_score_only

- Full-run average: heuristic 177.635 vs value_score_only 177.65 (+0.0150); win/loss/tie: 0.21 / 0.28 / 0.51
- Paired delta uncertainty: n=200, sample stdev 14.9463, stderr 1.0569, normal 95% CI [-2.0565, 2.0865]
- Objective tests: z=0.0142, one-sided normal p=0.494338, two-sided normal p=0.988676, effect dz=0.001
- Sign test: win/loss/tie counts 42 / 56 / 102; one-sided p=0.935354, two-sided p=0.188847
- Upper bonus rate: heuristic 0.345 vs value_score_only 0.39; avg exact table hits per game 5.0

### Saved Worst Cases

- Cases: 5; avg delta -51.6000; range -77 to -30
- Upper bonus delta sum +0; Yacht bonus delta sum -1; avg zero-category delta +0.8000
- First split turns: 8 (3), 9 (1), 11 (1)
- First split pairs: Fours -> Ones (1), 4 of a Kind -> Twos (1), Fives -> Twos (1), Threes -> Ones (1), Full House -> Large Straight (1)

- seed 20310149: delta -77, heuristic 297 vs value_score_only 220; first split turn 9 Fours(8) -> Ones(2); upper bonus delta +0, yacht bonus delta -1
- seed 20434256: delta -72, heuristic 185 vs value_score_only 113; first split turn 8 4 of a Kind(13) -> Twos(8); upper bonus delta +0, yacht bonus delta +0
- seed 20277861: delta -40, heuristic 182 vs value_score_only 142; first split turn 8 Fives(10) -> Twos(4); upper bonus delta +0, yacht bonus delta +0
- seed 20269789: delta -39, heuristic 239 vs value_score_only 200; first split turn 8 Threes(6) -> Ones(1); upper bonus delta +0, yacht bonus delta +0
- seed 20449391: delta -30, heuristic 340 vs value_score_only 310; first split turn 11 Full House(0) -> Large Straight(0); upper bonus delta +0, yacht bonus delta +0

### Saved Best Cases

- Cases: 5; avg delta +55.4000; range 39 to 104
- Upper bonus delta sum +4; Yacht bonus delta sum +1; avg zero-category delta +0.2000
- First split turns: 9 (3), 8 (2)
- First split pairs: Fours -> Yacht (2), Fours -> Large Straight (1), Yacht -> Ones (1), Twos -> Yacht (1)

- seed 20450400: delta +104, heuristic 222 vs value_score_only 326; first split turn 8 Fours(8) -> Large Straight(0); upper bonus delta +1, yacht bonus delta +1
- seed 20409031: delta +49, heuristic 136 vs value_score_only 185; first split turn 9 Fours(4) -> Yacht(0); upper bonus delta +1, yacht bonus delta +0
- seed 20338401: delta +43, heuristic 150 vs value_score_only 193; first split turn 9 Fours(8) -> Yacht(0); upper bonus delta +1, yacht bonus delta +0
- seed 20304095: delta +42, heuristic 221 vs value_score_only 263; first split turn 8 Yacht(0) -> Ones(0); upper bonus delta +0, yacht bonus delta +0
- seed 20361608: delta +39, heuristic 161 vs value_score_only 200; first split turn 9 Twos(4) -> Yacht(0); upper bonus delta +1, yacht bonus delta +0
