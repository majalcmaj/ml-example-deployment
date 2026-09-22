**ML Take-Home Refactor — Notes**

- 5 working days total, must submit 2 days before actual deadline
- Two stages: (1) refactor notebooks into good, testable, modular code, (2) propose a deployment approach (no actual deploy required, but plans to deploy anyway to self-test)
- Notebook 1: loads training CSV, preprocesses, extracts features, trains/evaluates a gradient boosted tree
- Notebook 2: inference — real external REST API or local mode against training data; preprocesses/extracts features again; simulates uploading results via mock API with a disable switch

**Config & secrets**
- Notebook/Databricks config moved into TOML (config-as-code, versioned)
- TOML currently holds a secret field (known planted issue) — plans to move to a vault (e.g. AWS Secrets Manager) via an abstraction
- Hardcoded constants scattered across notebooks in many places — pull into TOML config alongside everything else

**Local dev / environment parity**
- Docker Compose spins up mock/stub services so the *same* remote code path and config run everywhere — no separate bogus local-only path
- Real inference notebook's purpose (pipeline runs end to end) kept separate from model-quality testing (already covered in training notebook) via integration tests with injected test data
- Open question: does folding local/offline inference entirely into Compose stubs lose a legitimate use case (quick checks, no-network environments)?

**HTTP client**
- Single `requests` Session, exponential backoff, default timeout
- Timeout in TOML config; backoff params (retry count, multiplier) still hardcoded — inconsistency to resolve
- Retries on 408, 429, 502, 503, 504
- Currently retries only side-effect-free methods; wants to extend to POST using a request ID for server-side dedup
- Open questions: honor `Retry-After` on 429? Does the mock API actually support idempotency keys server-side?

**Feature extraction**
- Wants single shared implementation between training and inference; only introduce a strategy pattern if real divergence appears (not speculative) — confirmed YAGNI approach
- No formal feature store — deliberate skip given project scale, shared `forecasting` library covers the need; not an oversight

**Notebooks → production code**
- Eliminating Jupyter notebooks entirely from production (prints → logging, markdown → well-structured code)
- Original notebooks preserved in git history; will reference the commit in README/write-up so they stay discoverable
- Open question: separating genuinely one-off exploration from diagnostic output that should run/log every training run

**Project structure**
- UV workspace in a libs/apps shape: `training` and `inference` are deployable apps; `forecasting`
  (shared feature extraction/data logic, the metadata contract, model load+predict) and `infra`
  (config/logging/correlation-context) are libraries neither app depends on the other through.
- Resolved: yes, data/model concerns wanted their own top-level module — that's `forecasting`. It's
  kept separate from `infra` so the domain kernel depends on nothing but pandas/xgboost/pydantic
  plus a logger, rather than recreating a `common`-style junk drawer under a new name (the
  `package-split` plan).

**Data & model versioning**
- Rejected DVC (too much setup/learning curve for the timeline)
- Chose: hash data + model, store as blobs in git; explicit write-up note that this doesn't scale, real system would use S3 + git as pointer/manifest only

**Deployment — general**
- Two-option proposal: lightweight serverless (Lambda/Fargate) vs. Databricks Jobs, since assignment explicitly offered a choice ("this or that") — read as a signal they want tradeoff reasoning, not just an executed pick
- **Databricks now the primary recommendation**: native MLflow (tracking + model registry, zero setup), native job/run alerting, explicitly mentioned in the assignment
- Lambda kept as the leaner alternative, partly to preserve visible evidence of his own systems-design thinking rather than leaning entirely on what Databricks gives for free

**Model loading — architectural fork**
- Baking model into Docker image doesn't transfer to Databricks (Jobs run on managed clusters/env specs, not arbitrary containers; Container Services only customizes the cluster base image)
- Lambda path: bake model into image as last layer (cold starts near-certain at daily frequency, so avoiding a network call matters more than decoupling releases)
- Databricks path: pull model from MLflow model registry at job start
- Service should fail fast / refuse to start if model unavailable — no fallback, no crash-loop

**Experiment tracking**
- Databricks path: built-in MLflow (tracking + registry)
- Lightweight serverless path: simpler git-based metrics-file approach per training run (the one he'd actually implement)
- Training framed as CI/CD-like: input (code+data) → build (feature extraction+training) → test (eval against thresholds) → human gate to deploy
- Gap: no actual CI/CD for the codebase itself yet — tests/lint on PR, automated build/deploy of inference service

**Drift & monitoring**
- No ground-truth/label feedback loop in the assignment → limited to data/feature drift, not performance metrics
- Categorical features: detect drift, alert on unknown/unseen category values (not just numeric distribution shift)
- Rejected automatic retraining in favor of monitoring + human decision
- Will persist inference input data keyed by request ID so ground truth could be joined later if ever available
- Confirmed data is aggregate sales figures (e.g. units sold), no PII — no compliance/retention concern

**Data validation**
- Feature extraction requires 28 consecutive calendar days of history; need explicit check + clear failure if source API returns fewer days (currently just an unhandled/pretty-printed error, not real validation)
- Open question: existing check only verifies data exists from 27 days before, not the full 28-day window — off-by-one, needs review/fix

**Testing**
- Unit tests: feature extraction correctness
- Integration tests: run model against prepared data, check output shape/columns (not exact values — nondeterministic)
- End-to-end tests: full pipeline against Compose mock services
- Auto-generate a data schema/contract from training data at training time, version alongside model artifact; both training and inference validate against it — retrain that changes feature shape auto-produces a new schema

**Metrics/telemetry abstraction**
- Same interface-abstraction pattern as config/secrets/API client: real impl (CloudWatch/MLflow) vs. local impl (stdout/file) — fully local runnability
- Plans to name this as one coherent architectural principle in the write-up, not four separate decisions

**Observability**
- Replace current printf-based logging with structured logging: timestamp, log level, correlation/run ID on every line
- Generate a run ID (UUID) per scheduled execution, attach to all logs for that run, pass as custom header on outbound calls
- Will note W3C `traceparent` header as a trivial upgrade path if org has OTel infra already — not adopting full OTel SDK now (timeline)

**Alerting**
- CloudWatch: alarm on missing expected metric/heartbeat (catches silent job stoppage, not just bad values)
- Databricks: native Jobs run-status alerting (email/webhook on failure/success/duration threshold) — no separate metrics system needed
- Gap: no latency SLA or performance monitoring defined for the query-side API, despite task explicitly requiring low-latency prediction lookups

**Still open / not yet addressed**
- Rollback mechanism if a newly deployed model performs badly
- Training reproducibility (seed pinning for model + train/test split)
- Dependency/environment pinning (library versions) so dev/prod behavior doesn't silently diverge
- Architecture diagram (Mermaid/draw.io/PNG) for solution design — required by task, not yet produced
- Final submission packaging: repo link or ZIP + diagram + brief architecture notes, per task's "what to submit" section

