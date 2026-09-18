<!-- plan-status: pending -->
# Phase 05 — mutation-tests

> **Status:** ⬜ PENDING

Read `docs/uv-workspace/prompt.md` first.

## Goal
Every e2e suite provably fails when the thing it guards is broken. `make test-mutation` runs the
proof and leaves the tree clean.

## Red
```sh
make test-mutation      # → no such target
# manual probe:
sed -i 's/for lag in \[1, 7, 14, 28\]/for lag in [1, 7, 14, 29]/' src/common/common/features.py
uv run pytest -m e2e    # MUST fail. If it passes, the suites are toothless → tighten in Green.
git checkout -- src/common/common/features.py
```

## Green
`scripts/mutation_check.sh` (bash, `set -euo pipefail`):
- Abort if `git status --porcelain -- <mutated files>` is non-empty.
- One function `mutate <n> <file> <apply-cmd> <pytest-target>`: apply, run
  `uv run pytest <target> -q` expecting **non-zero**, `git checkout -- <file>` (or `mv` back for
  renames), print `PASS mutation N caught` / `FAIL mutation N survived`.
- Exit non-zero if any survived.

| # | Mutation | Suite that must fail |
|---|---|---|
| 1 | `src/common/common/features.py`: lag `28` → `29` | `src/training` (metrics rtol, bounds) and `src/inference` (predictions) |
| 2 | `features.py`: `Is_Weekend` `[5, 6]` → `[4, 6]` | both |
| 3 | `src/training/tests/baseline/next_day_product_forecast.csv`: first prediction `+= 10` | `src/training` (`PREDICTION_ATOL=1`) |
| 4 | `src/inference/tests/baseline/inference_next_day_forecast.csv`: first prediction `+= 10` | `src/inference` |
| 5 | `src/inference/tests/baseline/forecast_metadata.joblib` renamed away | `src/inference` (fail-fast `FileNotFoundError`) |
| 6 | `src/inference/inference/config.toml`: `artifact_dir = "nowhere"`, run with `INFERENCE_ARTIFACT_DIR` unset | `src/inference` |

Makefile: `test-mutation: ./scripts/mutation_check.sh`.

Any survivor → tighten the corresponding assertion. Never weaken the mutation to make it "pass".

## Refactor
Mutation table lives once, in the script header; apply/run/restore is one function; no per-mutation
copy-paste.

## Verify
```sh
make test-mutation          # 6/6 caught
git status --short          # clean
uv run pytest -m e2e        # still green
```

## Commit
`test: mutation checks proving e2e suites detect feature, baseline, and artifact breakage`
