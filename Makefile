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

.PHONY: image-inference
image-inference:  ## Build the inference image (trains first if outputs/ has no model)
	@test -f outputs/xgb_daily_product_demand.json || uv run python3 src/training/training/daily_product_demand_forecast.py
	docker build -f docker/inference.Dockerfile -t fc-inference .

.PHONY: image-training
image-training:  ## Build the training image
	docker build -f docker/training.Dockerfile -t fc-training .

.PHONY: image-mock-api
image-mock-api:  ## Build the mock sales API image
	docker build -f docker/mock-api.Dockerfile -t fc-mock-api .

.PHONY: images
images: image-inference image-training image-mock-api  ## Build all three images

.PHONY: compose-up
compose-up:  ## Run the local Compose stack (train -> serve -> infer -> upload)
	docker compose up --build

.PHONY: compose-down
compose-down:  ## Tear down the local Compose stack and its volumes
	docker compose down -v --remove-orphans

.PHONY: compose-retrain
compose-retrain:  ## Rerun training only (it exits after one run) without touching mock-api/inference
	docker compose run --rm training

.PHONY: test-compose
test-compose:  ## Full pipeline against the Compose stack, diffed against the inference baseline
	./scripts/compose_smoke.sh

.PHONY: type-check
type-check:  ## pyright over src (catches return-type mismatches ruff misses)
	uv run pyright

.PHONY: lint
lint:  ## ruff check + pyright (static checks only, no tests)
	uv run ruff check
	$(MAKE) type-check

.PHONY: check
check:  ## ruff check + pyright + full test suite
	uv run ruff check
	$(MAKE) type-check
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

# Deploy stages are stubs: no infra exists yet (no Dockerfile/k8s/deploy scripts), these just
# stand in for the real thing so the CD pipeline shape (gates, environments) is wired up now.
.PHONY: deploy-staging
deploy-staging:  ## [stub] Deploy to staging
	@echo "[stub] would deploy $$(git rev-parse --short HEAD) to staging — no real deploy logic yet"

.PHONY: deploy-prod
deploy-prod:  ## [stub] Deploy to prod
	@echo "[stub] would deploy $$(git rev-parse --short HEAD) to prod — no real deploy logic yet"

BRANCH ?= $(shell git rev-parse --abbrev-ref HEAD)
.PHONY: deploy-dev
deploy-dev:  ## [stub] Per-branch ephemeral dev deployment (BRANCH=<name> to override)
	@echo "[stub] would deploy $$(git rev-parse --short HEAD) to ephemeral env dev-$$(printf '%s' '$(BRANCH)' | tr -c 'a-zA-Z0-9-' '-' | tr 'A-Z' 'a-z') — no real deploy logic yet"
