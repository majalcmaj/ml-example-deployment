# ml-deployment

Demonstration production-ready ML project: daily product demand forecasting, split into a uv
workspace so `inference` can be deployed without pulling in `training`.

## Layout

```
src/
  infra/        config loader, logger, correlation-id context
  forecasting/  domain kernel: consts, metadata contract, preprocessing, feature engineering, model load+predict
  training/     trains the model, writes outputs/{model,metadata,predictions}
  inference/    loads the model, serves next-day forecasts
  testkit/      e2e test helpers (script runner, tolerance asserts) — dev-only
```

Dependency direction: `training` and `inference` (deployable apps) both depend on `forecasting`,
which depends on `infra`; `testkit` is a dev dependency of both apps. Neither `training` nor
`inference` depends on the other.

## Make targets

Run `make` with no arguments to list all targets with descriptions.

## Deploying a subset

Each member installs independently, without the other members' dependencies — see
`make sync-inference` / `make sync-training`.
