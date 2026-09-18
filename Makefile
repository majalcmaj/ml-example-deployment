
.PHONY: test
test: 
	uv run pytest

.PHONY: check
check:
	uv run ruff check
	$(MAKE) test

.PHONY: test-regression
test-regression:
	uv run pytest tests/regression

# Regenerates src/inference/tests/baseline/{xgb_daily_product_demand.json,forecast_metadata.joblib}
# by running the training notebook at repo root (training must be in the dev venv, which it is
# by default via the root `dev` dependency group). After it runs, `uv run --package inference
# pytest src/inference` will fail if predictions drifted beyond tolerance; if the drift is
# expected, copy the produced outputs/inference_next_day_forecast.csv (from the failing test's
# tmp run_root, printed in the pytest failure) over src/inference/tests/baseline/inference_next_day_forecast.csv.
.PHONY: baseline-inference
baseline-inference:
	uv run python -c "from pathlib import Path; from testkit.notebooks import run_notebook; root = Path.cwd(); run_notebook(root / 'src/training/training/daily_product_demand_forecast.ipynb', cwd=root)"
	cp outputs/xgb_daily_product_demand.json outputs/forecast_metadata.joblib src/inference/tests/baseline/
	uv run --package inference pytest src/inference

