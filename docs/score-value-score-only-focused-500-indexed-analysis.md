# Score Value Paired-case Analysis

- Source report: `artifacts/reports/score-value-score-only-focused-500-indexed.json`
- Mode: `focused`
- Games: `500` paired seeds
- Seed: `20260708`
- Value table: `artifacts/value/endgame-value-table-open4.json`
- Random source: `indexed`

## value_score_only

- Full-run average: heuristic 171.032 vs value_score_only 174.346 (+3.3140); win/loss/tie: 0.278 / 0.254 / 0.468
- Paired delta uncertainty: n=500, sample stdev 15.955, stderr 0.7135, normal 95% CI [1.9155, 4.7125]
- Upper bonus rate: heuristic 0.25 vs value_score_only 0.338; avg exact table hits per game 5.0

### Saved Worst Cases

- Cases: 5; avg delta -46.8000; range -98 to -28
- Upper bonus delta sum +0; Yacht bonus delta sum -1; avg zero-category delta +1.0000
- First split turns: 10 (2), 11 (2), 8 (1)
- First split pairs: Fives -> 4 of a Kind (1), Ones -> Yacht (1), 4 of a Kind -> Large Straight (1), Full House -> Large Straight (1), Twos -> Large Straight (1)

- seed 20329320: delta -98, heuristic 298 vs value_score_only 200; first split turn 10 Fives(5) -> 4 of a Kind(0); upper bonus delta +0, yacht bonus delta -1
- seed 20546255: delta -48, heuristic 175 vs value_score_only 127; first split turn 8 Ones(1) -> Yacht(0); upper bonus delta +0, yacht bonus delta +0
- seed 20594687: delta -30, heuristic 231 vs value_score_only 201; first split turn 11 4 of a Kind(0) -> Large Straight(0); upper bonus delta +0, yacht bonus delta +0
- seed 20701641: delta -30, heuristic 198 vs value_score_only 168; first split turn 11 Full House(0) -> Large Straight(0); upper bonus delta +0, yacht bonus delta +0
- seed 20392887: delta -28, heuristic 215 vs value_score_only 187; first split turn 10 Twos(4) -> Large Straight(0); upper bonus delta +0, yacht bonus delta +0

### Saved Best Cases

- Cases: 5; avg delta +73.6000; range 49 to 156
- Upper bonus delta sum +3; Yacht bonus delta sum +1; avg zero-category delta +0.0000
- First split turns: 8 (3), 9 (1), 10 (1)
- First split pairs: Sixes -> Ones (2), Ones -> Large Straight (1), Fives -> Threes (1), Yacht -> Ones (1)

- seed 20654218: delta +156, heuristic 150 vs value_score_only 306; first split turn 9 Ones(2) -> Large Straight(0); upper bonus delta +1, yacht bonus delta +1
- seed 20747046: delta +57, heuristic 148 vs value_score_only 205; first split turn 8 Fives(10) -> Threes(6); upper bonus delta +0, yacht bonus delta +0
- seed 20615876: delta +53, heuristic 155 vs value_score_only 208; first split turn 8 Sixes(12) -> Ones(1); upper bonus delta +1, yacht bonus delta +0
- seed 20331338: delta +53, heuristic 148 vs value_score_only 201; first split turn 10 Yacht(0) -> Ones(0); upper bonus delta +0, yacht bonus delta +0
- seed 20692560: delta +49, heuristic 155 vs value_score_only 204; first split turn 8 Sixes(6) -> Ones(0); upper bonus delta +1, yacht bonus delta +0
