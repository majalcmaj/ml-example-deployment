# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Daily product-demand forecasting (one global XGBoost model over coffee-shop sales), organised as a
**uv workspace** (Python 3.14) in a **libs/apps** shape so `inference` can be deployed without
`training`'s dependencies. Workspace members live under `src/*`, each with its own `pyproject.toml`:

- `infra` (library) — config loader (`load_config`), correlation-id context, logger. Depends on
  nothing but pydantic.
- `forecasting` (library) — the domain kernel: column/artifact consts, the train↔infer metadata
  contract (`ForecastMetadata`), preprocessing helpers, feature engineering (`create_time_features`,
  `build_future_features`, `encode_for_model`), model load + predict (`load_model`,
  `make_forecast`), and artifact-presence checks (`verify_artifacts_present`). Depends on `infra`.
- `training` (app) — `training/daily_product_demand_forecast.py`: cleans CSVs, trains, writes `outputs/{next_day_product_forecast.csv, xgb_daily_product_demand.json, forecast_metadata.joblib}`
- `inference` (app) — `inference/daily_product_demand_inference.py`: loads those artifacts, rebuilds
  features from recent sales, and hits HTTP endpoints via `gateway.py` (a `SalesGateway` protocol
  backed by `_RestGateway` + `_EnvSecretsProvider`, which reads `INFERENCE_API_TOKEN`) using
  `http_session.py`, writing `outputs/inference_next_day_forecast.csv`. There is no simulation
  mode in production code — tests inject a `StubSalesGateway` instead (`src/inference/tests/stub_gateway.py`).
