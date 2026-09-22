# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.9.30-python3.14-bookworm-slim@sha256:7cf77f594be8042dab6daa9fe326f90962252268b4f120a7f5dccce4d947e6c1 AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# --- layer 1: third-party dependencies (changes rarely) ---
# `uv.lock` is one file for the whole workspace, so `uv sync --frozen` needs every member's
# pyproject.toml present to resolve against it -- even members this image never installs.
# Only their *manifests* are copied here, not their source (that comes in layer 2, source-only,
# per package); `--package inference` below still means only inference + its deps land in
# /app/.venv. A per-package lockfile would let us skip copying training's/testkit's manifests,
# but uv workspaces don't support that split, and duplicating lockfiles by hand would reintroduce
# the version-drift problem workspaces exist to prevent -- not worth it for a few COPY lines.
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

FROM python:3.14-slim-bookworm@sha256:82bc3c539b8813ada9d68c63b40158fa002f7f33de9bf3312a3dfdc0620dff56 AS runtime
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
