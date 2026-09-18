# notebook-regression — plan

Versionable red/green/refactor plan. One phase doc per step + a `prompt.md` runner.

## How to run
`/plan execute phase1` (one phase at a time). See `prompt.md` for the ceremony and guardrails.

## Why these steps (and why not bespoke)

Goal: catch regressions in `src/daily_product_demand_forecast.ipynb` (training) and
`src/daily_product_demand_inference.ipynb` (inference) while they get refactored, by running
each notebook and diffing its artifacts against a frozen golden baseline.

- **Execution**: `nbclient` (already installed transitively via the `jupyter` dev dep) executes
  notebooks headlessly — the industry-standard way to run a `.ipynb` outside Jupyter, no bespoke
  runner needed. Considered `papermill` (nicer parameterization) but it isn't installed and
  parameterization isn't needed here, so it would be an unjustified new dependency. Considered
  `jupyter nbconvert --execute` as a subprocess but `nbclient`'s in-process API is simpler to
  wrap and assert on. `nbclient`/`nbformat` are made **explicit** dev dependencies in
  `pyproject.toml` rather than relying on transitive install via `jupyter` (user requested
  explicit deps).
- **Comparison**: tolerance-based (`numpy`/`pandas` tolerance helpers), not exact-match or a
  bespoke deep-diff library — floats from XGBoost/pandas can drift by float noise even with a
  fixed `random_state`, and exact-match would make the suite flaky. Not diffing the raw XGBoost
  model JSON dump directly either: nested tree-structure diffing with tolerance is fiddly and
  isn't what "model unchanged" means to a consumer — the model's *behavior* (its predictions and
  validation metrics, already persisted to `outputs/`) is the meaningful signal, and comparing
  those is simpler.
- **Producer/compare seam** (bespoke, justified): the notebook-execution step is isolated behind
  two functions (`produce_training_artifacts` / `produce_inference_artifacts`) in `lib.py` so
  the comparison tests never import or know about notebooks. User is planning to replace these
  notebooks with scripts; when that happens only these two functions' bodies change.
- **Baseline**: the existing, untracked `outputs/` directory (one clean pre-refactor run) is
  frozen into `tests/regression/baseline/` as the golden reference, per user's explicit choice —
  no baseline-generation harness needed, it already exists.

## Phases
| id | title |
|---|---|
| phase01 | baseline-and-training-regression |
| phase02 | inference-output-and-regression |
| phase03 | wire-and-document |
