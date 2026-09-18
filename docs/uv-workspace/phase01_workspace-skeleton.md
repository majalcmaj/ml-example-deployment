<!-- plan-status: done; commit=da3a2fa2b3e248438b83f9d9cc423e920376760c; date=2026-09-18 -->
# Phase 01 — workspace-skeleton

> **Status:** ✅ DONE — da3a2fa2b3e248438b83f9d9cc423e920376760c (2026-09-18)

Read `docs/uv-workspace/prompt.md` first.

## Goal
Repo is a uv workspace with members `common`, `inference`, `training`, `testkit` under `src/`.
`uv sync --package inference --no-dev` installs only `inference` + `common`. Old regression suite stays green.

## Red
```sh
uv sync --package inference --no-dev
```
Fails: no workspace, no package named `inference`.

## Green
1. Root `pyproject.toml` becomes the virtual workspace root:
   ```toml
   [project]
   name = "ml-deployment"
   version = "0.1.0"
   description = "A demonstration production-ready ML project"
   readme = "README.md"
   requires-python = ">=3.14"
   dependencies = []

   [dependency-groups]
   dev = ["common", "inference", "training", "testkit",
          "ruff>=0.15.17", "debugpy>=1.8.21", "jupyter>=1.1.1"]

   [tool.uv]
   package = false

   [tool.uv.workspace]
   members = ["src/*"]

   [tool.uv.sources]
   common = { workspace = true }
   inference = { workspace = true }
   training = { workspace = true }
   testkit = { workspace = true }

   [tool.ruff.lint]
   extend-select = ["B", "C4", "RET", "SIM", "UP", "ANN", "PTH", "ARG", "TCH"]
   ```
   Plain `uv sync` installs every member through the dev group (no `--all-packages` needed).
2. Member `pyproject.toml` files (all: `requires-python = ">=3.14"`, `version = "0.1.0"`,
   `[build-system] requires = ["uv_build>=0.12.0,<0.13.0"]`, `build-backend = "uv_build"`,
   `[tool.uv.build-backend] module-root = ""`):
   - `src/common/pyproject.toml` — `name = "common"`, deps `pandas>=3.0.5`, `pydantic>=2.13.5`.
   - `src/inference/pyproject.toml` — `name = "inference"`, deps `common`, `joblib>=1.6.0`,
     `pandas>=3.0.5`, `pydantic>=2.13.5`, `xgboost>=3.4.1`, `requests>=2.32`;
     `[dependency-groups] dev = ["testkit"]`; `[tool.uv.sources] common/testkit = { workspace = true }`.
   - `src/training/pyproject.toml` — `name = "training"`, deps `common`, `joblib`, `matplotlib>=3.11.1`,
     `pandas`, `scikit-learn>=1.9.0`, `xgboost`; dev `testkit`; same sources.
   - `src/testkit/pyproject.toml` — `name = "testkit"`, deps `pytest>=9.1.0`, `nbclient>=0.10`,
     `nbformat>=5.10`, `ipykernel`, `pandas`, `joblib`. No build excludes (never shipped).
3. Moves (`git mv`):
   - `src/inference/{__init__.py,config.py,config.toml,config_test.py,context.py,http_session.py,logger.py,daily_product_demand_inference.ipynb}` → `src/inference/inference/`
   - `src/daily_product_demand_forecast.ipynb` → `src/training/training/`
   - `src/common/{__init__.py,config.py,consts.py,features.py}` → `src/common/common/`
   - `git rm src/__init__.py`; create `src/training/training/__init__.py`, `src/testkit/testkit/__init__.py` (empty).
4. `common` is now importable from the venv, so kill the hacks:
   - Inference notebook cell 2: delete the `sys.path.insert(0, os.path.abspath(".."))` line. **Only that line.**
   - `tests/regression/conftest.py`: delete the `src/common` copytree + its TODO comment;
     copytree source `src/inference` → `src/inference/inference`.
   - `tests/regression/lib.py`: training notebook path → `src/training/training/...`, cwd back to
     `outputs_root` (drop `/ "src"` + its comment); inference notebook path → `src/inference/inference/...`,
     cwd `outputs_root / "src" / "inference" / "inference"`.
5. `uv lock && uv sync`.

## Refactor
- Root `[project.dependencies]` empty — every third-party dep now lives on exactly one member.
- Drop the `doc/TODO.md` P2 bullet about the harness copying `src/common`.

## Verify
```sh
uv sync --package inference --no-dev && uv pip list | grep -E "^(common|inference|training|testkit) "
# → common, inference only
uv sync && make test-regression   # green, same count as before
```

## Commit
`build: convert to uv workspace with common/inference/training/testkit members`