- `testkit` — dev-only: `runner.run_script` (runs a member script in a tmp cwd via `uv run python3`,
  used by `training`'s e2e) and `asserts` (tolerance constants + frame comparators, used by both)

Dependency direction: `training` and `inference` → `forecasting` → `infra`; `testkit` is a dev dep
of both apps. `training` and `inference` never import each other — the only link is the artifact
files, and this is now enforced by the library boundary rather than convention.

## Commands

Run `make` with no arguments to list all targets with descriptions (descriptions live on the
target lines in `Makefile` as `## ...` comments — keep them updated when adding targets).

```
uv run ruff check      # lint (ruff config in root pyproject; *.ipynb excluded)
uv run pytest src/forecasting/forecasting/features_test.py::test_is_weekend_flags_saturday_and_sunday   # single test
```

Run scripts directly from repo root: `uv run python3 src/training/training/daily_product_demand_forecast.py`
(training must run before inference — inference fails fast if `outputs/` lacks model + metadata).

Container workflow (see `docker/` below): `make images` (or `image-inference` / `image-training` /
`image-mock-api` individually) builds the three images; `make compose-up` runs the local Compose
stack (mock API → training → inference → upload); `make compose-down` tears it down; `make test-compose`
runs the full pipeline through Compose and diffs the result against the inference baseline — this
is also a CI job (`.github/workflows/ci-cd.yml`).

## Config and paths

Each member has `config.py` (pydantic `Config`, frozen) + `config.toml` next to it, loaded once at
import time into a module-level `CONFIG`. `infra.config.load_config`:
- overrides any field from env var `<PREFIX>_<FIELD_UPPER>` (`TRAINING_DATA_DIR`, `INFERENCE_ARTIFACT_DIR`, …)
- overrides the whole config file's path via `<PREFIX>_CONFIG_FILE` (e.g. `INFERENCE_CONFIG_FILE`);
  the Dockerfiles use this to point at `/etc/forecast/*.toml`, baked from `deploy/config/*.toml`
- resolves relative `Path` fields against the project root, found by `find_project_root` walking
  up to `uv.lock`, silently falling back to `cwd` if none is found

A lean runtime image has no `uv.lock` (only the built venv is copied in), so `find_project_root`'s
fallback would resolve relative paths against whatever the container's `WORKDIR` happens to be —
`deploy/config/*.toml` therefore use **absolute** paths (`/opt/model`, `/var/forecast/outputs`, …),
never relative ones.

The e2e conftests rely on those env overrides to redirect `data`/`outputs` into a tmp dir — keep
that mechanism intact when touching config.

## Tests

- Unit tests sit beside the code as `*_test.py` (excluded from wheels via `wheel-exclude`).
- E2e tests live in `src/<member>/tests/`, marked `e2e`, but the two members test differently:
  - `training`'s e2e (`src/training/tests/conftest.py`) is still a subprocess: `testkit.runner.run_script`
    runs the script under `uv run python3` in a tmp cwd, with `TRAINING_DATA_DIR`/`TRAINING_OUTPUT_DIR`
    env overrides redirecting it into that tmp dir.
  - `inference`'s e2e (`src/inference/tests/conftest.py`) is in-process: it imports `run()` from
    `daily_product_demand_inference.py` and calls it directly with a `Config` built **in the fixture**
    (`Config.model_validate({...})`, not env vars) and an injected `StubSalesGateway`
    (`src/inference/tests/stub_gateway.py`), which reads `data/` off disk instead of hitting HTTP.
    `Config` is *not* driven through env overrides here because `CONFIG` is an import-time
    singleton, frozen at module-collection time — env vars set after import wouldn't take effect.
  - Both tests diff the produced artifacts against `src/<member>/tests/baseline/`.
- Tolerances are in `testkit/asserts.py` (`PREDICTION_ATOL=1`, `METRIC_RTOL=1e-3`, `BOUND_RTOL=1e-6`);
  the XGBoost JSON dump is deliberately *not* diffed. Rationale in `src/testkit/README.md`.
- `make test-compose` (`scripts/compose_smoke.sh`, also a CI job) runs the real Compose stack
  end to end — mock API → training → inference → upload — and diffs the resulting forecast CSV
  against the same inference baseline. Because the model it exercises comes from the Compose
  training run rather than the committed baseline artifacts, this is what actually catches a
  stale `src/inference/tests/baseline/` model relative to current training code; refresh it with
  `make baseline-inference` when that drifts.
- `scripts/mutation_check.sh` mutates `features.py`, baselines, `config.toml`, `result_upload.py`,
  and the mock API server, asserting the right suite goes red (mutations 7 and 8 are the newest:
  7 corrupts the uploaded `predicted_quantity` and must fail `src/inference -m e2e`; 8 clamps the
  mock API's history window to 10 days and must fail `make test-compose`'s 28-day guard). It
  refuses to run with uncommitted changes to the files it mutates. If you add an e2e assertion,
  add a mutation that proves it bites; never weaken a mutation to make it pass.
- Refreshing a baseline after an intentional change: run the member suite, hand-diff the tmp
  `outputs/*` against `baseline/*`, copy over, commit with the *why*.

## Known drift / gotchas

- The `.py` scripts started as `nbconvert` exports of the `.ipynb` next to them, but have since
  diverged: `daily_product_demand_inference.py` was split into `gateway.py`, `preprocess.py`,
  `result_upload.py`, `config.py`, and `http_session.py` (its pure-compute modules — `features.py`,
  `forecaster.py`/`model_loader.py`, `artifacts.py` — have since moved into `forecasting` as
  `features.py`, `model.py`, and `artifacts.py`) and no longer carries `# In[n]:` cell markers, and
  the training script has drifted the same way. Tests run the **scripts**; the notebooks still
  exist but show stale logic (e.g. inline secret lookup, dict-style artifact access) — treat them
  as historical reference only, not current design. Do not edit the notebooks. They're slated for
  eventual removal from the repo (tracked in `docs/TODO.md`); once gone, this note goes with them.
- `make baseline-inference` runs the training script at repo root, copies model + metadata into
  inference's baseline dir, then runs `make test-inference`.
- `outputs/` is gitignored; `data/coffeeshop_daily_sales_report.csv` is the only input and is committed.
- xgboost's manylinux wheel links `libgomp.so.1` but doesn't vendor it — slim runtime images
  (`docker/inference.Dockerfile`, `docker/training.Dockerfile`) must `apt-get install libgomp1`.
- `training/daily_product_demand_forecast.py` calls `plt.show()` twice; headless containers need
  `MPLBACKEND=Agg` (set in `docker/training.Dockerfile`) or it hangs/errors with no display.
- The inference image bakes a model into `/opt/model` at build time (`ARG MODEL_DIR`); set
  `INFERENCE_ARTIFACT_DIR` to point elsewhere at runtime. Compose demonstrates this by mounting a
  freshly-trained model over `/opt/model` from the shared `model-artifacts` volume.
- `docker/` holds the three Dockerfiles + `docker/mock-api/server.py` (a stand-in sales API);
  `deploy/config/*.toml` holds the config files baked into the images via `<PREFIX>_CONFIG_FILE`
  — see "Config and paths" above.
- `docs/TODO.md` and `docs/planning.md` hold the prioritized backlog and design rationale; check
  them before proposing structural changes (several options are already ruled out there).
