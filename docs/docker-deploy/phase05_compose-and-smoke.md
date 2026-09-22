<!-- plan-status: done; commit=584b4bc255a4302d401284d45c2439fc7e925aba; date=2026-09-22 -->
# Phase 05 — compose-and-smoke

> **Status:** ✅ DONE — 584b4bc255a4302d401284d45c2439fc7e925aba (2026-09-22)

Read `docs/docker-deploy/prompt.md` first.

## Goal
`docker compose up` on a clean checkout trains, serves, infers and uploads — exercising the real
`_RestGateway` HTTP path end to end. Closes `docs/TODO.md:14` (P0, "End-to-end tests: full pipeline
against Docker Compose mocks").

## Red
Two checks, both failing today:

1. **`make test-compose`** does not exist. Once written it must run the three phase-04 images
   together and diff the produced `inference_next_day_forecast.csv` against
   `src/inference/tests/baseline/` within `PREDICTION_ATOL`.

2. **New mutation 8.** In `scripts/mutation_check.sh`, clamp `docker/mock-api/server.py` to return
   only 10 days of history and require `make test-compose` to fail — the 28-day guard at
   `preprocess.py:74-77` must bite. Without this, a Compose test that merely starts containers
   would pass while proving nothing about the pipeline.

## Green
### `docker-compose.yml` (repo root)
Three services. Both apps are **batch jobs, not servers** (`restart: "no"`) — this is what becomes
a k8s CronJob or an EventBridge-triggered Lambda/Fargate task.

- **`mock-api`** — healthcheck polling `/healthz`, `MOCK_API_TOKEN=local-dev-token`.
- **`training`** — `./data:/var/forecast/data:ro`, writes to a named volume `model-artifacts`.
- **`inference`** —
  `depends_on: {mock-api: {condition: service_healthy}, training: {condition: service_completed_successfully}}`.
  Without the healthcheck gate it races the stub. Mounts `model-artifacts` at `/opt/model:ro`
  (**demonstrating the override of the baked-in default**), bind-mounts
  `./deploy/config/inference.toml` at `/etc/forecast/inference.toml:ro`, and sets
  `INFERENCE_API_TOKEN=local-dev-token`.

The bind-mounted config is the whole point of phase 01: the same file lands as a ConfigMap on k8s,
an EFS volume on ECS, or an S3 input channel on SageMaker, with `INFERENCE_CONFIG_FILE` unchanged.

### `scripts/compose_smoke.sh`
`docker compose up --build --abort-on-container-exit --exit-code-from inference`, then compare the
produced CSV against the committed baseline using `testkit.asserts`' `PREDICTION_ATOL`. Tear down
with `docker compose down -v` in a `trap` so a failed run leaves no volume behind.

Note the model here comes from the **Compose training run**, not the committed baseline — so this
doubles as the missing train→infer integration check (`docs/TODO.md:23-38`, P1) and would catch a
stale `src/inference/tests/baseline/` model, which nothing in CI does today (`CLAUDE.md:63-66`).

### `Makefile`
Add, with `## ` descriptions on the target lines (`CLAUDE.md:29-31`):
`image-inference`, `image-training`, `image-mock-api`, `images`, `compose-up`, `compose-down`,
`test-compose`. `image-inference` must ensure `outputs/` holds a model before building
(`ARG MODEL_DIR=outputs`), running training first if absent.

### `scripts/mutation_check.sh`
Add mutation 8 and add `docker/mock-api/server.py` to the `MUTATED_FILES` clean-tree guard at
`:24`. Extend the table comment at `:9-16`. Mutations 1-7 must still pass.

### `.github/workflows/ci-cd.yml`
New `test-compose` job after `test-e2e`, before the deploy gates, with buildx layer caching.

## Refactor
`testkit/runner.py` stays as-is — do not stretch `run_script` to shell out to Docker. A container
smoke test is a shell concern, and `runner.py` is still exactly right for `src/training/tests/`.
Keep `compose_smoke.sh` short enough to read in one screen; no bespoke orchestration.

## Verify
```
rm -rf outputs && make test-compose
docker compose logs mock-api
make test-mutation
```
- `make test-compose` green from a clean checkout with no pre-existing `outputs/`.
- `mock-api` logs show 200 on both the GET and the POST, with an `Authorization: Bearer` header on
  each and an `X-Correlation-ID` that matches the inference logs.
- All 8 mutations caught.

Failure-mode checks:
```
docker compose run --rm -e INFERENCE_ARTIFACT_DIR=/nonexistent inference
docker compose run --rm -e INFERENCE_API_TOKEN= inference
```
The first must fail fast with `verify_artifacts_present`'s `FileNotFoundError`; the second with
`INFERENCE_API_TOKEN is not set`, not a 401 traceback.

## Commit
`feat(docker): add the local Compose stack and a container smoke test`
