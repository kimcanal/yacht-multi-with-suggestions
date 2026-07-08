# Score Value Paired-case Analysis

- Source report: `artifacts/reports/score-value-full-table-optimal-focused-200-indexed.json`
- Mode: `focused`
- Games: `200` paired seeds
- Seed: `20260708`
- Value table: `artifacts/value/endgame-value-table-open12.npz`
- Random source: `indexed`

## value

- Full-run average: heuristic 168.195 vs value 182.6 (+14.4050); win/loss/tie: 0.63 / 0.365 / 0.005
- Paired delta uncertainty: n=200, sample stdev 42.6111, stderr 3.0131, normal 95% CI [8.4994, 20.3106]
- Objective tests: z=4.7808, one-sided normal p=8.73e-07, two-sided normal p=1.75e-06, effect dz=0.3381
- Sign test: win/loss/tie counts 126 / 73 / 1; one-sided p=0.000105, two-sided p=0.00021
- Upper bonus rate: heuristic 0.235 vs value 0.43; avg exact table hits per game 12.0

### Saved Worst Cases

- Cases: 5; avg delta -97.8000; range -105 to -87
- Upper bonus delta sum -1; Yacht bonus delta sum -3; avg zero-category delta -0.4000
- First split turns: 1 (4), 2 (1)
- First split pairs: Sixes -> Threes (1), Choice -> Twos (1), Choice -> Ones (1), Yacht -> Small Straight (1), Choice -> Small Straight (1)

- seed 20397932: delta -105, heuristic 271 vs value 166; first split turn 2 Sixes(24) -> Threes(6); upper bonus delta -1, yacht bonus delta +0
- seed 20300059: delta -102, heuristic 286 vs value 184; first split turn 1 Choice(12) -> Twos(4); upper bonus delta +0, yacht bonus delta -1
- seed 20329320: delta -100, heuristic 298 vs value 198; first split turn 1 Choice(23) -> Ones(4); upper bonus delta +1, yacht bonus delta -1
- seed 20394905: delta -95, heuristic 279 vs value 184; first split turn 1 Yacht(50) -> Small Straight(15); upper bonus delta -1, yacht bonus delta -1
- seed 20338401: delta -87, heuristic 220 vs value 133; first split turn 1 Choice(23) -> Small Straight(15); upper bonus delta +0, yacht bonus delta +0

### Saved Best Cases

- Cases: 5; avg delta +141.0000; range 119 to 167
- Upper bonus delta sum +2; Yacht bonus delta sum +5; avg zero-category delta -0.6000
- First split turns: 3 (3), 1 (1), 2 (1)
- First split pairs: Sixes -> Small Straight (2), Sixes -> Ones (1), Fives -> Full House (1), Choice -> Small Straight (1)

- seed 20382797: delta +167, heuristic 208 vs value 375; first split turn 1 Sixes(12) -> Ones(2); upper bonus delta +0, yacht bonus delta +1
- seed 20264744: delta +151, heuristic 205 vs value 356; first split turn 3 Fives(15) -> Full House(19); upper bonus delta +1, yacht bonus delta +1
- seed 20309140: delta +140, heuristic 336 vs value 476; first split turn 2 Choice(23) -> Small Straight(15); upper bonus delta +0, yacht bonus delta +1
- seed 20426184: delta +128, heuristic 328 vs value 456; first split turn 3 Sixes(18) -> Small Straight(15); upper bonus delta +1, yacht bonus delta +1
- seed 20403986: delta +119, heuristic 234 vs value 353; first split turn 3 Sixes(18) -> Small Straight(15); upper bonus delta +0, yacht bonus delta +1

## value_optimal

- Full-run average: heuristic 168.195 vs value_optimal 198.645 (+30.4500); win/loss/tie: 0.775 / 0.22 / 0.005
- Paired delta uncertainty: n=200, sample stdev 44.1369, stderr 3.121, normal 95% CI [24.3329, 36.5671]
- Objective tests: z=9.7566, one-sided normal p=8.64e-23, two-sided normal p=1.73e-22, effect dz=0.6899
- Sign test: win/loss/tie counts 155 / 44 / 1; one-sided p=5.35e-16, two-sided p=1.07e-15
- Upper bonus rate: heuristic 0.235 vs value_optimal 0.66; avg exact table hits per game 12.0

### Saved Worst Cases

- Cases: 5; avg delta -59.2000; range -86 to -47
- Upper bonus delta sum -1; Yacht bonus delta sum -1; avg zero-category delta +0.8000
- First split turns: 1 (4), 3 (1)
- First split pairs: Choice -> Ones (2), Choice -> Twos (1), Choice -> Threes (1), Sixes -> Twos (1)

- seed 20329320: delta -86, heuristic 298 vs value_optimal 212; first split turn 1 Choice(23) -> Ones(4); upper bonus delta +0, yacht bonus delta -1
- seed 20452418: delta -55, heuristic 158 vs value_optimal 103; first split turn 1 Choice(23) -> Twos(4); upper bonus delta +0, yacht bonus delta +0
- seed 20362617: delta -54, heuristic 194 vs value_optimal 140; first split turn 3 Choice(14) -> Ones(2); upper bonus delta +0, yacht bonus delta +0
- seed 20436274: delta -54, heuristic 242 vs value_optimal 188; first split turn 1 Choice(21) -> Threes(9); upper bonus delta +0, yacht bonus delta +0
- seed 20298041: delta -47, heuristic 201 vs value_optimal 154; first split turn 1 Sixes(24) -> Twos(8); upper bonus delta -1, yacht bonus delta +0

### Saved Best Cases

- Cases: 5; avg delta +176.4000; range 143 to 225
- Upper bonus delta sum +2; Yacht bonus delta sum +5; avg zero-category delta -1.2000
- First split turns: 1 (3), 2 (2)
- First split pairs: Small Straight -> Fours (1), Sixes -> Yacht (1), Sixes -> Ones (1), Threes -> Yacht (1), Choice -> Small Straight (1)

- seed 20290978: delta +225, heuristic 126 vs value_optimal 351; first split turn 1 Small Straight(15) -> Fours(12); upper bonus delta +1, yacht bonus delta +1
- seed 20419121: delta +191, heuristic 153 vs value_optimal 344; first split turn 2 Sixes(18) -> Yacht(50); upper bonus delta +1, yacht bonus delta +1
- seed 20382797: delta +172, heuristic 208 vs value_optimal 380; first split turn 1 Sixes(12) -> Ones(1); upper bonus delta +0, yacht bonus delta +1
- seed 20345464: delta +151, heuristic 160 vs value_optimal 311; first split turn 1 Threes(12) -> Yacht(50); upper bonus delta +0, yacht bonus delta +1
- seed 20309140: delta +143, heuristic 336 vs value_optimal 479; first split turn 2 Choice(23) -> Small Straight(15); upper bonus delta +0, yacht bonus delta +1
