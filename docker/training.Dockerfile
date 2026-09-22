# syntax=docker/dockerfile:1
#
# Training image: reads TRAINING_DATA_DIR, writes TRAINING_OUTPUT_DIR. Pure compute step — no
# model, no data, no baseline baked in. Two-stage uv sync so the dependency layer stays cached
# across code-only changes (astral's uv-docker-example pattern).

FROM ghcr.io/astral-sh/uv:0.9.30-python3.14-bookworm-slim@sha256:7cf77f594be8042dab6daa9fe326f90962252268b4f120a7f5dccce4d947e6c1 AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Deps layer: every workspace member's pyproject.toml is needed to resolve the shared uv.lock,
# even though only `training` gets installed here.
COPY pyproject.toml uv.lock ./
COPY src/infra/pyproject.toml src/infra/pyproject.toml
COPY src/forecasting/pyproject.toml src/forecasting/pyproject.toml
COPY src/training/pyproject.toml src/training/pyproject.toml
COPY src/inference/pyproject.toml src/inference/pyproject.toml
COPY src/testkit/pyproject.toml src/testkit/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package training --no-install-workspace

# Code layer: only the packages training actually depends on.
COPY src/infra src/infra
COPY src/forecasting src/forecasting
COPY src/training src/training
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package training

FROM python:3.14-slim-bookworm@sha256:82bc3c539b8813ada9d68c63b40158fa002f7f33de9bf3312a3dfdc0620dff56 AS runtime

RUN useradd --create-home --uid 10001 app

ENV TRAINING_CONFIG_FILE=/etc/forecast/training.toml \
    PATH="/app/.venv/bin:$PATH"

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY deploy/config/training.toml /etc/forecast/training.toml

# Docker seeds a named volume's initial content and ownership from whichever container mounts it
# first. Compose's `model-artifacts` volume is shared with the inference image at a different
# path (/opt/model) and a different uid, so this image's own non-root uid must match inference's
# (10001) -- otherwise whichever container wins the race to populate the volume locks the other
# out of it.
RUN mkdir -p /var/forecast/outputs && chown app:app /var/forecast/outputs

WORKDIR /var/forecast
USER app

ENTRYPOINT ["python", "-m", "training.daily_product_demand_forecast"]
