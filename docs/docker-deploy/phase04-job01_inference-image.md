<!-- plan-status: done; commit=8adb6b7262e0e517e5a4b13c822a4ed430d0aa77; date=2026-09-22 -->
# phase04 · Job 01 — inference-image

> **Status:** ✅ DONE — 8adb6b7262e0e517e5a4b13c822a4ed430d0aa77 (2026-09-22)

Read `docs/docker-deploy/prompt.md` and the parent phase file first. This job runs in its own git
worktree; touch only the files in its slice (jobs are file-disjoint).

## Goal
A minimal inference image with three cache layers in dependency order — deps → code → model — plus
the repo's `.dockerignore` and the container-facing inference config.

**Owns:** `.dockerignore`, `docker/inference.Dockerfile`, `deploy/config/inference.toml`.
Jobs 02 and 03 must not touch `.dockerignore`.

## Red
```
docker build -f docker/inference.Dockerfile -t fc-inference .
```
Fails — no such file. After it builds, the cache check must also hold:
touch `src/inference/inference/preprocess.py`, rebuild, and the dependency layer must print
`CACHED`. A single-`COPY`-then-`uv sync` Dockerfile fails that check, which is the real assertion
here.

## Green
```dockerfile
# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.12.15-python3.14-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# --- layer 1: third-party dependencies (changes rarely) ---
COPY uv.lock pyproject.toml ./
COPY src/infra/pyproject.toml       src/infra/pyproject.toml
COPY src/forecasting/pyproject.toml src/forecasting/pyproject.toml
COPY src/inference/pyproject.toml   src/inference/pyproject.toml
COPY src/training/pyproject.toml    src/training/pyproject.toml
COPY src/testkit/pyproject.toml     src/testkit/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package inference --no-install-workspace

# --- layer 2: workspace code (changes per commit) ---
COPY src/infra       src/infra
COPY src/forecasting src/forecasting
COPY src/inference   src/inference
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package inference

FROM python:3.14-slim-bookworm AS runtime
# xgboost's manylinux wheel links libgomp.so.1 and does not vendor it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 10001 app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY --chown=app:app deploy/config/inference.toml /etc/forecast/inference.toml
ENV INFERENCE_CONFIG_FILE=/etc/forecast/inference.toml

# --- layer 3: model artifacts (change most often — must be last) ---
ARG MODEL_DIR=outputs
COPY --chown=app:app ${MODEL_DIR}/xgb_daily_product_demand.json \
                     ${MODEL_DIR}/forecast_metadata.joblib \
                     /opt/model/

USER app
WORKDIR /var/forecast
ENTRYPOINT ["python", "-m", "inference.daily_product_demand_inference"]
```

`deploy/config/inference.toml` — absolute paths, Compose-facing endpoints:
```toml
source_endpoint_url = "http://mock-api:8080/api/recent-sales"
result_endpoint_url = "http://mock-api:8080/api/demand-forecast"
history_days = 60
artifact_dir = "/opt/model"
output_dir   = "/var/forecast/outputs"
```
`http_session.py:24-25` mounts retries on both `http://` and `https://`, so plain HTTP against the
mock needs no code change.

`.dockerignore`: `.venv/`, `.git/`, `.claude/`, `**/__pycache__/`, `*.ipynb`,
`.ipynb_checkpoints/`, `docs/`, `dist/`, `build/`, `*.egg-info/`.
**Keep `outputs/` in context** — `ARG MODEL_DIR=outputs` copies the model from there.

The model is baked as a default, not a hard binding: `INFERENCE_ARTIFACT_DIR` still overrides it,
which is how SageMaker's `/opt/ml/model` and a k8s PVC attach. Baking earns the Lambda cold-start
win (`docs/planning.md:54`) and makes the image tag the code+model identity, so rollback is
redeploying the previous tag.

## Refactor
Resist adding a healthcheck or `CMD` args — this image is a batch job that runs once and exits, not
a server. Keep the runtime stage to exactly: OS dep, user, venv, config, model, entrypoint.

## Verify
```
docker build -f docker/inference.Dockerfile -t fc-inference .
docker run --rm fc-inference python -c "import xgboost, inference.gateway; print('ok')"
docker image inspect --format '{{.Size}}' fc-inference
docker run --rm -e INFERENCE_ARTIFACT_DIR=/nonexistent fc-inference   # must fail fast
```
The last one must raise `verify_artifacts_present`'s `FileNotFoundError` and exit non-zero — no
crash-loop, no fallback (`docs/planning.md:56`). Requires `outputs/` to hold a model; run
`uv run python3 src/training/training/daily_product_demand_forecast.py` first if it does not.

Then the cache check: `touch src/inference/inference/preprocess.py`, rebuild, confirm layer 1 is
`CACHED`.

## Commit
`feat(docker): add the inference image with deps/code/model layers`  <!-- committed inside the job worktree; squashed at phase merge -->
