# TODO

Prioritized task list, pulled from `planning.md`. P0 = required for submission, P1 = strengthens it, P2 = open question / nice-to-have. Check off as done; keep rationale in `planning.md`.

## Deliverable 1: Refactored code

**P0**
- [x] Move hardcoded constants into TOML config
- [x] Structured logging (timestamp, log level, correlation/run ID) replacing printf-based logging
- [x] Regression tests
- [ ] Single shared feature extraction implementation (training + inference) — confirmed concrete duplication: `create_time_features` + category-alignment logic is copy-pasted between the two current notebooks. Concretely: `training/daily_product_demand_forecast.py`'s "Predict incoming-day sales" block (placeholder row + `create_time_features` + `get_dummies`/`reindex`) duplicates `forecasting/features.py`'s `build_future_features()`/`encode_for_model()` almost line for line (training additionally carries `Lower_Bound`/`Upper_Bound`/`Is_Outlier` columns inference doesn't need). The *placement* half is done — the `package-split` plan moved this code into the `forecasting` library alongside training's reuse sites (each now carries a `TODO` naming its target); what remains is collapsing the three `get_dummies`+reindex sites, the two future-row blocks, the two clip/round blocks, and the two date×category panel builds into single implementations.
- [ ] Unit tests: feature extraction correctness
- [x] Integration tests: model output shape/columns against prepared data
- [ ] End-to-end tests: full pipeline against Docker Compose mocks
- [ ] Auto-generate data schema/contract at training time, version with model artifact, validate on both train + inference
- [ ] Fail-fast model loading (no fallback, no crash-loop)
- [ ] Secret → vault abstraction (move off plain TOML field; base config refactor already done per git log)
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
- [ ] Categorical feature drift: alert on unknown/unseen category values
- [ ] Metrics/telemetry abstraction (real impl: CloudWatch/MLflow; local impl: stdout/file)
- [ ] Extend HTTP retry to POST using request ID for server-side dedup (base retry+backoff already done per git log)
- [ ] Persist inference input data keyed by request ID (for future ground-truth join)
- [ ] `_SimulatedGateway.fetch_source_payload` globs every CSV in `data_dir` with no de-dup guard — latent today (one bundled CSV), but a second overlapping CSV would silently double-count sales
- [ ] CI runner image (`ubuntu-24.04`, pinned in `.github/workflows/ci-cd.yml`) needs a periodic bump process — pinning trades `ubuntu-latest`'s silent-drift risk (e.g. the Sept 2026 in-place migration to Ubuntu 26 that `ubuntu-latest` would've absorbed automatically) for staleness risk if nobody revisits the pin

**P2 — open questions**
- [ ] Local/offline inference mode vs folding entirely into Compose stubs — keep or drop?
- [ ] Honor `Retry-After` on 429; confirm mock API actually supports idempotency keys server-side
- [ ] Separate one-off exploration from diagnostics that should run/log every training run — concretely: pull training notebook's inspect/validate EDA cell (`display(raw_sales.head())`, shape prints) out into its own scratch notebook, keep the training pipeline module free of exploration output
- [ ] Note: metadata (`outlier_bounds`, `validation_metrics`, `model_feature_columns`, `categories`) is NOT a separable stage from training — outlier bounds are needed *before* fit (train_mask), validation metrics only exist *after* fit. Don't split it into its own workflow/notebook; it stays a byproduct of the training run. Ruled out this option when considering the training/inference notebook split.
- [x] Does data/model need its own top-level module (vs current training/inference/common)? — Yes: the `package-split` plan extracted it as the `forecasting` library (plus `infra` for cross-cutting config/logging/context), splitting the former `common` junk drawer along a domain/infra seam.
- [ ] Seed pinning for training reproducibility (model + train/test split)
- [ ] Clean up `scripts/ast_similarity.py` (quick AST clone finder for training vs inference scripts): drop single-line/weight heuristics for something principled (e.g. min fingerprint length), add `argparse`, consider `--json` output; or delete it once the shared-feature-extraction P0 item lands and it has served its purpose
- [ ] Pin dependency/environment versions (dev/prod parity)

## Deliverable 2: Solution design doc

**P0**
- [ ] Architecture diagram (Mermaid/draw.io/PNG)
- [ ] Databricks vs Lambda tradeoff write-up
- [ ] Model loading strategy per platform (MLflow registry vs baked-into-image)
- [ ] Drift/monitoring approach write-up
- [ ] Alerting approach write-up (CloudWatch heartbeat / Databricks Jobs run-status)

**P1**
- [ ] Define latency SLA / perf monitoring for the query-side API (task requires low-latency lookups — currently undefined)
- [ ] Note CI/CD gap for the codebase itself (tests/lint on PR, automated build/deploy) — distinct from training-as-CI/CD framing
- [ ] Rollback mechanism if newly deployed model performs badly
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
