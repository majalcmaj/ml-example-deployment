<!-- plan-status: pending -->
# Phase 01 — infra-package

> **Status:** ⬜ PENDING

Read `docs/package-split/prompt.md` first.

## Goal
Extract the cross-cutting helpers (`load_config`/`find_project_root`, `get_logger`,
`CORRELATION_ID`/`init_context`) out of `common` into a new `infra` workspace member, so `common`
is left holding domain code only. Pure moves — no behaviour change.

## Red
Both must fail before any edit:

```
uv run python3 -c "import infra.config"                       # ModuleNotFoundError: infra
grep -rn "common\.\(config\|logger\|context\)" src/ | wc -l   # 11 today, across 8 files (2 of them inside common itself)
```

## Green
1. `git mv` into a new member, contents untouched apart from one import line:
   | from | to |
   |---|---|
   | `src/common/common/config.py` | `src/infra/infra/config.py` |
   | `src/common/common/logger.py` | `src/infra/infra/logger.py` |
   | `src/common/common/context.py` | `src/infra/infra/context.py` |
   | `src/common/common/config_test.py` | `src/infra/infra/config_test.py` |
   | `src/common/common/__init__.py` | copy to `src/infra/infra/__init__.py` (empty) |
2. `src/infra/infra/logger.py:3` — `from common.context import CORRELATION_ID` → `from infra.context import CORRELATION_ID`.
3. New `src/infra/pyproject.toml`: clone `src/common/pyproject.toml`, name `infra`, deps
   `pydantic>=2.13.5` only (logger and context are stdlib). Keep the same `uv_build` block and
   `wheel-exclude = ["**/*_test.py", "**/conftest.py"]`.
4. Rewrite the consumer imports (6 files outside `common`): `common.config` → `infra.config` (`training/config.py:3`,
   `inference/config.py:3`), `common.logger` / `from common import logger` → `infra.logger` /
   `from infra import logger` (`training/daily_product_demand_forecast.py:23`,
   `inference/{preprocess,forecaster,gateway,daily_product_demand_inference}.py`),
   `common.context` → `infra.context` (`inference/http_session.py:1`,
   `inference/daily_product_demand_inference.py:4`).
5. Root `pyproject.toml`: add `infra` to the `dev` group and to `[tool.uv.sources]` as
   `{ workspace = true }`. Add `infra` to `src/training/pyproject.toml` and
   `src/inference/pyproject.toml` deps + their `[tool.uv.sources]` (both still depend on `common`
   at this point — that link dies in phase 02).
6. `uv sync`.

`src/common/` must still be a valid member here, holding `consts.py`, `features.py`,
`preprocessing.py`, `forecast_metadata.py` and their two unit tests. It needs no `infra` dep —
none of those four modules import config, logging or context.

## Refactor
- `grep -rn "common\.\(config\|logger\|context\)" src/` returns nothing.
- `src/infra/infra/__init__.py` stays empty — no re-exports, matching the existing convention of
  importing by submodule path.
- No shim or re-export module left behind in `common`.

## Verify
- `uv run ruff check` and `make type-check` clean. Watch `TCH` on the rewritten import blocks.
- `make test` green, **same pass count as before the phase**.
- `git status --porcelain src/training/tests/baseline src/inference/tests/baseline` is empty —
  no baseline may be touched in this phase.
- `git diff -M --stat` shows the four files as renames, not add+delete.

## Commit
`refactor(workspace): extract infra package from common`

Trailer: `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`
