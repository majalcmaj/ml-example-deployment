# Notebook regression suite

Catches drift while refactoring `src/*.ipynb` into non-notebook code: each test runs a notebook
end-to-end via `nbclient` (cwd = repo root, exactly like a human run) and diffs the artifacts it
writes in `outputs/` against a frozen copy in `baseline/`.

Run with:

```
make test-regression
```

## Artifact map

| notebook | writes to `outputs/` | compared against |
|---|---|---|
| `src/daily_product_demand_forecast.ipynb` | `next_day_product_forecast.csv` | `baseline/next_day_product_forecast.csv` |
| `src/daily_product_demand_forecast.ipynb` | `forecast_metadata.joblib` | `baseline/forecast_metadata.joblib` |
| `src/daily_product_demand_inference.ipynb` | `inference_next_day_forecast.csv` | `baseline/inference_next_day_forecast.csv` |

`xgb_daily_product_demand.json` (the native XGBoost model dump) is **not** diffed directly — it's
a serialization of the fitted model, not a stable contract; `forecast_metadata.joblib`'s
`validation_metrics` and the prediction CSVs already cover whether the model behaves the same.

## Tolerances (`lib.py`)

| constant | value | why |
|---|---|---|
| `PREDICTION_ATOL` | `1` | predicted quantities are rounded; ±1 absorbs rounding jitter |
| `METRIC_RTOL` | `1e-3` | MAE/RMSE/WMAPE are floats accumulated over many rows; allow float noise |
| `BOUND_RTOL` | `1e-6` | IQR bounds come from static historical data — should be near-exact; the tiny tolerance only absorbs float summation order |

## Refreshing the baseline after an intentional change

1. Make the reviewed change to the notebook(s).
2. `make test-regression` once to regenerate `outputs/`.
3. Diff `outputs/*` against `tests/regression/baseline/*` by hand (e.g.
   `git diff --no-index outputs/next_day_product_forecast.csv tests/regression/baseline/next_day_product_forecast.csv`)
   and confirm the change is expected.
4. Copy `outputs/*` over the corresponding `baseline/*` files.
5. Commit, explaining *why* the baseline moved.
