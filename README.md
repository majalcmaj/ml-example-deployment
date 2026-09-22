# ml-deployment

Demonstration production-ready ML project: daily product demand forecasting, split into a uv
workspace so `inference` can be deployed without pulling in `training`.

## Layout

```
src/
  infra/        config loader, logger, correlation-id context
  forecasting/  domain kernel: consts, metadata contract, preprocessing, feature engineering, model load+predict
  training/     trains the model, writes outputs/{model,metadata,predictions}
  inference/    loads the model, calls the source/result HTTP endpoints, serves next-day forecasts
  testkit/      e2e test helpers (script runner, tolerance asserts) — dev-only
docker/         one Dockerfile per image (inference, training, mock-api) + the mock API's source
deploy/         config/*.toml baked into each image at build time (absolute paths, no uv.lock at runtime)
docker-compose.yml   local stack: mock-api -> training -> inference, wired together for an e2e run
```

Dependency direction: `training` and `inference` (deployable apps) both depend on `forecasting`,
which depends on `infra`; `testkit` is a dev dependency of both apps. Neither `training` nor
`inference` depends on the other.

## Make targets

Run `make` with no arguments to list all targets with descriptions.

## Git hooks

`make install-hooks` sets up a pre-push hook (via `pre-commit`) that runs lint, type-check, and
unit tests before every `git push`. Run it once after `uv sync`.

## Deploying a subset

Each member installs independently, without the other members' dependencies — see
`make sync-inference` / `make sync-training`.

## Building and running the container images

`make help` lists every image/Compose target (`image-*`, `compose-up`, `compose-retrain`,
`compose-down`, `test-compose`) with a one-line description each — that list is the source of
truth, not this section. The two things worth knowing that aren't obvious from a target name
alone: `image-inference` bakes a model into the image at build time and trains first if
`outputs/` has no model yet; and Compose's `training` service exits after one run
(`restart: "no"`), so `make compose-retrain` is how you rerun it without rebuilding or restarting
`mock-api`/`inference`.

## Deployment shape

Training and daily inference are deployed as separate workloads with different execution
profiles — this repo's images stay platform-neutral (the model directory is just a config field),
but the intended target split, the reasoning behind it, and what to do if the chosen platform runs
out of headroom are written up in `docs/architecture.md` and `docs/what_if.md`.

## Origin

`training/main.py` and `inference/main.py` started as `nbconvert` exports of two Jupyter
notebooks (`daily_product_demand_forecast.ipynb`, `daily_product_demand_inference.ipynb`). The
notebooks have since diverged from the refactored scripts and were removed from the working tree;
their last state is preserved at commit `3594a0b`.
