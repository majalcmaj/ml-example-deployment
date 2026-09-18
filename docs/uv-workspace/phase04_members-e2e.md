<!-- plan-status: pending -->
# Phase 04 — members-e2e

> **Status:** ⬜ PENDING

Read `docs/uv-workspace/prompt.md` first.

## Goal
Each deployable member has a standalone e2e suite in `src/<member>/tests/` driven by `testkit`,
with config-driven `data_dir` / `artifact_dir` / `output_dir`. Inference e2e runs without
`training` installed.

## Jobs (file-disjoint, parallel worktrees)
| job | file | owns |
|---|---|---|
| job01 | `phase04-job01_inference.md` | `src/inference/**`, `tests/regression/test_inference_notebook.py` (rm), `tests/regression/baseline/inference_next_day_forecast.csv` (mv), Makefile `baseline-inference` target |
| job02 | `phase04-job02_training.md` | `src/training/**`, `tests/regression/test_training_notebook.py` (rm), `tests/regression/baseline/{forecast_metadata.joblib,next_day_product_forecast.csv}` (mv) |

Neither job touches `tests/regression/conftest.py`, `lib.py`, `src/common/**`, or `src/testkit/**`.

**Notebook rule (both jobs):** edit only import lines and the `DATA_DIR` / `ARTIFACT_DIR` /
`OUTPUT_DIR` assignment cells. No other cell, no unused-import cleanup, no logging changes.

## Red
Each job writes its `src/<member>/tests/` suite first and shows it fails (see job files).

## Green
Per job. Then merge both worktree branches and squash into one phase commit.

## Refactor
Per job; after merge, confirm `tests/regression/` contains only `conftest.py`, `lib.py`,
`README.md`, `__init__.py` and an empty `baseline/` (phase 06 removes them).

## Verify
```sh
uv sync && uv run pytest -m e2e                       # both suites green
uv sync --package inference && uv run --package inference pytest src/inference   # training absent
uv sync --package training  && uv run --package training  pytest src/training
git diff HEAD~1 -- '*.ipynb' | grep '^[-+]    "' | grep -vE 'import|_DIR|sys.path|CONFIG\.' ; # → empty
```

## Commit
`feat: per-member e2e suites with config-driven dirs and committed baselines`
