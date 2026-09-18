<!-- plan-status: pending -->
# phase04 · Job 02 — training

> **Status:** ⬜ PENDING

Read `docs/uv-workspace/prompt.md` and the parent phase file first. This job runs in its own git
worktree; touch only the files in its slice (jobs are file-disjoint).

## Goal
`uv run --package training pytest src/training` passes. Training notebook reads
`DATA_DIR` / `OUTPUT_DIR` from `training.config.CONFIG`.

## Red
Write first:
- `src/training/tests/conftest.py` — session fixture `run_root`: tmp dir; copy repo `data/` in;
  set `TRAINING_DATA_DIR`, `TRAINING_OUTPUT_DIR`; run the notebook via
  `testkit.notebooks.run_notebook(nb_path, cwd=run_root)`.
- `src/training/tests/test_training_notebook.py` — port of `tests/regression/test_training_notebook.py`
  onto `testkit.asserts`; `pytestmark = pytest.mark.e2e`; baselines from `src/training/tests/baseline/`.
```sh
uv run --package training pytest src/training
# → fails: training.config missing; notebook cwd heuristic finds no data/
```

## Green
1. `src/training/training/config.py`: pydantic `Config(data_dir: Path, output_dir: Path)`;
   `CONFIG = load_config(Config, Path(__file__).parent / "config.toml", env_prefix="TRAINING")`.
   `src/training/training/config.toml`: `data_dir = "data"`, `output_dir = "outputs"`.
2. Notebook — **minimal rule**:
   - import cell: add `from training.config import CONFIG`.
   - cell 4: `DATA_DIR = CONFIG.data_dir` (replace cwd search).
   - cell 24: `OUTPUT_DIR = CONFIG.output_dir`.
   Nothing else.
3. `git mv tests/regression/baseline/{forecast_metadata.joblib,next_day_product_forecast.csv} src/training/tests/baseline/`.
4. `git rm tests/regression/test_training_notebook.py`.

## Refactor
Code side only (conftest, config module). Notebook untouched beyond Green.

## Verify
```sh
uv sync --package training && uv run --package training pytest src/training
# fallback: uv sync --package training && uv run --no-sync pytest src/training
```

## Commit
`feat(training): package member with config-driven dirs and e2e baseline`  <!-- squashed at phase merge -->
