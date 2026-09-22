<!-- plan-status: done; commit=8adb6b7262e0e517e5a4b13c822a4ed430d0aa77; date=2026-09-22 -->
# Phase 04 — images

> **Status:** ✅ DONE — 8adb6b7262e0e517e5a4b13c822a4ed430d0aa77 (2026-09-22)

Read `docs/docker-deploy/prompt.md` first.

## Goal
Three minimal, layer-cacheable images — inference, training, mock API — each buildable on its own,
with no Compose or Makefile wiring yet (that is phase 05).

## Red
No image exists: `Makefile:78-79` says so outright ("no infra exists yet (no Dockerfile/k8s/deploy
scripts)"), and a repo-wide search for `Dockerfile`/`compose`/`Containerfile` returns nothing.
Each job's Red is the concrete `docker build` + `docker run` check named in its own file.

## Green
Three file-disjoint jobs, run in isolated worktrees:

| job | owns |
|---|---|
| 01 inference-image | `.dockerignore`, `docker/inference.Dockerfile`, `deploy/config/inference.toml` |
| 02 training-image  | `docker/training.Dockerfile`, `deploy/config/training.toml` |
| 03 mock-api-image  | `docker/mock-api.Dockerfile`, `docker/mock-api/server.py` |

`.dockerignore` is owned by **job 01 only** — jobs 02 and 03 must not create or edit it.

### Constraints every job shares
- **Two-stage `uv sync` split**, or the dependency layer will not cache. The workspace-wide
  `uv.lock` means *every* member's `pyproject.toml` must be copied for resolution, even when only
  one package is installed:
  `uv sync --frozen --no-dev --package <name> --no-install-workspace` (third-party layer), then
  copy sources, then `uv sync --frozen --no-dev --no-editable --package <name>` (workspace layer).
  This is astral's own `uv-docker-example` pattern.
- **`libgomp1` in the runtime stage** for any image that imports xgboost. The manylinux wheel links
  `libgomp.so.1` and does not vendor it; without the package the image dies at import with
  `libgomp.so.1: cannot open shared object file`.
- **Multi-stage**: build in `ghcr.io/astral-sh/uv:…-python3.14-bookworm-slim`, run from
  `python:3.14-slim-bookworm` with only `/app/.venv` copied across. `--no-editable` installs the
  workspace packages properly into the venv, so the runtime stage needs no source tree, no `uv`,
  and no `uv.lock`.
- **Pin base images by digest** and keep `--frozen` — reproducibility is the stated point of this
  work (`docs/TODO.md:54`).
- **Absolute paths only** in `deploy/config/*.toml`. There is no `uv.lock` in a lean image, so
  `find_project_root` (`infra/config.py:8-13`) falls back silently to `cwd`; absolute values skip
  the walk entirely (`config.py:29`).
- **Non-root** user, `ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never`.

## Refactor
Factor the shared builder preamble so `inference.Dockerfile` and `training.Dockerfile` differ only
in `--package`, the extra layers, and the entrypoint — but **do not** introduce a base image built
from this repo just to hold six identical lines. Duplicating a small preamble beats a build-order
dependency between two images that deploy independently.

## Verify
Each job verifies its own image. At phase level, after the merge:
```
docker build -f docker/inference.Dockerfile -t fc-inference .
docker build -f docker/training.Dockerfile  -t fc-training  .
docker build -f docker/mock-api.Dockerfile  -t fc-mock-api  .
make lint && make test-unit && make test-e2e
```
The host test suite must be unaffected — this phase adds files, it does not change Python.

Then re-run the inference build after touching one `src/inference/inference/*.py` file: the
dependency layer must report `CACHED`. If it rebuilds, the two-stage split is wrong.

## Commit
`feat(docker): add inference, training and mock-api images`
