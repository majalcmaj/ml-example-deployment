#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# Runs the full Compose stack (mock-api, training, inference) end to end and diffs the
# produced forecast CSV against the committed baseline within PREDICTION_ATOL. The model
# comes from the Compose training run, not the baseline, so this also catches a stale
# src/inference/tests/baseline/ model -- nothing in CI does that today (CLAUDE.md:63-66).

trap 'docker compose down -v --remove-orphans' EXIT

# The inference image bakes a model at build time (ARG MODEL_DIR=outputs); Compose's own
# `--build` has no equivalent of `make image-inference`'s "train first if missing" guard, so
# outputs/ must hold *some* model before `docker compose up --build` runs. The Compose training
# service then overwrites it in the model-artifacts volume, which inference mounts over the
# baked-in copy at /opt/model -- the baked model is a build-time placeholder, never what actually
# gets used.
if [[ ! -f outputs/xgb_daily_product_demand.json ]]; then
    uv run python3 src/training/training/daily_product_demand_forecast.py
fi

rm -f outputs/inference_next_day_forecast.csv

# outputs/ is bind-mounted into the inference container so this script can read the result back
# on the host; the container's non-root uid (10001) rarely matches the host uid, so the bind
# mount needs to be world-writable for the container-side write to succeed.
chmod 777 outputs

docker compose up --build --abort-on-container-exit --exit-code-from inference

uv run python3 scripts/compose_smoke_check.py
