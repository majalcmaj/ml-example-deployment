<!-- plan-status: pending -->
# Phase 03 — common-testkit

> **Status:** ⬜ PENDING

Read `docs/uv-workspace/prompt.md` first.

## Goal
`common` owns the config loader (env override + project-root path resolution), logger and context.
`testkit` owns the notebook runner and tolerance asserts. Old regression suite stays green.

## Red
New `src/common/common/config_test.py`:
- `load_config(Model, toml_path, env_prefix="X")` returns a pydantic model from TOML.
- `X_DATA_DIR=/tmp/elsewhere` env overrides the `data_dir` field.
- A relative `Path` field resolves against `find_project_root()` (dir containing `uv.lock`).
- `find_project_root()` falls back to cwd when no `uv.lock` is above.
```sh
uv run pytest src/common   # → ImportError: common.config has no load_config
```

## Green
1. `src/common/common/config.py`:
   - `find_project_root(start: Path | None = None) -> Path` — walk up from `start or Path.cwd()`
     to the first dir containing `uv.lock`; else return `start`.
   - `load_config[T: BaseModel](model: type[T], path: Path, *, env_prefix: str) -> T` —
     `tomllib` load; for every field, `os.environ.get(f"{env_prefix}_{name.upper()}")` overrides;
     relative `Path`-typed fields resolved against `find_project_root()`.
     (Side effect worth noting in the commit: `INFERENCE_SECRET_KEY` now overrides the planted
     plaintext secret. Do not expand scope beyond that note.)
2. `git mv src/inference/inference/{logger.py,context.py} src/common/common/`.
   `common/logger.py` → `from common.context import CORRELATION_ID` (whatever it imports today).
3. Minimal consumer patches so the old suite still runs:
   - `src/inference/inference/http_session.py` → `from common.context import ...`.
   - Inference notebook cell 2: `from context import init_context` → `from common.context import init_context`;
     `import logger` → `from common import logger`. **Other flat imports untouched** (phase 04).
4. `src/testkit/testkit/notebooks.py` — `run_notebook(path: Path, cwd: Path) -> None`
   (body of `tests/regression/lib.py:_run_notebook`).
5. `src/testkit/testkit/asserts.py` — `PREDICTION_ATOL`, `METRIC_RTOL`, `BOUND_RTOL`,
   `assert_columns_equal`, `assert_frame_within_tolerance`, `assert_mapping_equal`
   (from `lib.py`). Explicit paths only — no `BASELINE_DIR`, no `load_csv/load_joblib` coupling.

## Refactor
`tests/regression/lib.py` becomes a thin shim re-exporting from `testkit` (dies in phase 06).
Delete the now-empty `src/inference/inference/logger.py`/`context.py` references.

## Verify
```sh
uv run pytest src/common && make test-regression
```

## Commit
`feat(common): config loader with env override; move logger/context; add testkit helpers`
