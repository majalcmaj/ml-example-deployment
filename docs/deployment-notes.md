# Deployment Proposal — Working Notes

## Overall direction
- Primary recommendation: **AWS**, using **SageMaker** for model registry/versioning, not Databricks — chosen because it's the platform he knows best and can defend confidently in a follow-up conversation.
- **MLflow** (open source client) is kept regardless of host for experiment tracking — the tracking API is identical whether pointed at a local file store or a hosted server, since Databricks' MLflow is the same open source project under a managed tracking server.
- Keep **Lambda** for inference serving (already his working pattern) rather than adopting SageMaker hosting, Step Functions, or SageMaker Pipelines — avoids over-engineering the take-home with orchestration he'd struggle to defend.
- CloudWatch (or any cross-cloud observability push from Databricks) explicitly **out of scope for now** — mentioned as a future consideration in the write-up rather than implemented, to avoid unnecessary credential/batching complexity for a side concern the assignment isn't testing.

## Pipeline structure (three pipelines)
1. **CI pipeline** — runs on every code change: unit tests, plus a smoke test doing a lightweight train + lightweight inference against tiny sample data to catch broken code before it touches real infrastructure.
2. **Training pipeline** — trains on real data, logs to MLflow, and on success pushes the model into the SageMaker Model Registry; promotes through dev → staging → prod.
3. **Inference pipeline** — pulls whichever model version is marked current for that environment and runs it (batch on a schedule, or backing the real-time Lambda).

## Model version resolution ("Docker latest tag" pattern)
- Inference pipeline resolves which model to use by querying the SageMaker Model Registry for whichever version is tagged/aliased **prod** at execution time — not via an environment variable (which would just move the "what needs updating" problem elsewhere).
- Promotion = repointing the alias. Nothing else needs to change or redeploy.
- **Rollback** = repoint the prod alias back to the previous model version. No redeploy needed, since inference always reads the current alias on its next run.

## Promotion gating — maturity curve
- Start with **manual human approval**: surfaced comparison metrics, a human reviews before promoting staging → prod. Deliberate choice for the early lifetime of the project since non-obvious issues are more likely to surface on first deployments.
- Later, once the humans doing deployments observe the process is reliable and requires minimal intervention (mostly just approving), consider **automatic promotion based on metric thresholds**, with **alerting** as the safety net once it's automated.

## Data versioning
- Would bring in **DVC** alongside MLflow if scope allowed: DVC handles actual data version tracking (git-like diffing/history, data stored in S3, pointer files in repo); MLflow logs a reference to the DVC version used per training run, since MLflow itself only references data, it doesn't version it the way DVC does.
- (Note: separately, for *this specific take-home's* actual implementation — as opposed to the AWS/SageMaker proposal being discussed here — he'd already decided against DVC in favor of a lighter git-blob-hashing approach given the timeline; worth reconciling which applies where in the final write-up.)

## Atomic deployment of breaking changes (new data dimension + model + inference code change together)
Problem: a new training run adds a new feature dimension, requiring both a new model and new inference code — the new pipeline won't work with the old model, and vice versa.

Best practice, in order of rigor:
1. **Schema validation as the safety net** — auto-generated, versioned data schema (already planned) means inference fails loudly at startup if the schema it expects doesn't match what the model was trained against, rather than silently producing garbage.
2. **Ordered rollout** — deploy the new inference code first (it keeps serving the *old* model since the alias hasn't moved yet); once the new code is confirmed healthy, promote the new model version and repoint the alias. The two land together for consumers even though deployed as separate steps.
3. **Compatibility tagging (more rigorous, likely out of scope but worth naming)** — tag the model registry entry with the git commit hash of the inference code it's compatible with, so promotion can assert compatibility and refuse otherwise.
- Suggested framing for the write-up: implement (1) and (2) as the actual answer, mention (3) as the more rigorous version for a larger system.

## Anticipated curveball questions (interview prep)
1. How does staging → prod promotion actually happen? → Answered above (manual → automatic maturity curve).
2. How does inference know which model version is current? → Answered above (registry alias, not env var).
3. How do you roll back a bad model? → Answered above (repoint alias).
4. How is training data versioned / how would drift be caught? → Answered above (DVC + MLflow reference); on drift specifically, no ground-truth feedback loop exists in this assignment, so drift monitoring would be limited to data/feature drift, not performance metrics; inference inputs would be persisted keyed by request ID so ground truth could be joined later if it ever becomes available.
5. How do you deploy a breaking model + inference code change atomically? → Answered above (schema validation + ordered rollout, tagging as future rigor).
