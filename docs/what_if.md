# What if — escalation paths

`docs/architecture.md` is the baseline design. This is a decision record for what changes and
what it costs, in the order you'd actually reach for these — not a roadmap, and not a set of
speculative options to leave permanently open.

## 1. Nearing the 15-minute execution cap or the 10 GB image limit

**Trigger:** the training or inference container starts bumping into Lambda's hard ceilings —
more rows, a heavier model, or a preprocessing step that no longer finishes in minutes.

**Move:** move the batch to an ECS/Fargate scheduled task. It runs the *same image*, the same
entrypoint (`ENTRYPOINT ["python", "-m", "inference.daily_product_demand_inference"]` in
`docker/inference.Dockerfile:44`, or training's equivalent) — no code change. Only the trigger
(EventBridge target: Lambda → Fargate task) and where config comes from move; `infra/config.py:16-30`
already resolves config from either a config file or an env var per field, so this is
infrastructure-side, not application-side.

**Cost:** a task launch is slower to start than a warm-ish Lambda invocation (irrelevant at daily
cadence) and you now pay for a running task instead of Lambda's per-invocation billing — worth it
only once you're actually hitting the ceiling, not preemptively.

## 2. Model too large to bake, or model releases need to decouple from code releases

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

## 3. Need experiment tracking, a model registry, or staged model promotion

**Trigger:** more than one person training models, wanting to compare runs, or needing a
promote-to-production gate that isn't "someone manually copies files into S3."

**Move:** SageMaker Model Registry, or managed MLflow on SageMaker, replacing the S3 + manifest
scheme this design uses today (`docs/planning.md:45`: "hash data + model, store as blobs in git
... real system would use S3 + git as pointer/manifest only"). Considered and declined *for now* —
not an oversight. At this scale (one model, one owner, infrequent retraining) a managed registry
is setup cost with no immediate payoff; it's the right move once more than one of those stops
being true.

**Cost:** operational surface (another managed service to configure and pay for) in exchange for
promotion workflow and run comparison you don't currently need.

## 4. Per-request rather than daily predictions

**Trigger:** the product requirement changes from "predictions computed once a day, queried
later" to predictions computed *at* query time.

**Move:** this isn't a scaling tweak to the batch job — the batch shape is wrong for it entirely.
It becomes a served model behind API Gateway (a real-time inference endpoint, e.g. SageMaker
real-time or a Lambda invoked synchronously per request) instead of a scheduled job writing to
DynamoDB. The `forecasting` library — feature engineering, model load/predict
(`forecasting/model.py`), the artifact contract — is the part that's already shaped to be reused
here; only the entrypoint (batch script vs. request handler) and the trigger (EventBridge vs. API
Gateway) change.

**Cost:** a fundamentally different latency and availability bar — the model now sits on the
request path, so its load time and inference time become user-facing latency, and it needs to be
warm/available continuously rather than once a day. Not a small move; listed last because it's a
different problem, not an extension of this one.

## See also

`docs/architecture.md` for the baseline these branches escalate from, and for the
designed-not-built low-latency read path (DynamoDB + read Lambda + API Gateway) that #4 above
would replace with a synchronous serving path instead.
