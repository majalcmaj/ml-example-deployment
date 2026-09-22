# Ultrareview findings — 2026-09-22

Full-repo critical review (base: initial commit `ac5a79d3`). Scope: task.md fulfillment,
docs (architecture.md / README / what_if.md / TODO.md) vs. code, code smells, best practices.
Two clusters: live correctness/reliability bugs in shipped code, and documentation credibility rot.

## P0 — live correctness/reliability bugs

1. **`src/infra/infra/logger.py:16`** — `get_logger()` unconditionally calls
   `logger.addHandler(syslog)` on every call; `logging.getLogger(name)` returns the same cached
   singleton, so repeated calls pile up duplicate handlers. Called inside function bodies rather
   than at import in `src/inference/inference/preprocess.py:40`, `src/inference/inference/main.py:81`,
   `src/forecasting/forecasting/model.py:38`, `src/infra/infra/metrics.py:25` — every additional
   call in the same process duplicates subsequent log lines. Live risk under any warm/reused-process
   deployment.

2. **`scripts/mutation_check.sh:94`** — mutation 7's `sed` pattern matches the literal string
   `row["Predicted_Qty"]`, but `result_upload.py` was refactored (commit 3407876) to use
   `row[PREDICTED_QTY_COLUMN]`. The sed silently no-ops, so `uv run pytest src/inference -m e2e`
   passes trivially. CLAUDE.md's documented guarantee ("mutation 7 must fail this suite") is not
   being exercised at all — a real regression corrupting uploaded `predicted_quantity` would go
   undetected.

3. **`src/inference/inference/preprocess.py:46`** — rows whose category isn't in
   `metadata.categories` are silently dropped (`valid_rows &= sales[category_column].isin(...)`)
   with no count/metric, despite `docs/architecture.md` describing exactly this drop count as the
   categorical-drift signal to record. An upstream category rename/typo or new product line loses
   rows from a day's forecast with zero log line, metric, or alert.

4. **`src/inference/inference/preprocess.py:70`** — the 28-day history check only bounds the
   *pooled* min/max date span across all categories. A single category with a multi-day gap
   mid-window still passes (other categories keep the pooled span at 28 days) and gets zero-filled
   by `aggregate_per_category` (line 87) instead of raising — that category's lag/rolling features
   are built over fabricated zeros, silently degrading its forecast, unmonitored.

5. **`src/inference/inference/http_session.py:17`** — `Retry(total=3, ..., status_forcelist=[...])`
   is built without `allowed_methods`, so it inherits urllib3's default allowlist, which excludes
   POST. `RestGateway.upload_inference_results` (`gateway.py:71`) POSTs the forecast through this
   same session — on a 502/503 it gets zero automatic retry, unlike GET calls on the identical
   session. `docs/TODO.md` understates this: it frames remaining POST-retry work as only needing a
   request ID for server-side dedup, but the base retry doesn't cover POST at all today.

## P1 — documentation credibility (stale/dangling, actively misleading)

6. **`docs/planning.md` is deleted** (commit `184146e`, "rm planning doc") but still cited with
   specific line numbers as the authoritative rationale source by `CLAUDE.md:116`,
   `docs/TODO.md:3,119`, `docs/architecture.md:172,202,207,231`, and `docs/what_if.md:73,77`.
   Load-bearing design decisions (public S3 bucket policy justification, decision not to
   auto-retrain on drift) now rest on unverifiable citations; CLAUDE.md's own instruction to
   consult `docs/planning.md` before proposing structural changes points nowhere.

