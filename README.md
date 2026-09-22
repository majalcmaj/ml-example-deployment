# ml-deployment

Demonstration production-ready ML project: daily product demand forecasting, split into a uv
workspace so `inference` can be deployed without pulling in `training`.

## Layout

See `docs/architecture.md` ("Repository layout") for the directory tree and dependency direction.

## Requirements

- `make` — target runner, `make` with no arguments lists everything
- [`uv`](https://docs.astral.sh/uv/) — Python 3.14 workspace/dependency manager; `uv sync` before
  running anything locally
- [Docker](https://docs.docker.com/get-docker/) with Compose v2 (`docker compose ...`) — for
  `make images` / `make compose-up` / `make test-compose`

## Make targets

Run `make` with no arguments to list all targets with descriptions.

## Git hooks

`make install-hooks` sets up a pre-push hook (via `pre-commit`) that runs lint, type-check, and
unit tests before every `git push`. Run it once after `uv sync`.


## Deployment shape

Training and daily inference are deployed as separate workloads with different execution
profiles — this repo's images stay platform-neutral (the model directory is just a config field),
but the intended target split, the reasoning behind it, and what to do if the chosen platform runs
out of headroom are written up in `docs/architecture.md` and `docs/what_if.md`.

## Origin

`training/main.py` and `inference/main.py` started as `nbconvert` exports of two Jupyter
notebooks (`daily_product_demand_forecast.ipynb`, `daily_product_demand_inference.ipynb`). The
notebooks have since diverged from the refactored scripts and were removed from the working tree;
their last state is preserved at commit `3594a0b`; their original shape is commit `ac5a79d`
(initial commit).
