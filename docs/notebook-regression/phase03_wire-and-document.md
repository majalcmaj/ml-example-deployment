<!-- plan-status: done; commit=98dc8472d93bf99f9b28b4cc5bb7a72a8693a259; date=2026-09-18 -->
# Phase 03 — wire-and-document

> **Status:** ✅ DONE — 98dc8472d93bf99f9b28b4cc5bb7a72a8693a259 (2026-09-18)

Read `docs/notebook-regression/prompt.md` first.

## Goal
`make test-regression` runs just the notebook regression suite, and
`tests/regression/README.md` tells the next person (refactoring the notebooks) what's compared,
why those tolerances, and exactly how to intentionally refresh the baseline after a legitimate
change — so they don't have to reverse-engineer `lib.py` to do that safely.

## Context (read before starting)
- Current `Makefile`:
  ```
  .PHONY: test
  test:
  	uv run pytest

  .PHONY: check
  check:
  	uv run ruff check
  	$(MAKE) test
  ```
  `make test` already runs the regression suite (no `testpaths` restriction in `pyproject.toml`)
  — this phase adds a convenience target for running *just* the regression suite, it does not
  change what `make test`/`make check` cover.

## Red
There's no documented, single command to run only `tests/regression/` (today you'd have to know
to type `uv run pytest tests/regression` by hand) and no doc explaining the tolerance values or
how to refresh the baseline after an intentional model/feature change. Confirm `make test-regression`
doesn't exist: `make test-regression` → `make: *** No rule to make target 'test-regression'.`

## Green
- Add to `Makefile`:
  ```
  .PHONY: test-regression
  test-regression:
  	uv run pytest tests/regression
  ```
- Write `tests/regression/README.md` covering:
  - What this suite does (run notebook → diff against `baseline/`) and why (catch regressions
    while refactoring `src/` notebooks into non-notebook code).
  - The artifact map: which file in `outputs/` pairs with which file in `baseline/`, and which
    notebook produces it.
  - The tolerance constants in `lib.py` (`PREDICTION_ATOL`, `METRIC_RTOL`, `BOUND_RTOL`) and the
    one-line reason for each (float noise vs. rounding jitter vs. near-exact-expected).
  - Why the raw XGBoost model JSON isn't diffed directly (see plan README's "why not bespoke").
  - **How to intentionally refresh the baseline** after a real, reviewed change: run
    `make test-regression` once to regenerate `outputs/`, diff `outputs/*` against
    `tests/regression/baseline/*` by hand (or via `git diff --no-index`), confirm the change is
    expected, then copy `outputs/*` over the corresponding `baseline/*` files and commit with a
    message explaining *why* the baseline moved.

## Refactor
N/A — this phase only adds a Makefile target and documentation; nothing to simplify.

## Verify
- `make test-regression` — runs only `tests/regression/`, green.
- `make check` — ruff + full `make test` — still green (Makefile change is additive).
- Read `tests/regression/README.md` once more against actual `lib.py` contents to confirm no
  drift between doc and code before committing.

## Commit
`docs(regression): add make target and usage guide for the regression suite`
