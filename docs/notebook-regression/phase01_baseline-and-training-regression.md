<!-- plan-status: pending -->
# Phase 01 — baseline-and-training-regression

> **Status:** ⬜ PENDING

Read `docs/notebook-regression/prompt.md` first.

## Goal
Running `src/daily_product_demand_forecast.ipynb` and diffing its artifacts against a frozen
golden baseline is a single `pytest` command — any drift in the trained model's predictions,
validation metrics, outlier bounds, or feature/schema contract fails the suite.

## Context (read before starting)
- Training notebook (cell 12, `## 12. Save predictions and model artifacts`) writes to
  `outputs/` (path: `DATA_DIR.parent / "outputs"`, i.e. repo-root `outputs/`):
  - `next_day_product_forecast.csv` — columns `Date, Menu, Predicted_Qty`.
  - `xgb_daily_product_demand.json` — native XGBoost dump. **Do not diff this file directly.**
  - `forecast_metadata.joblib` — `joblib.dump` of a dict with keys: `model_feature_columns`,
    `raw_feature_columns`, `categories`, `category_dummy_columns`, `configuration` (dict:
    `date_column`, `category_column`, `target_column`, `validation_days`, `random_seed`),
    `outlier_bounds` (a DataFrame — `category_quartiles.reset_index()`, columns include
    `Lower_Bound`/`Upper_Bound` per category), `validation_metrics` (dict of MAE/RMSE/WMAPE,
    overall + per category).
- `outputs/` already exists on disk right now (untracked, one clean run) — this is the agreed
  golden baseline. Copy it, don't regenerate it.
- `nbclient`/`nbformat` are currently only transitive (via the `jupyter` dev dep in
  `pyproject.toml`) — add them as **explicit** entries in `[dependency-groups] dev`.
- No `tests/` directory exists yet; `pyproject.toml` has no `testpaths`, so pytest's default
  discovery will pick up `tests/regression/test_*.py` with no config change.

## Red
Write `tests/regression/test_training_notebook.py` importing `from tests.regression import lib`
(or a relative import — match however `lib.py` is structured) and calling
`lib.produce_training_artifacts(repo_root)` plus `lib.assert_columns_equal` /
`lib.assert_frame_within_tolerance` / `lib.assert_mapping_equal`. Run
`uv run pytest tests/regression/test_training_notebook.py` — it must fail at collection
(`ModuleNotFoundError`/`ImportError`) because `tests/regression/lib.py` does not exist yet.
Confirm that failure before writing any implementation.

## Green
- Add `nbclient>=0.10` and `nbformat>=5.10` to `[dependency-groups] dev` in `pyproject.toml`;
  run `uv sync` (or equivalent) so they're installed non-transitively.
- Create `tests/regression/lib.py`:
  - `produce_training_artifacts(repo_root: Path) -> None` — load
    `src/daily_product_demand_forecast.ipynb` via `nbformat.read`, execute it with
    `nbclient.NotebookClient(nb, resources={"metadata": {"path": str(repo_root)}}).execute()`
    (cwd = repo root, so the notebook's own `DATA_DIR`/`OUTPUT_DIR` logic resolves exactly as a
    human run would — no path patching). This is the only notebook-aware code in the file.
  - `load_csv` / `load_joblib` thin wrappers around `outputs/<file>` and
    `tests/regression/baseline/<file>`.
  - `assert_columns_equal(actual_df, expected_df)` — exact column-name/order equality (schema
    contract).
  - `assert_frame_within_tolerance(actual_df, expected_df, *, rtol=None, atol=None)` — numeric
    columns via `numpy.allclose`/`pandas.testing.assert_frame_equal(check_exact=False, ...)`.
  - `assert_mapping_equal(actual, expected)` — exact equality for
    `configuration`/`categories`/`model_feature_columns`/`category_dummy_columns` (plain
    dict/list compare).
  - Named tolerance constants: `PREDICTION_ATOL = 1` (rounded-quantity jitter),
    `METRIC_RTOL = 1e-3` (MAE/RMSE/WMAPE), `BOUND_RTOL = 1e-6` (IQR bounds computed from static
    data — should be ~exact; tight tolerance just absorbs float summation order).
- `mkdir -p tests/regression/baseline` and copy the **current** `outputs/next_day_product_forecast.csv`
  and `outputs/forecast_metadata.joblib` into it unmodified — this freezes today's pre-refactor
  run as the golden baseline. `git add` them (they're small: ~1KB CSV, ~5KB joblib).
- Write `tests/regression/test_training_notebook.py` with a module-scoped fixture that calls
  `lib.produce_training_artifacts(repo_root)` once, then four tests, each comparing one slice of
  `outputs/*` against `tests/regression/baseline/*`:
  - `test_schema_contract_unchanged` — `assert_mapping_equal` on `configuration`, `categories`,
    `model_feature_columns`, `category_dummy_columns`; `assert_columns_equal` on the forecast CSV.
  - `test_outlier_bounds_within_tolerance` — `assert_frame_within_tolerance` on `outlier_bounds`,
    `rtol=lib.BOUND_RTOL`.
  - `test_validation_metrics_within_tolerance` — same on `validation_metrics`,
    `rtol=lib.METRIC_RTOL`.
  - `test_predictions_within_tolerance` — same on `next_day_product_forecast.csv`'s
    `Predicted_Qty` column, `atol=lib.PREDICTION_ATOL`.
- `uv run pytest tests/regression/test_training_notebook.py` green.

## Refactor
- Ensure the module-scoped "run training notebook once" fixture isn't duplicated per test.
- Ensure tolerance constants live only in `lib.py`, imported (not re-declared) in the test file.
- Remove any leftover print/debug statements added while iterating.

## Verify
- `uv run pytest tests/regression/test_training_notebook.py` — green, 4 passed.
- Sanity-check the harness actually detects drift: temporarily set `lib.PREDICTION_ATOL = 0` and
  confirm `test_predictions_within_tolerance` still passes (same-run determinism) or, better,
  temporarily edit a training notebook cell (e.g. a lag window) and confirm at least one test
  fails — then revert the temporary edit before committing.
- `make check` (ruff + pytest) stays green.

## Commit
`test(regression): add training-notebook regression baseline and harness`
