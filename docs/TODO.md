# TODO

Prioritized task list, pulled from `planning.md`. P0 = required for submission, P1 = strengthens it, P2 = open question / nice-to-have. Check off as done; keep rationale in `planning.md`.

## Deliverable 1: Refactored code

**P0**
- [x] Move hardcoded constants into TOML config
- [x] Structured logging (timestamp, log level, correlation/run ID) replacing printf-based logging
- [x] Regression tests
- [x] Single shared feature extraction implementation (training + inference) — `training` now calls
  `forecasting.features.build_future_features`/`encode_for_model` and `forecasting.model.make_forecast`
  directly instead of duplicating them (reordered to save the model + build `ForecastMetadata`
  before the next-day-forecast step, since `make_forecast` reloads the model from disk).
  `encode_for_model` was split into `one_hot_encode_categories`/`reindex_to_contract` so training's
  pre-fit `X_train`/`X_validation` encoding (which needs a `ForecastMetadata` that doesn't exist yet)
  can share the same primitives too. Still open: the two date×category panel builds
  (`training/preprocess.py` vs `inference/preprocess.py`) remain separate — not addressed by this
  pass.
- [ ] Unit tests: feature extraction correctness
- [x] Integration tests: model output shape/columns against prepared data
- [x] End-to-end tests: full pipeline against Docker Compose mocks — `make test-compose`
  (`scripts/compose_smoke.sh`), wired into CI after `test-e2e` (phase 05)
- [ ] Auto-generate data schema/contract at training time, version with model artifact, validate on both train + inference
- [ ] Fail-fast model loading (no fallback, no crash-loop)
- [ ] Secret → vault abstraction — env-var backend shipped (`INFERENCE_API_TOKEN` read by
  `_EnvSecretsProvider`, `SecretsProvider` seam retained, `_DatabricksSecretsProvider` deleted); an
  AWS Secrets Manager / vault-backed implementation behind the same seam is still open
- [ ] 28-consecutive-calendar-day history check: fix/verify off-by-one (currently checks day 27, not 28) + clear error if API returns fewer days than required
- [ ] 28-day history check only bounds the pooled min/max date span (`preprocess.py`), not per-category contiguity — a category closed for several days mid-window still passes and gets zero-filled by `aggregate_per_category` instead of raised. Frame this as a data-drift / distribution guardrail (detect and reject fabricated zero-history), not a quick fix to the existing check.
- [ ] Documentation: Improve readme, add runbooks (e.g. what happens when regression tests break - whether to accept change or investigate), add arch diagram

**P1**
- [ ] Workspace-level train→infer integration e2e test (uv-workspace split follow-up): the
  per-member e2e suites (`src/inference/tests`, `src/training/tests`) are hermetic — each
  compares against its own committed baseline (`forecast_metadata.joblib`,
  `xgb_daily_product_demand.json`, prediction CSVs), independently of the other member. This
  makes `inference`'s test pass even if its baseline model has gone stale relative to
  `training`'s current code, because nothing currently re-derives inference's baseline from a
  fresh training run as part of CI — a dev has to remember to run `make baseline-inference`
  whenever training-side logic (features, hyperparams, notebook) changes, and nothing flags it
  if they forget. Add one additional test, living outside both `src/inference` and
  `src/training` (e.g. `tests/integration/`, using `testkit` like the old pre-split regression
  suite did), that runs train → assert → feeds that freshly-trained model straight into
  inference → assert, with no committed model baseline — only that flow proves inference is
  still correct against training's *current* output. This needs the full workspace synced
  (both members installed together), so it can't run as part of the `make sync-inference`
  deploy-subset check; it's a slower dev/CI-only safety net layered on top of the per-member
  suites, not a replacement for them.

  **Narrowed, not closed, by `make test-compose`** (phase 05): the Compose smoke test trains a
  fresh model, feeds it straight into inference over the real HTTP path, and diffs the result
  against `src/inference/tests/baseline/inference_next_day_forecast.csv` within `PREDICTION_ATOL`
  — catching exactly the staleness case this item was written for (`scripts/compose_smoke.sh:5-8`
  says so explicitly). What it *doesn't* give: this item's baseline-free design, so a drift that's
  "wrong but within tolerance" of the stale baseline still passes; and it needs Docker, where a
  workspace-level pytest wouldn't. Keeping this item open for the baseline-free, Docker-free
  variant; `make test-compose` covers the CI-facing staleness risk in the meantime.
- [ ] Categorical feature drift: alert on unknown/unseen category values
- [ ] Metrics/telemetry abstraction (real impl: CloudWatch/MLflow; local impl: stdout/file)
- [ ] Extend HTTP retry to POST using request ID for server-side dedup (base retry+backoff already done per git log)
- [ ] POST retry above is now testable end to end: `docker/mock-api/server.py` gives it a real
  local HTTP target (previously this needed hitting the real service to verify)
- [x] Strip matplotlib out of the training script rather than suppressing it — both `plt.show()`
  blocks (outlier before/after chart, actual-vs-predicted daily chart) removed; the `matplotlib`
  dependency and `MPLBACKEND=Agg` (`docker/training.Dockerfile`) stopgap are gone. Underlying stats
  (outlier counts, IQR bounds, MAE/RMSE/WMAPE) are still logged and saved into `ForecastMetadata`;
  ad-hoc visual exploration belongs in a disposable scratch notebook, not the production script —
  no MLflow/artifact-tracker exists in this repo to make a saved PNG useful.
- [ ] Persist inference input data keyed by request ID (for future ground-truth join)
- [ ] CI runner image (`ubuntu-24.04`, pinned in `.github/workflows/ci-cd.yml`) needs a periodic bump process — pinning trades `ubuntu-latest`'s silent-drift risk (e.g. the Sept 2026 in-place migration to Ubuntu 26 that `ubuntu-latest` would've absorbed automatically) for staleness risk if nobody revisits the pin

