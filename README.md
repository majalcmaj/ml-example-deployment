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

## Deploying a subset

Each member installs independently, without the other members' dependencies — see
`make sync-inference` / `make sync-training`.

## Building and running the container images

- `make images` builds all three images (`make image-inference`, `make image-training`,
  `make image-mock-api` individually). `image-inference` trains first if `outputs/` has no model
  yet, since the image bakes a model in at build time.
- `make compose-up` runs the local Compose stack end to end: the mock API comes up, training
  writes a model into a shared volume, then inference consumes it, calls the mock API, and writes
  the forecast.
- `make test-compose` runs that same stack and diffs the result against the committed inference
  baseline — this is also a CI job, so it catches a stale baseline model independently of the
  per-member unit/e2e suites.
- `make compose-down` tears the stack (and its volumes) down.

## Deployment shape

Training and daily inference are deployed as separate workloads with different execution
profiles — this repo's images stay platform-neutral (the model directory is just a config field),
but the intended target split, the reasoning behind it, and what to do if the chosen platform runs
out of headroom are written up in `docs/architecture.md` and `docs/what_if.md`.
