.DEFAULT_GOAL := help

.PHONY: help
help:  ## Show this help
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'

.PHONY: sync
sync:  ## uv sync — full workspace + dev tools
	uv sync

.PHONY: test
test:  ## Full test suite (testpaths = src)
	uv run pytest

.PHONY: test-unit
test-unit:  ## Unit tests only (-m "not e2e")
	uv run pytest -m "not e2e"

.PHONY: test-e2e
test-e2e:  ## E2e tests only (-m e2e)
	uv run pytest -m e2e

.PHONY: test-inference
test-inference:  ## Inference package tests
	uv run --package inference pytest src/inference

.PHONY: test-training
test-training:  ## Training package tests
	uv run --package training pytest src/training

.PHONY: test-mutation
test-mutation:  ## Prove e2e suites catch regressions (scripts/mutation_check.sh)
	./scripts/mutation_check.sh

.PHONY: check
check:  ## ruff check + full test suite
	uv run ruff check
	$(MAKE) test

.PHONY: sync-inference
sync-inference:  ## Deploy-subset check: inference only, no dev deps
	uv sync --package inference --no-dev

.PHONY: sync-training
sync-training:  ## Training only, no dev deps
	uv sync --package training --no-dev

.PHONY: build
build:  ## uv build --all-packages
	uv build --all-packages

# Regenerates src/inference/tests/baseline/{xgb_daily_product_demand.json,forecast_metadata.joblib}
# by running the training script at repo root (training must be in the dev venv, which it is
# by default via the root `dev` dependency group). After it runs, `make test-inference` will fail
# if predictions drifted beyond tolerance; if the drift is expected, copy the produced
# outputs/inference_next_day_forecast.csv over src/inference/tests/baseline/inference_next_day_forecast.csv.
.PHONY: baseline-inference
baseline-inference:  ## Regenerate inference baseline model + metadata from fresh training run, then test-inference
	uv run python3 src/training/training/daily_product_demand_forecast.py
	cp outputs/xgb_daily_product_demand.json outputs/forecast_metadata.joblib src/inference/tests/baseline/
	$(MAKE) test-inference

# TODO: remove
.PHONY: code-duplication-check
code-duplication-check:  ## AST similarity between training and inference scripts
	uv run scripts/ast_similarity.py src/inference/inference/daily_product_demand_inference.py src/training/training/daily_product_demand_forecast.py
