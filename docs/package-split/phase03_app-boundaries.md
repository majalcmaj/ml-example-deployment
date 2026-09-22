<!-- plan-status: pending -->
# Phase 03 — app-boundaries

> **Status:** ⬜ PENDING

Read `docs/package-split/prompt.md` first.

## Goal
Make each member declare exactly what it imports, and mark every site in the training script that
the `forecasting` kernel will absorb later. No training logic moves and no duplication is
collapsed in this phase — comments only.

## Red
```
grep -n 'scikit-learn' src/inference/pyproject.toml     # present, imported nowhere under src/inference
grep -n 'joblib'       src/training/pyproject.toml      # present, never imported directly
grep -c 'forecasting\.'  src/training/training/daily_product_demand_forecast.py  # no reuse markers yet
```

## Green
**Dependency truth-up.**
- `src/inference/pyproject.toml`: drop `scikit-learn` (declared at `:9`, imported nowhere under
  `src/inference`). Drop `numpy` if phase 02 left it — `forecaster.py` was the only user. Keep
  `forecasting`, `infra`, `pandas`, `pydantic`, `requests>=2.32`.
- `src/training/pyproject.toml`: drop `joblib` (reaches it only through
  `ForecastMetadata.save`); add explicit `numpy` (`daily_product_demand_forecast.py:13` imports it
  but it arrives transitively via pandas/xgboost today). Keep `forecasting`, `infra`, `pandas`,
  `scikit-learn` (validation metrics, `:279-284`), `matplotlib`, `xgboost`.

**Reuse markers in `src/training/training/daily_product_demand_forecast.py`.** One TODO comment
per site, each naming its target and referencing `docs/TODO.md`'s P0 "single shared feature
extraction" item:

| site | marker points at |
|---|---|
| `:229-235` train/validation `get_dummies` + reindex | `forecasting.features.encode_for_model` |
| `:332-347` future placeholder rows + `create_time_features` + filter | `forecasting.features.build_future_features` |
| `:349-352` future `get_dummies` + reindex | `forecasting.features.encode_for_model` |
| `:353-359` `np.clip` + `np.rint` + forecast frame | `forecasting.model.make_forecast` |
| `:109-121` date×category panel build | shared panel helper, to be extracted alongside `inference/preprocess.py:55-86` |
| `:371,375` `model.save_model` | `forecasting.model` should own the write side of the artifact contract; it already owns the read side |

Rewrite the existing block at `:327-331`, which still says "extract into `common`". Same for the
TODO at `:108` ("how much can be sensibly extracted to common/") — the answer is now
`forecasting`, and the *placement* half is already done.

Add a one-line note (not a TODO) at `:51-61` recording that the CSV glob+concat it shares with
`inference/gateway.py:111-115` is deliberately left duplicated: different semantics (full history
+ `Source_File` tag vs. recent window → JSON records), ~6 lines, and sharing it would couple an
app to an app.

## Refactor
Audit every member: each declared dependency must have at least one real import under that
member's source tree, and every third-party import must be declared. Fix both directions.

## Verify
- `uv run ruff check`, `make type-check`, `make test` — all green, same pass count.
- `make sync-inference` resolves, then confirm the deploy subset carries neither `scikit-learn`
  nor `matplotlib` (`uv pip list` in that env, or `uv tree --package inference --no-dev`).
- `make sync-training` resolves.
- `uv sync` restores the full dev workspace afterwards.
- Baselines untouched: `git status --porcelain src/*/tests/baseline` is empty.
- The training script's behaviour is byte-identical — this phase adds comments and edits
  `pyproject.toml` files only.

## Commit
`chore(workspace): tighten member dependencies, mark kernel reuse sites`

Trailer: `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`
