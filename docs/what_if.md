# What if — escalation paths

`docs/architecture.md` is the baseline design. This is a decision record for what changes and
what it costs, in the order you'd actually reach for these — not a roadmap, and not a set of
speculative options to leave permanently open.

## 1. Nearing the 15-minute execution cap or the 10 GB image limit

**Trigger:** the training or inference container starts bumping into Lambda's hard ceilings —
more rows, a heavier model, or a preprocessing step that no longer finishes in minutes.

**Move:** move the batch to an ECS/Fargate scheduled task. It runs the *same image*, the same
entrypoint (`ENTRYPOINT ["python", "-m", "inference.main"]` in
`docker/inference.Dockerfile:44`, or training's equivalent) — no code change. Only the trigger
(EventBridge target: Lambda → Fargate task) and where config comes from move; `infra/config.py:16-30`
already resolves config from either a config file or an env var per field, so this is
infrastructure-side, not application-side.

**Cost:** a task launch is slower to start than a warm-ish Lambda invocation (irrelevant at daily
cadence) and you now pay for a running task instead of Lambda's per-invocation billing — worth it
only once you're actually hitting the ceiling, not preemptively.

**Why Fargate and not SageMaker Processing/Training Jobs**, the more ML-specialized tool for
batch container workloads: considered and declined, same reasoning as #4 below. SageMaker's
batch primitives buy you things this project doesn't need yet (managed spot/distributed
execution, built-in Pipelines integration) at the cost of a container contract the images don't
follow today — SageMaker expects specific `/opt/ml/{input,output,processing}` conventions and its
own env-var surface, not the plain `ENTRYPOINT` + config-file/env-var contract this repo already
has. Fargate runs the *exact* image and entrypoint unchanged; a SageMaker move would mean
reworking the Dockerfiles around SageMaker's I/O conventions for capabilities (distributed
training, spot) this single-model, daily-batch job doesn't use. Revisit if training ever needs
multi-node distribution or spot-driven cost cutting — until then it's operational surface without
payoff, the same bar #4 applies to the model registry.

## 2. Need filtered/indexed queries, per-client auth, or write concurrency the flat S3 object can't express

**Trigger:** multiple clients needing filtered/paginated/indexed lookups (not just "get today's
forecast"), per-client authentication or rate limits, or concurrent-write concerns the baseline's
single S3 object can't express.

**Move:** this is the design `docs/architecture.md` deliberately doesn't build today — a DynamoDB
table (predictions keyed by category/date) behind a read Lambda and API Gateway. Inference's write
target changes from the S3 object to a DynamoDB `PutItem`; the `forecasting` library and the rest
of inference's compute logic don't change, only the sink.

**Cost:** a running query tier (DynamoDB + a read Lambda + API Gateway) instead of a static
object — you pay for indexed lookups and auth/rate-limiting you don't need at low request volume,
in exchange for the flexibility once you do.

## 3. Model too large to bake, or model releases need to decouple from code releases

**Trigger:** the model artifact grows past what's comfortable to embed in an image layer, or the
team wants to ship a new model without cutting a new code release (and vice versa).

**Move:** stop baking. Point `INFERENCE_ARTIFACT_DIR` at a mounted volume, or have the entrypoint
fetch from S3 before `verify_artifacts_present` runs. This is already supported by the existing
contract — `artifact_dir` is a plain config field (`src/inference/inference/config.py:11`) consumed
by `forecasting/artifacts.py:9` and `forecasting/model.py:17-18`, both of which take it as a
parameter rather than assuming `/opt/model`. One env var, zero code change.

**Cost:** you give up the rollback story from `docs/architecture.md` ("rollback = redeploy the
previous image tag") — model version and code version now roll back independently, which means
tracking *which* model version is live becomes its own piece of state instead of being implied by
the image tag. You also reintroduce a startup network dependency (S3 reachability) that baking
was specifically chosen to avoid.

## 4. Need experiment tracking, a model registry, or staged model promotion

**Trigger:** more than one person training models, wanting to compare runs, or needing a
promote-to-production gate that isn't "someone manually copies files into S3."

**Move:** SageMaker Model Registry, or managed MLflow on SageMaker, replacing the S3 + manifest
scheme this design uses today (`docs/planning.md:45`: "hash data + model, store as blobs in git
... real system would use S3 + git as pointer/manifest only"). A lighter specialized option worth
naming before reaching for SageMaker: [DVC](https://dvc.org) layers exactly this S3-blobs +
git-pointer scheme on top of git as an off-the-shelf tool, instead of hand-rolling the
hashing/manifest logic `docs/planning.md` describes. Considered and declined *for now* — not an
oversight. At this scale (one model, one owner, infrequent retraining) a managed registry, or even
adopting DVC, is setup cost with no immediate payoff; it's the right move once more than one of
those stops being true.

**Cost:** operational surface (another managed service to configure and pay for) in exchange for
promotion workflow and run comparison you don't currently need.

## 5. Per-request rather than daily predictions

**Trigger:** the product requirement changes from "predictions computed once a day, queried
later" to predictions computed *at* query time.

**Move:** this isn't a scaling tweak to the batch job — the batch shape is wrong for it entirely.
It becomes a served model behind API Gateway (a real-time inference endpoint, e.g. SageMaker
real-time or a Lambda invoked synchronously per request) instead of a scheduled job writing to
S3 (or, if #2 above was already taken, to DynamoDB). The `forecasting` library — feature
engineering, model load/predict
(`forecasting/model.py`), the artifact contract — is the part that's already shaped to be reused
here; only the entrypoint (batch script vs. request handler) and the trigger (EventBridge vs. API
Gateway) change.

**Cost:** a fundamentally different latency and availability bar — the model now sits on the
request path, so its load time and inference time become user-facing latency, and it needs to be
warm/available continuously rather than once a day. Not a small move; listed last because it's a
different problem, not an extension of this one.

## See also

`docs/architecture.md` for the baseline these branches escalate from — including its S3-direct
read path, which #2 above escalates to DynamoDB + read Lambda + API Gateway, and which #5 above
would replace with a synchronous serving path instead.