**P2 — open questions**
- [ ] Honor `Retry-After` on 429; confirm mock API actually supports idempotency keys server-side
- [ ] Separate one-off exploration from diagnostics that should run/log every training run — concretely: pull training notebook's inspect/validate EDA cell (`display(raw_sales.head())`, shape prints) out into its own scratch notebook, keep the training pipeline module free of exploration output
- [ ] Note: metadata (`outlier_bounds`, `validation_metrics`, `model_feature_columns`, `categories`) is NOT a separable stage from training — outlier bounds are needed *before* fit (train_mask), validation metrics only exist *after* fit. Don't split it into its own workflow/notebook; it stays a byproduct of the training run. Ruled out this option when considering the training/inference notebook split.
- [x] Does data/model need its own top-level module (vs current training/inference/common)? — Yes: the `package-split` plan extracted it as the `forecasting` library (plus `infra` for cross-cutting config/logging/context), splitting the former `common` junk drawer along a domain/infra seam.
- [ ] Seed pinning for training reproducibility (model + train/test split)
- [ ] Clean up `scripts/ast_similarity.py` (quick AST clone finder for training vs inference scripts): drop single-line/weight heuristics for something principled (e.g. min fingerprint length), add `argparse`, consider `--json` output; or delete it once the shared-feature-extraction P0 item lands and it has served its purpose
- [x] Pin dependency/environment versions (dev/prod parity) — digest-pinned `uv` and `python` base
  images plus `uv sync --frozen` in both `docker/inference.Dockerfile` and
  `docker/training.Dockerfile`

## Deliverable 2: Solution design doc

**P0**
- [ ] Architecture diagram (Mermaid/draw.io/PNG)
- [ ] Databricks vs Lambda tradeoff write-up
- [x] Model loading strategy per platform (MLflow registry vs baked-into-image) — written up in
  `docs/architecture.md` / `docs/what_if.md`
- [ ] Drift/monitoring approach write-up
- [ ] Alerting approach write-up (CloudWatch heartbeat / Databricks Jobs run-status)

**P1**
- [ ] Define latency SLA / perf monitoring for the query-side API (task requires low-latency lookups — currently undefined)
- [ ] Note CI/CD gap for the codebase itself (tests/lint on PR, automated build/deploy) — distinct from training-as-CI/CD framing
- [x] Rollback mechanism if newly deployed model performs badly — the image tag is the code+model
  identity (model is baked in, `docs/planning.md`), so rollback is redeploying the previous tag
- [ ] Note feature store deliberately skipped (shared `forecasting` library sufficient at this scale)
- [ ] Data/model versioning approach + scaling caveat (git-blob hashing doesn't scale; real system = S3 + git pointer/manifest)

**P2**
- [ ] Mention W3C `traceparent` header as future OTel upgrade path (not adopting full OTel now)

## Submission
- [ ] Package repo link or ZIP
- [ ] Attach diagram + brief architecture notes
- [ ] Reference original notebooks' git commit in README so they stay discoverable
- [ ] Delete the `.ipynb` notebooks from the working tree once the README references their git
  commit (item above) — they've drifted from the `.py` scripts and CLAUDE.md's "Known drift"
  note about them should be removed in the same change
