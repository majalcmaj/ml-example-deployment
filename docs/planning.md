**ML Take-Home Refactor — Notes**

- 5 working days total, must submit 2 days before actual deadline
- Two stages: (1) refactor notebooks into good, testable, modular code, (2) propose a deployment approach (no actual deploy required, but plans to deploy anyway to self-test)
- Notebook 1: loads training CSV, preprocesses, extracts features, trains/evaluates a gradient boosted tree
- Notebook 2: inference — real external REST API or local mode against training data; preprocesses/extracts features again; simulates uploading results via mock API with a disable switch

**Config & secrets**
- Notebook/Databricks config moved into TOML (config-as-code, versioned)
- Planted secret is gone: `inference/config.toml` no longer carries `secret_key`. The API token comes
  from `INFERENCE_API_TOKEN` at runtime through the retained `SecretsProvider` seam
  (`gateway.py`'s `_EnvSecretsProvider`); `_DatabricksSecretsProvider` and the `dbutils` lookup were
  deleted with it
- Vault-backed implementation behind that same seam (e.g. AWS Secrets Manager) is still open — the
  env var is the ship-now backend, not the final one
- Hardcoded constants scattered across notebooks in many places — pull into TOML config alongside everything else

**Local dev / environment parity**
- Docker Compose spins up mock/stub services so the *same* remote code path and config run everywhere — no separate bogus local-only path
- Resolved: simulation mode is dropped. `_SimulatedGateway` and `config.simulation_mode` are gone
  from production code; the payload fixture moved to `src/inference/tests/stub_gateway.py`
  (`StubSalesGateway`), injected through the `SalesGateway` protocol for tests only. Locally and in
  Compose, inference always runs the real `_RestGateway` over HTTP against the stdlib mock API
  (`docker/mock-api/server.py`) — one code path everywhere, no bogus local-only branch
- Real inference notebook's purpose (pipeline runs end to end) kept separate from model-quality testing (already covered in training notebook) via integration tests with injected test data

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
- Decided: Docker-first, targets split **by workload**, not by platform. The images themselves stay
  platform-neutral (see "Model loading" below), so where each one runs is a deploy-time choice, not
  a code choice — this split *is* the tradeoff reasoning the assignment's "this or that" phrasing
  was asking for
  - Training → SageMaker Training Job or an ECS/Fargate task. Not Lambda: 15-minute execution cap,
    no GPU, 10 GB image/`/tmp` limits. Fine against today's 20k-row CSV, doesn't generalise, and a
    training run is exactly the kind of unbounded batch job Lambda is the wrong tool for
  - Daily inference batch → Lambda container image. Seconds of compute, a ~2.5 MB model, one
    invocation a day — cold start is irrelevant at that cadence, and the baked-in model (below)
    avoids a per-invocation fetch
- Databricks demoted from "primary recommendation" to named alternative: still attractive for its
  native MLflow registry and Jobs alerting, but the container-first path above is now built and
  running (`docker/`, `docker-compose.yml`), and Databricks Jobs run on managed clusters/env specs
  rather than arbitrary containers — adopting it now means re-deriving the same image split for its
  Container Services (which only customizes the cluster base image), not reusing what already works
- SageMaker Model Registry / managed MLflow on SageMaker considered as the managed replacement for
  the S3 + git-manifest versioning scheme noted above under "Data & model versioning" — declined for
  now: it's an operational dependency this project doesn't need at 20k rows and a single model, and
  the git-blob approach is already flagged as not scaling; revisit if the manifest scheme actually
  becomes the bottleneck rather than pre-adopting it

**Model loading — platform-neutral by config, not by fork**
- Resolved: no fork. `artifact_dir` is a plain config field (`inference/config.py:11`, mirrored on
  `training`) consumed by `forecasting/artifacts.py:9`'s `verify_artifacts_present` and
  `forecasting/model.py:17`'s `load_model` — neither function knows or cares whether the directory
  is a baked image layer or a mounted volume
- The inference image bakes the model into `/opt/model` as the last Dockerfile layer
  (`docker/inference.Dockerfile`) — cold starts near-certain at daily-batch cadence, so avoiding a
  network fetch on invocation matters more than decoupling model releases from image releases
- The same image, unmodified, would instead read a SageMaker-mounted `/opt/ml/model` or any other
  platform's mount point by overriding `INFERENCE_ARTIFACT_DIR` — one env var changes, zero code
  changes
- Databricks path (if ever taken): pull from the MLflow model registry at job start instead — still
  just a different value for the same config field, backed by a different fetch step before the
  process starts, not a different code path inside it
- Service still fails fast / refuses to start if the model is unavailable — no fallback, no
  crash-loop (`verify_artifacts_present`, unchanged)

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
- Image reproducibility ≠ model reproducibility: digest-pinned base images and `uv sync --frozen`
  (both Dockerfiles) make the *build environment* reproducible, not the *model* — without the seed
  pinning above (`docs/TODO.md:68`), two image builds from the same commit can still train slightly
  different models
- Dependency/environment pinning (library versions) so dev/prod behavior doesn't silently diverge
- Architecture diagram (Mermaid/draw.io/PNG) for solution design — required by task, not yet produced
- Final submission packaging: repo link or ZIP + diagram + brief architecture notes, per task's "what to submit" section

