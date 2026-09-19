.PHONY: sync
sync:
	uv sync

.PHONY: test
test:
	uv run pytest

.PHONY: test-unit
test-unit:
	uv run pytest -m "not e2e"

.PHONY: test-e2e
test-e2e:
	uv run pytest -m e2e

.PHONY: test-inference
test-inference:
	uv run --package inference pytest src/inference

.PHONY: test-training
test-training:
	uv run --package training pytest src/training

.PHONY: test-mutation
test-mutation:
	./scripts/mutation_check.sh

.PHONY: check
check:
	uv run ruff check
	$(MAKE) test

.PHONY: sync-inference
sync-inference:
	uv sync --package inference --no-dev

.PHONY: sync-training
sync-training:
	uv sync --package training --no-dev

.PHONY: build
build:
	uv build --all-packages

# Regenerates src/inference/tests/baseline/{xgb_daily_product_demand.json,forecast_metadata.joblib}
# by running the training script at repo root (training must be in the dev venv, which it is
# by default via the root `dev` dependency group). After it runs, `make test-inference` will fail
# if predictions drifted beyond tolerance; if the drift is expected, copy the produced
# outputs/inference_next_day_forecast.csv over src/inference/tests/baseline/inference_next_day_forecast.csv.
.PHONY: baseline-inference
baseline-inference:
	uv run python3 src/training/training/daily_product_demand_forecast.py
	cp outputs/xgb_daily_product_demand.json outputs/forecast_metadata.joblib src/inference/tests/baseline/
	$(MAKE) test-inference
