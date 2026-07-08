# Score Value Paired-case Analysis

- Source report: `artifacts/reports/score-value-score-only-focused-200-indexed.json`
- Mode: `focused`
- Games: `200` paired seeds
- Seed: `20260708`
- Value table: `artifacts/value/endgame-value-table-open4.json`
- Random source: `indexed`

## value_score_only

- Full-run average: heuristic 168.195 vs value_score_only 170.57 (+2.3750); win/loss/tie: 0.305 / 0.255 / 0.44
- Paired delta uncertainty: n=200, sample stdev 14.9308, stderr 1.0558, normal 95% CI [0.3057, 4.4443]
- Upper bonus rate: heuristic 0.235 vs value_score_only 0.305; avg exact table hits per game 5.0

### Saved Worst Cases

- Cases: 5; avg delta -41.0000; range -98 to -26
- Upper bonus delta sum +0; Yacht bonus delta sum -1; avg zero-category delta +0.8000
- First split turns: 10 (2), 9 (2), 8 (1)
- First split pairs: Fives -> 4 of a Kind (1), Twos -> Large Straight (1), 4 of a Kind -> Full House (1), Fours -> Ones (1), Fives -> Ones (1)

- seed 20329320: delta -98, heuristic 298 vs value_score_only 200; first split turn 10 Fives(5) -> 4 of a Kind(0); upper bonus delta +0, yacht bonus delta -1
- seed 20392887: delta -28, heuristic 215 vs value_score_only 187; first split turn 10 Twos(4) -> Large Straight(0); upper bonus delta +0, yacht bonus delta +0
- seed 20391878: delta -27, heuristic 317 vs value_score_only 290; first split turn 9 4 of a Kind(20) -> Full House(20); upper bonus delta +0, yacht bonus delta +0
- seed 20287951: delta -26, heuristic 151 vs value_score_only 125; first split turn 9 Fours(4) -> Ones(1); upper bonus delta +0, yacht bonus delta +0
- seed 20297032: delta -26, heuristic 211 vs value_score_only 185; first split turn 8 Fives(10) -> Ones(1); upper bonus delta +0, yacht bonus delta +0

### Saved Best Cases

- Cases: 5; avg delta +46.6000; range 44 to 53
- Upper bonus delta sum +2; Yacht bonus delta sum +0; avg zero-category delta -0.2000
- First split turns: 10 (2), 8 (2), 9 (1)
- First split pairs: Yacht -> Ones (2), Fives -> Yacht (1), Fours -> Yacht (1), Threes -> Yacht (1)

- seed 20331338: delta +53, heuristic 148 vs value_score_only 201; first split turn 10 Yacht(0) -> Ones(0); upper bonus delta +0, yacht bonus delta +0
- seed 20446364: delta +47, heuristic 138 vs value_score_only 185; first split turn 8 Fives(10) -> Yacht(0); upper bonus delta +1, yacht bonus delta +0
- seed 20387842: delta +45, heuristic 206 vs value_score_only 251; first split turn 10 Yacht(0) -> Ones(0); upper bonus delta +0, yacht bonus delta +0
- seed 20415085: delta +44, heuristic 191 vs value_score_only 235; first split turn 9 Fours(20) -> Yacht(50); upper bonus delta +0, yacht bonus delta +0
- seed 20380779: delta +44, heuristic 120 vs value_score_only 164; first split turn 8 Threes(3) -> Yacht(0); upper bonus delta +1, yacht bonus delta +0
