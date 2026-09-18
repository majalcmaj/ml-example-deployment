<!-- plan-status: pending -->
# phase04 · Job 01 — inference

> **Status:** ⬜ PENDING

Read `docs/uv-workspace/prompt.md` and the parent phase file first. This job runs in its own git
worktree; touch only the files in its slice (jobs are file-disjoint).

## Goal
`uv run --package inference pytest src/inference` passes with `training` absent from the venv,
using committed baseline artifacts. Inference notebook uses package-qualified imports and
`CONFIG.*` dirs.

## Red
Write first:
- `src/inference/tests/conftest.py` — session fixture `run_root`: tmp dir; copy repo `data/` in;
  seed `outputs/` from `src/inference/tests/baseline/{xgb_daily_product_demand.json,forecast_metadata.joblib}`;
  set `INFERENCE_DATA_DIR`, `INFERENCE_ARTIFACT_DIR`, `INFERENCE_OUTPUT_DIR` via `monkeypatch`
  (session-scoped `MonkeyPatch`); run the notebook with `testkit.notebooks.run_notebook(nb_path, cwd=run_root)`.
- `src/inference/tests/test_inference_notebook.py` — `pytestmark = pytest.mark.e2e`; compare
  `run_root/outputs/inference_next_day_forecast.csv` against `baseline/inference_next_day_forecast.csv`
  with `testkit.asserts` (`assert_columns_equal`, `assert_frame_within_tolerance(atol=PREDICTION_ATOL)`).
```sh
uv run --package inference pytest src/inference
# → fails: flat imports, cwd heuristic misses tmp dirs, baseline model json missing
```

## Green
1. `src/inference/inference/config.py`: `Config` gains `data_dir: Path`, `artifact_dir: Path`,
   `output_dir: Path`; `CONFIG = load_config(Config, Path(__file__).parent / "config.toml", env_prefix="INFERENCE")`.
   `config.toml` adds `data_dir = "data"`, `artifact_dir = "outputs"`, `output_dir = "outputs"`.
2. Notebook — **minimal rule**:
   - cell 2 import lines: `from config import CONFIG` → `from inference.config import CONFIG`;
     `from http_session import create_http_session` → `from inference.http_session import ...`.
   - cell 4: replace the candidate-dir search with `ARTIFACT_DIR = CONFIG.artifact_dir`; keep the
     fail-fast `FileNotFoundError`. Data dir lookup → `CONFIG.data_dir`.
   - cell 13: output path → `CONFIG.output_dir`.
   Nothing else.
3. Baseline generation (once, at repo root, `training` installed in dev venv):
   ```sh
   uv run jupyter nbconvert --to notebook --execute src/training/training/daily_product_demand_forecast.ipynb --output-dir /tmp/nbout
   cp outputs/xgb_daily_product_demand.json outputs/forecast_metadata.joblib src/inference/tests/baseline/
   git mv tests/regression/baseline/inference_next_day_forecast.csv src/inference/tests/baseline/
   uv run --package inference pytest src/inference   # then copy the produced csv over the baseline csv
   ```
   Capture these steps as Makefile target `baseline-inference`.
4. `git rm tests/regression/test_inference_notebook.py`.

## Refactor
Code side only (conftest, config module). Notebook untouched beyond Green.

## Verify
```sh
uv sync --package inference && uv run --package inference pytest src/inference
# fallback if --package doesn't pull the member dev group:
uv sync --package inference && uv run --no-sync pytest src/inference
uv run --no-sync python -c "import training"   # → ModuleNotFoundError
```

## Commit
`feat(inference): package-qualified imports, config-driven dirs, standalone e2e baseline`  <!-- squashed at phase merge -->