7. **`docs/TODO.md` is stale in both directions**:
   - Line 25: "Fail-fast model loading (no fallback, no crash-loop)" marked open, but already fully
     implemented (`forecasting/artifacts.py:9` `verify_artifacts_present`, `forecasting/model.py:17-21`
     `load_model`, both raise `FileNotFoundError` with no fallback; `inference/main.py:84` calls
     `verify_artifacts_present` before any network/feature work).
   - Line 29: describes an off-by-one ("currently checks day 27, not 28") in the 28-day check, but
     `preprocess.py:70`'s `latest_date - pd.Timedelta(days=27)` is already a correct 28-day-inclusive
     lower bound — this framing is stale (distinct from the still-genuinely-open per-category
     contiguity gap in finding 4, which TODO.md's next bullet does correctly describe).
   - Line 84: "Seed pinning for training reproducibility" marked open, but
     `src/training/training/main.py:49` already hardcodes `RANDOM_SEED = 42`, threaded into
     `XGBRegressor(random_state=random_seed, ...)` (`train_model.py:25`). The doc's own remaining
     nondeterminism caveat (`architecture.md:153`) points at the wrong lever — `n_jobs=-1`
     (`train_model.py:26`) means multi-threaded histogram building isn't bit-identical across runs
     even with a fixed seed, and that's the actual open item.

8. **`docs/deployment-notes.md`** proposes a materially different, contradicting design (SageMaker
   Model Registry + alias-based promotion, MLflow, DVC) than the adopted `docs/architecture.md` /
   `docs/what_if.md`, which explicitly decline SageMaker Registry, MLflow, and DVC as YAGNI-for-now.
   Reads as private interview-prep notes ("chosen because it's the platform he knows best and can
   defend confidently", "Anticipated curveball questions (interview prep)") rather than
   submission-quality material, and admits internally it needs reconciling — that reconciliation
   was never done before commit.

9. **`docs/architecture.md:120`** — several precise file:line citations anchoring the doc's claims
   have drifted from the current Dockerfiles/Compose file (e.g. the model-artifact `COPY` layer and
   `ENTRYPOINT` line cited in `docs/what_if.md:13` no longer match their stated line numbers),
   undermining a doc set whose main credibility device is exact code citations.

10. **`Makefile:118`** — the comment above `deploy-staging`/`deploy-prod`/`deploy-dev` reads "Deploy
    stages are stubs: no infra exists yet (no Dockerfile/k8s/deploy scripts)" — but
    `docker/*.Dockerfile` exist, are built by `make images`, and are exercised end-to-end in CI via
    `make test-compose`. Directly contradicts `docs/architecture.md`'s own opening claim that the
    three container images and the Compose stack are actually built.

11. **`docs/architecture.md:340`** — `task.md` requires the system to "run as autonomously as
    possible with minimal manual intervention," but architecture.md's "Pipeline wiring" section
    requires every new model to clear a human `workflow_dispatch` + required reviewer before
    reaching production, without reconciling this against the literal requirement. Defensible design
    choice, but asserted elsewhere as full autonomy without naming this as a deliberate concession.

## P2 — coverage / design gaps

12. **`src/forecasting/forecasting/features_test.py`** — the entire unit-test file for
    `forecasting/features.py`, described in `architecture.md` as the shared "domain kernel" for both
    training and inference, contains exactly one test (`is_weekend` flags Saturday/Sunday).
    `build_future_features`, `encode_for_model`, `one_hot_encode_categories`, and
    `reindex_to_contract` have zero unit coverage. `task.md` deliverable 1 explicitly asks for
    "basic tests" as a craftsmanship signal, and `docs/TODO.md` checks off "single shared feature
    extraction implementation" as done — a regression in `reindex_to_contract`'s fill/reindex logic
    (enforces train/infer column parity) would only surface indirectly through an e2e baseline diff
    within `PREDICTION_ATOL=1`, letting a small but real encoding bug hide inside that tolerance.

13. **`src/forecasting/forecasting/metadata.py:34`** — `ForecastMetadata.outlier_bounds` is declared
    as a bare `pd.DataFrame` under `arbitrary_types_allowed=True`, so pydantic performs zero
    structural validation on the train↔infer contract's most complex field; `ForecastMetadata.load`
    deserializes the whole object via joblib/pickle with no integrity check. Inert today (models are
    only baked into images at build time), but `docs/what_if.md` #3 explicitly proposes fetching the
    artifact from S3 at startup — at that point a tampered or corrupted object in that bucket becomes
    arbitrary deserialization on load, not just a bad prediction, and neither doc calls out or
    mitigates that cost.

## Status (2026-09-22)

Implemented: #2, #1, #5, #3 (drop-count now logged), #6, #7, #8. **#4 was attempted and reverted**:
the naive per-category row-count-vs-window-span heuristic flags nearly every category in the real
dataset as "gapped," because categories legitimately sell zero units on many days and the raw
sales-event feed has no row for a zero-sale day — indistinguishable from an actual reporting outage
without a signal this feed doesn't carry. Left open in `docs/TODO.md` with that finding recorded so
it isn't re-attempted the same way.

## Suggested fix order

1. #2 — dead mutation-7 sed pattern defeats the project's own safety net; fix first.
2. #1 — logger handler accumulation; cheap fix (cache/guard `addHandler`).
3. #5 — add `allowed_methods` to cover POST retry.
4. #3 / #4 — wire up drop-count metric and per-category contiguity check in preprocessing.
5. #6 / #7 / #8 / #10 — doc cleanup, fast wins (fix dangling `planning.md` refs, correct TODO.md
   status, reconcile or remove `deployment-notes.md`, fix Makefile comment).
6. #9 / #11 — re-sync citations, name the autonomy/review-gate tradeoff explicitly.
7. #12 / #13 — backfill `features.py` unit tests; revisit metadata validation before the S3
   fetch-at-startup escalation in what_if.md #3 ships.
