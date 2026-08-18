# Exact-memo vs MLP roll policy evaluation (2026-07-27)

## Goal

Compare decision engines independently from the game strategy.  All variants
use the `focused` strategy and the exact score-stage choice; they differ only
in the roll (`keep` / `reroll`) policy.

- `exact_memo`: exact solver baseline, accelerated by its memoized state cache.
- `mlp_roll`: v3 MLP chooses every roll action directly; score selection stays exact.
- `guarded_mlp`: v3 MLP proposes a roll action, then the existing confidence and
  exact-value guard accepts it or falls back to the exact solver.

## Method

Each policy played the same 200 indexed dice streams.  Pairing identical
streams removes most dice variance, so the per-game score difference is a
direct policy comparison rather than a comparison of luck.

```bash
.venv/bin/python scripts/simulate_roll_policy_games.py \
  --games 200 --seed 20260727 --mode focused \
  --model-v2 artifacts/runtime/models/model-20260717-roll-policy-v3.json \
  --label-v2 mlp_v3 --policy-set second --min-confidence 0.95 \
  --random-source indexed \
  --output artifacts/generated/roll-policy-v3-vs-exact-indexed-200-20260727.json
```

## Results

| Policy | Mean total | Mean delta vs exact | W / T / L vs exact | Upper-bonus rate |
| --- | ---: | ---: | ---: | ---: |
| `exact_memo` | 176.03 | 0.00 | 0 / 200 / 0 | 42.0% |
| `guarded_mlp` | 177.35 | +1.32 | 29 / 156 / 15 | 42.0% |
| `mlp_roll` | 162.43 | -13.61 | 56 / 7 / 137 | 23.0% |

The guard accepted 2,471 of 4,729 roll decisions (52.3%) and returned the
other 2,258 decisions to the exact solver.  The guarded result is therefore a
quality-protection result, not evidence that a pure MLP has surpassed exact
search.

## Decision

- Keep `exact_memo` as the default for the AI opponent and recommendation API.
- Keep `mlp_roll` available only as an explicitly labelled experiment.
- `guarded_mlp` may be used for A/B testing, but it must not be presented as a
  latency improvement while it still performs an exact verification step.
- A future MLP candidate needs a new teacher dataset and the same paired
  evaluation before promotion.  Its promotion gate should include both mean
  score delta and a worst-case/regret limit, not top-1 action accuracy alone.
