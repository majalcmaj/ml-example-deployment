# testkit

Shared e2e test helpers for the workspace members. Each member (`inference`, `training`) has its
own `src/<member>/tests/` suite: every test runs its script end-to-end via
`testkit.runner.run_script` (cwd = a tmp dir seeded with `data/` and, for `inference`, a
seeded `outputs/`) and diffs the artifacts it writes against a frozen copy in
`src/<member>/tests/baseline/`.

Run with:

```
make test-e2e            # both members
make test-inference       # inference only
make test-training        # training only
```

## Artifact map

| script | writes | compared against |
|---|---|---|
| `src/training/training/main.py` | `next_day_product_forecast.csv` | `src/training/tests/baseline/next_day_product_forecast.csv` |
| `src/training/training/main.py` | `forecast_metadata.joblib` | `src/training/tests/baseline/forecast_metadata.joblib` |
| `src/inference/inference/main.py` | `inference_next_day_forecast.csv` | `src/inference/tests/baseline/inference_next_day_forecast.csv` |

`xgb_daily_product_demand.json` (the native XGBoost model dump) is **not** diffed directly — it's
a serialization of the fitted model, not a stable contract; `forecast_metadata.joblib`'s
`validation_metrics` and the prediction CSVs already cover whether the model behaves the same.

## Tolerances (`testkit.asserts`)

| constant | value | why |
|---|---|---|
| `PREDICTION_ATOL` | `1` | predicted quantities are rounded; ±1 absorbs rounding jitter |
| `METRIC_RTOL` | `1e-3` | MAE/RMSE/WMAPE are floats accumulated over many rows; allow float noise |
| `BOUND_RTOL` | `1e-6` | IQR bounds come from static historical data — should be near-exact; the tiny tolerance only absorbs float summation order |

## Refreshing a baseline after an intentional change

1. Make the reviewed change to the script(s).
2. Run the affected member's suite once (`make test-inference` / `make test-training`) to
   regenerate its tmp `outputs/`.
3. Diff the tmp `outputs/*` against `src/<member>/tests/baseline/*` by hand and confirm the
   change is expected. `inference`'s `outputs/xgb_daily_product_demand.json` and
   `forecast_metadata.joblib` come from `make baseline-inference` (which runs `training` fresh).
4. Copy the regenerated files over the corresponding `baseline/*` files.
5. Commit, explaining *why* the baseline moved.

## Proving the suites aren't toothless

`make test-mutation` (`scripts/mutation_check.sh`) deliberately breaks the feature code, a
baseline, or a config value the suites are supposed to guard, and asserts each mutation makes the
right suite go red — see the table in that script for the full list.
