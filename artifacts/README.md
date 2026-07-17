# Artifact Policy

- `runtime/`: versioned models and value tables required by the application or tests.
- `reference/`: versioned benchmark evidence and reproducible reference datasets.
- `generated/`: local experiment output. This directory is ignored except for `.gitkeep`.

Training and evaluation commands should write new output under `generated/`. Promote an artifact to `runtime/` or `reference/` only after validation and update its documentation in the same change.
