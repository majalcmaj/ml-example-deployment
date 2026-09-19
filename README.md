# ml-deployment

Demonstration production-ready ML project: daily product demand forecasting, split into a uv
workspace so `inference` can be deployed without pulling in `training`.

## Layout

```
src/
  common/     shared config loader, logger, correlation-id context, feature engineering
  training/   trains the model, writes outputs/{model,metadata,predictions}
  inference/  loads the model, serves next-day forecasts
  testkit/    e2e test helpers (script runner, tolerance asserts) — dev-only
```

Dependency direction: `training` and `inference` both depend on `common`; `testkit` is a dev
dependency of both. Neither `training` nor `inference` depends on the other.

## Make targets

| target | what it does |
|---|---|
| `make sync` | install the full workspace (all members + dev tools) |
| `make test` | run every test |
| `make test-unit` | run non-e2e tests only |
| `make test-e2e` | run the script e2e suites (`inference` + `training`) |
| `make test-inference` / `make test-training` | run one member's e2e suite |
| `make test-mutation` | prove the e2e suites actually catch regressions (`scripts/mutation_check.sh`) |
| `make check` | ruff + full test suite |
| `make build` | build wheels for every member |
| `make baseline-inference` | regenerate inference's e2e baseline from a fresh training run |

## Deploying a subset

Each member installs independently, without the other members' dependencies:

```
make sync-inference   # uv sync --package inference --no-dev — common + inference only
make sync-training    # uv sync --package training --no-dev  — common + training only
```
