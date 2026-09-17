# TODO

Prioritized task list, pulled from `planning.md`. P0 = required for submission, P1 = strengthens it, P2 = open question / nice-to-have. Check off as done; keep rationale in `planning.md`.

## Deliverable 1: Refactored code

**P0**
- [x] Move hardcoded constants into TOML config
- [ ] Structured logging (timestamp, log level, correlation/run ID) replacing printf-based logging
- [ ] 28-consecutive-calendar-day history check: fix/verify off-by-one (currently checks day 27, not 28) + clear error if API returns fewer days than required
- [ ] Single shared feature extraction implementation (training + inference)
- [ ] Unit tests: feature extraction correctness
- [ ] Integration tests: model output shape/columns against prepared data
- [ ] End-to-end tests: full pipeline against Docker Compose mocks
- [ ] Auto-generate data schema/contract at training time, version with model artifact, validate on both train + inference
- [ ] Fail-fast model loading (no fallback, no crash-loop)
- [ ] Secret → vault abstraction (move off plain TOML field; base config refactor already done per git log)

**P1**
- [ ] Categorical feature drift: alert on unknown/unseen category values
- [ ] Metrics/telemetry abstraction (real impl: CloudWatch/MLflow; local impl: stdout/file)
- [ ] Extend HTTP retry to POST using request ID for server-side dedup (base retry+backoff already done per git log)
- [ ] Persist inference input data keyed by request ID (for future ground-truth join)

**P2 — open questions**
- [ ] Local/offline inference mode vs folding entirely into Compose stubs — keep or drop?
- [ ] Honor `Retry-After` on 429; confirm mock API actually supports idempotency keys server-side
- [ ] Separate one-off exploration from diagnostics that should run/log every training run
- [ ] Does data/model need its own top-level module (vs current training/inference/common)?
- [ ] Seed pinning for training reproducibility (model + train/test split)
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
- [ ] Note feature store deliberately skipped (shared `common` module sufficient at this scale)
- [ ] Data/model versioning approach + scaling caveat (git-blob hashing doesn't scale; real system = S3 + git pointer/manifest)

**P2**
- [ ] Mention W3C `traceparent` header as future OTel upgrade path (not adopting full OTel now)

## Submission
- [ ] Package repo link or ZIP
- [ ] Attach diagram + brief architecture notes
- [ ] Reference original notebooks' git commit in README so they stay discoverable
