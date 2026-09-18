<!-- plan-status: done; commit=2fbd5d9; date=2026-09-18 -->
# Phase 06 — cleanup

> **Status:** ✅ DONE — 2fbd5d9 (2026-09-18)

Read `docs/uv-workspace/prompt.md` first.

## Goal
No legacy `tests/` tree. Makefile covers dev, per-member and deploy-subset flows. README explains
the layout.

## Red
```sh
test -d tests/regression && echo "legacy suite still present"   # prints
make test-regression                                            # targets a dir with no tests left
```

## Green
1. `git mv tests/regression/README.md src/testkit/README.md` (fix paths inside); `git rm -r tests/`.
2. Root `pyproject.toml`: `testpaths = ["src"]`.
3. Makefile (replace wholesale):
   ```make
   sync:               uv sync
   test:               uv run pytest
   test-unit:          uv run pytest -m "not e2e"
   test-e2e:           uv run pytest -m e2e
   test-inference:     uv run --package inference pytest src/inference
   test-training:      uv run --package training pytest src/training
   test-mutation:      ./scripts/mutation_check.sh
   check:              uv run ruff check && $(MAKE) test
   sync-inference:     uv sync --package inference --no-dev
   sync-training:      uv sync --package training --no-dev
   build:              uv build --all-packages
   baseline-inference: (kept from phase 04)
   ```
4. `README.md`: one short section — layout tree, dependency arrows, `make` targets, how to deploy a
   subset (`make sync-inference`).

## Refactor
Grep for `tests.regression`, `lib.py`, `test-regression` — zero hits. `uv run ruff check` clean.

## Verify
```sh
make check
make sync-inference && uv pip list | grep -E "^(training|testkit) "   # → empty
make sync-training  && uv pip list | grep -E "^(inference|testkit) "  # → empty
make build && for w in dist/*.whl; do unzip -l "$w" | grep -E "_test\.py|conftest|tests/"; done  # → empty
git diff main -- '*.ipynb' | grep '^[-+]    "' | grep -vE 'import|_DIR|sys.path|CONFIG\.'      # → empty
```

## Commit
`chore: remove legacy regression suite; add workspace Makefile targets`
