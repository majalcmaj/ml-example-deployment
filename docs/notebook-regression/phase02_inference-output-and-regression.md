<!-- plan-status: done; commit=03611065ef4b6f10c0981c1bc3c71af028d2c4eb; date=2026-09-18 -->
# Phase 02 — inference-output-and-regression

> **Status:** ✅ DONE — 03611065ef4b6f10c0981c1bc3c71af028d2c4eb (2026-09-18)

Read `docs/notebook-regression/prompt.md` first.

## Goal
`src/daily_product_demand_inference.ipynb` persists its forecast to `outputs/`, and running it
+ diffing against a frozen baseline is covered by the same pytest suite as phase 1 — the
inference notebook currently only prints/POSTs, so this phase both adds the missing persistence
and the regression test for it.

## Context (read before starting)
- Depends on phase 1's `tests/regression/lib.py` (tolerance constants + assert helpers) — reuse,
  don't duplicate.
- Inference notebook (final cell, `## 6. Return predictions to the result endpoint`) currently
  builds `result_payload` (with a `generated_at_utc` timestamp — **nondeterministic, must not be
  persisted**) and either simulates or POSTs it. The `forecast` DataFrame just above it
  (columns: `CATEGORY_COLUMN`, `Predicted_Qty`, already sorted) is the deterministic artifact to
  persist.
- Inference notebook resolves `ARTIFACT_DIR` by walking `[cwd/outputs, cwd.parent/outputs]` —
  same convention as training's `OUTPUT_DIR`. Write the new file next to
  `xgb_daily_product_demand.json`/`forecast_metadata.joblib`, i.e. `ARTIFACT_DIR / "inference_next_day_forecast.csv"`.
- Test ordering matters: the inference notebook loads the model/metadata from `outputs/`, so the
  inference test must run against the artifacts phase 1's training test just produced in the
  same `outputs/` dir (real dir, not tmp — matches the plan's "shared real outputs/" design, and
  mirrors how the pipeline chains in production).

## Red
Write `tests/regression/test_inference_notebook.py` calling a not-yet-existing
`lib.produce_inference_artifacts(repo_root)` and asserting
`(repo_root / "outputs" / "inference_next_day_forecast.csv").exists()`. Run
`uv run pytest tests/regression/test_inference_notebook.py` — must fail (`AttributeError`: no
`produce_inference_artifacts` in `lib.py`, and/or the notebook doesn't write the file yet).
Confirm that failure before implementing.

## Green
- Add one small cell to the end of `src/daily_product_demand_inference.ipynb`, right after
  `outbound_result` is built, saving the deterministic slice:
  ```python
  forecast[[CATEGORY_COLUMN, "Predicted_Qty"]].to_csv(
      ARTIFACT_DIR / "inference_next_day_forecast.csv", index=False
  )
  ```
  (No `generated_at_utc`, no `forecast_date` unless it's needed for the schema check — keep it
  to exactly what's compared.)
- Add `produce_inference_artifacts(repo_root: Path) -> None` to `tests/regression/lib.py`,
  mirroring `produce_training_artifacts` (execute
  `src/daily_product_demand_inference.ipynb` via `nbclient`, `cwd=repo_root`). Note: the
  notebook's `try/except NameError` widget-vs-env-var branch means it'll run fine outside
  Databricks in simulation mode by default — no extra env setup needed.
- `mkdir -p` (already exists) `tests/regression/baseline/` and, after running the notebook once
  to produce it, copy `outputs/inference_next_day_forecast.csv` into
  `tests/regression/baseline/inference_next_day_forecast.csv`. `git add` it.
- Write `tests/regression/test_inference_notebook.py`: a fixture that first calls
  `lib.produce_training_artifacts` (phase 1, so `outputs/` has a fresh model) then
  `lib.produce_inference_artifacts`, then:
  - `test_schema_contract_unchanged` — `assert_columns_equal` on the CSV.
  - `test_predictions_within_tolerance` — `assert_frame_within_tolerance` on `Predicted_Qty`,
    `atol=lib.PREDICTION_ATOL`.
- `uv run pytest tests/regression/test_inference_notebook.py` green.

## Refactor
- If both test files need "run training then inference," hoist the shared fixture into a
  `conftest.py` in `tests/regression/` instead of duplicating it.
- Confirm no tolerance constants or assert helpers got redefined locally instead of imported
  from `lib.py`.

## Verify
- `uv run pytest tests/regression/` — all training + inference regression tests green.
- Sanity-check drift detection the same way as phase 1 (temporarily tweak something inference
  reads, e.g. `HISTORY_DAYS` default, confirm a test fails, then revert).
- `make check` stays green.

## Commit
`test(regression): persist inference forecast and add its regression baseline`
