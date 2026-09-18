<!-- plan-status: pending -->
# Phase 02 — wheel-excludes-pytest

> **Status:** ⬜ PENDING

Read `docs/uv-workspace/prompt.md` first.

## Goal
In-package `*_test.py` files are discovered by pytest and never ship in a wheel.

## Red
```sh
uv build --package inference && unzip -l dist/inference-*.whl | grep -E "_test\.py"
# → prints inference/config_test.py  (must be empty)
uv run pytest --collect-only -q | grep config_test
# → prints nothing  (must list it)
```

## Green
1. In `src/common`, `src/inference`, `src/training` `pyproject.toml`:
   ```toml
   [tool.uv.build-backend]
   module-root = ""
   wheel-exclude = ["**/*_test.py", "**/conftest.py"]
   ```
   If `**/*_test.py` does not match, use `*_test.py` (glob anchoring undocumented offline — the
   `unzip -l` check decides).
2. Root `pyproject.toml`:
   ```toml
   [tool.pytest.ini_options]
   testpaths = ["src", "tests"]
   python_files = ["test_*.py", "*_test.py"]
   addopts = "--import-mode=importlib"
   markers = ["e2e: executes a notebook end-to-end"]
   ```
   `importlib` mode avoids basename clashes between the future per-member `conftest.py` /
   `config_test.py`. `tests` stays in `testpaths` until phase 06 removes it.

## Refactor
Replace the `inference/config_test.py` stub (`pass`) with a real test: load the bundled
`config.toml`, assert `simulation_mode` and the HTTP timeout parse into `Config`.

## Verify
```sh
rm -rf dist && uv build --all-packages && for w in dist/*.whl; do unzip -l "$w" | grep -E "_test\.py|conftest"; done
# → no output
uv run pytest --collect-only -q | grep -c _test.py   # ≥ 1
make test-regression                                  # green
```

## Commit
`build: exclude in-package tests from wheels; configure pytest discovery`
