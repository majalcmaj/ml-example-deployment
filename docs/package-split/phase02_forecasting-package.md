<!-- plan-status: done; commit=be37af9; date=2026-09-22 -->
# Phase 02 — forecasting-package

> **Status:** ✅ DONE — be37af9 (2026-09-22)

Read `docs/package-split/prompt.md` first.

## Goal
Collapse what remains of `common` and `inference`'s pure-compute modules into a single domain
kernel, `forecasting`: column/artifact constants, the train↔infer metadata contract,
preprocessing helpers, feature engineering (including future-row construction and
contract-encoding), and model load + predict. `src/common/` disappears. Pure moves — no
behaviour change.

## Red
All three must fail before any edit:

```
uv run python3 -c "import forecasting.model"      # ModuleNotFoundError: forecasting
test ! -d src/common                              # fails: src/common still exists
grep -rn "^from common\|^import common" src/ | wc -l   # > 0
```

## Green
1. `git mv` the survivors out of `common`:
   | from | to |
   |---|---|
   | `src/common/common/consts.py` | `src/forecasting/forecasting/consts.py` |
   | `src/common/common/forecast_metadata.py` | `src/forecasting/forecasting/metadata.py` |
   | `src/common/common/preprocessing.py` (+ `preprocessing_test.py`) | `src/forecasting/forecasting/` |
   | `src/common/common/features.py` (+ `features_test.py`) | `src/forecasting/forecasting/` |
2. `git mv` `inference`'s pure-compute modules in:
   | from | to |
   |---|---|
   | `src/inference/inference/features.py` | append into `src/forecasting/forecasting/features.py` |
   | `src/inference/inference/model_loader.py` + `forecaster.py` | `src/forecasting/forecasting/model.py` |
   | `src/inference/inference/artifacts.py` (+ `artifacts_test.py`) | `src/forecasting/forecasting/` |
   `features.py` ends up holding `create_time_features`, `build_future_features`,
   `encode_for_model`. `model.py` holds `load_model` + `make_forecast` (the private import edge
   `forecaster.py:6 → model_loader` becomes an intra-module call).
3. New `src/forecasting/pyproject.toml`: deps `infra` (workspace), `pandas>=3.0.5`, `numpy`,
   `joblib>=1.6.0`, `pydantic>=2.13.5`, `xgboost>=3.4.1`; dev group `testkit`; same `uv_build`
   block and `wheel-exclude`.
4. Rewrite every remaining import: `common.consts` → `forecasting.consts`,
   `common.forecast_metadata` → `forecasting.metadata`, `common.preprocessing` →
   `forecasting.preprocessing`, `common.features` → `forecasting.features`,
   `inference.features` → `forecasting.features`, `inference.forecaster` → `forecasting.model`,
   `inference.artifacts` → `forecasting.artifacts`. Includes the mid-file import at
   `src/training/training/daily_product_demand_forecast.py:197`.
5. Delete `src/common/`; drop `common` from the root `pyproject.toml` dev group and
   `[tool.uv.sources]`, add `forecasting`. Swap `common` → `forecasting` in the `training` and
   `inference` member pyprojects (dep cleanup beyond the swap belongs to phase 03).
6. `uv sync`.

**Do not move** `src/inference/inference/preprocess.py`. `payload_to_dataframe` is wire-format
parsing, and `preprocess_data`'s 28-day guard plus `isin(metadata.categories)` filter are
inference-only — training has no metadata before fit. Its shared panel-build block is phase-3 TODO
material, not a move.

**Do not move** `src/inference/inference/daily_product_demand_inference.py` —
`src/inference/tests/conftest.py:9` pins that path. Preserve its load-bearing line order: the
bare `init_context()` at `:15` sits between the import blocks, before
`from inference.gateway import …`, so `create_http_session` reads a real correlation id.

## Refactor
- One `forecasting/features.py`, one `forecasting/model.py` — no `model_loader.py` or
  `forecaster.py` shim left behind, no re-export module in `inference`.
- Repoint the cross-referencing TODO block that arrives with `inference/features.py:10-14`: it
  currently says "extract into `common`"; the target is now `forecasting`, and the *placement*
  half is done — only collapsing the duplicate remains.
- `grep -rn "\bcommon\b" src/` returns nothing outside prose.

## Verify
- `uv run ruff check` and `make type-check` clean.
- `make test` green, same pass count.
- Baselines untouched: `git status --porcelain src/*/tests/baseline` is empty.
- Artifact contract survived the class move — `ForecastMetadata.save` dumps `model_dump()`, a
  plain dict, so the committed `src/inference/tests/baseline/forecast_metadata.joblib` (written by
  the old `common.forecast_metadata.ForecastMetadata`) must still load through
  `forecasting.metadata.ForecastMetadata`. The inference e2e covers this; confirm it actually ran
  rather than skipped.
- `git diff -M --stat` shows renames.

## Commit
`refactor(workspace): extract forecasting kernel from common and inference`

Trailer: `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`
