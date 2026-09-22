# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Daily product-demand forecasting (one global XGBoost model over coffee-shop sales), organised as a
**uv workspace** (Python 3.14) so `inference` can be deployed without `training`'s dependencies.
Workspace members live under `src/*`, each with its own `pyproject.toml`:

- `common` — config loader (`load_config`), correlation-id context, logger, column consts, `create_time_features`
- `training` — `training/daily_product_demand_forecast.py`: cleans CSVs, trains, writes `outputs/{next_day_product_forecast.csv, xgb_daily_product_demand.json, forecast_metadata.joblib}`
- `inference` — `inference/daily_product_demand_inference.py`: loads those artifacts, rebuilds features from recent sales, writes `outputs/inference_next_day_forecast.csv` (simulation mode by default; real mode hits HTTP endpoints via `http_session.py`)
- `testkit` — dev-only: `runner.run_script` (runs a member script in a tmp cwd via `uv run python3`) and `asserts` (tolerance constants + frame comparators)

Dependency direction: `training` and `inference` → `common`; `testkit` is a dev dep of both.
`training` and `inference` never import each other — the only link is the artifact files.

## Commands

Run `make` with no arguments to list all targets with descriptions (descriptions live on the
target lines in `Makefile` as `## ...` comments — keep them updated when adding targets).

```
uv run ruff check      # lint (ruff config in root pyproject; *.ipynb excluded)
uv run pytest src/common/common/features_test.py::test_is_weekend_flags_saturday_and_sunday   # single test
```

Run scripts directly from repo root: `uv run python3 src/training/training/daily_product_demand_forecast.py`
(training must run before inference — inference fails fast if `outputs/` lacks model + metadata).

## Config and paths

Each member has `config.py` (pydantic `Config`, frozen) + `config.toml` next to it, loaded once at
import time into a module-level `CONFIG`. `common.config.load_config`:
- overrides any field from env var `<PREFIX>_<FIELD_UPPER>` (`TRAINING_DATA_DIR`, `INFERENCE_ARTIFACT_DIR`, …)
- resolves relative `Path` fields against the project root, found by walking up to `uv.lock`

The e2e conftests rely on those env overrides to redirect `data`/`outputs` into a tmp dir — keep
that mechanism intact when touching config.

## Tests

- Unit tests sit beside the code as `*_test.py` (excluded from wheels via `wheel-exclude`).
- E2e tests live in `src/<member>/tests/`, marked `e2e`. A session-scoped `run_root` fixture copies
  `data/` (and, for inference, the baseline model + metadata) into a tmp dir, runs the member
  script there, and tests diff the produced artifacts against `src/<member>/tests/baseline/`.
- Tolerances are in `testkit/asserts.py` (`PREDICTION_ATOL=1`, `METRIC_RTOL=1e-3`, `BOUND_RTOL=1e-6`);
  the XGBoost JSON dump is deliberately *not* diffed. Rationale in `src/testkit/README.md`.
- `scripts/mutation_check.sh` mutates `features.py`, baselines and `config.toml` and asserts the
  right suite goes red. It refuses to run with uncommitted changes to those files. If you add an
  e2e assertion, add a mutation that proves it bites; never weaken a mutation to make it pass.
- Refreshing a baseline after an intentional change: run the member suite, hand-diff the tmp
  `outputs/*` against `baseline/*`, copy over, commit with the *why*. Inference's baseline model
  (`xgb_daily_product_demand.json`, `forecast_metadata.joblib`) comes from a fresh training run
  and must be regenerated whenever training-side logic changes — nothing in CI catches a stale one
  (see `docs/TODO.md`, P1).

## Known drift / gotchas

- The `.py` scripts started as `nbconvert` exports of the `.ipynb` next to them, but have since
  diverged: `daily_product_demand_inference.py` was split into six modules (`gateway.py`,
  `features.py`, `forecaster.py`, `preprocess.py`, `result_upload.py`, `model_loader.py`) and no
  longer carries `# In[n]:` cell markers, and the training script has drifted the same way. Tests
  run the **scripts**; the notebooks still exist but show stale logic (e.g. inline secret lookup,
  dict-style artifact access) — treat them as historical reference only, not current design. Do
  not edit the notebooks. They're slated for eventual removal from the repo (tracked in
  `docs/TODO.md`); once gone, this note goes with them.
- `make baseline-inference` runs the training script at repo root, copies model + metadata into
  inference's baseline dir, then runs `make test-inference`.
- `outputs/` is gitignored; `data/coffeeshop_daily_sales_report.csv` is the only input and is committed.
- `inference/config.toml` has `secret_key` inline with a TODO to move it to an env var/vault.
- `docs/TODO.md` and `docs/planning.md` hold the prioritized backlog and design rationale; check
  them before proposing structural changes (several options are already ruled out there).
