<!-- plan-status: done; commit=ac5542c7c52be58c260eb07a42e4f4c58bfecad5; date=2026-09-22 -->
# phase06 · Job 01 — architecture-and-what-if

> **Status:** ✅ DONE — ac5542c7c52be58c260eb07a42e4f4c58bfecad5 (2026-09-22)

Read `docs/docker-deploy/prompt.md` and the parent phase file first. This job runs in its own git
worktree; touch only the files in its slice (jobs are file-disjoint).

## Goal
The two missing submission artefacts: an architecture diagram with notes
(`docs/TODO.md:59`, P0, required by `docs/task.md:24`), and a written escalation path for when the
Lambda inference batch stops being the right fit.

**Owns:** `docs/architecture.md`, `docs/what_if.md` — both new.

## Red
Neither file exists. `docs/task.md:24` asks for "a rough diagram (Mermaid, draw.io, PNG) and a few
paragraphs"; `docs/TODO.md:59-63` lists the diagram, the platform tradeoff, the model-loading
strategy, drift/monitoring and alerting as unticked P0 items for deliverable 2.

## Green
### `docs/architecture.md`
Mermaid flow, plus a few paragraphs. The shape:

- EventBridge (daily) → **training job** (Fargate task or SageMaker Training Job, the phase-04
  training image) reading raw sales from S3
- → versioned model + metadata artifacts in S3
- → CI builds and tags the **inference image** with those artifacts baked in (image tag = code +
  model identity)
- → EventBridge (daily) → **inference Lambda** (container image) → GET the sales API, POST the
  forecast
- → predictions written to DynamoDB
- → **API Gateway + a read Lambda** serving low-latency client queries
- CloudWatch alarm on a missing heartbeat metric from the daily job (`docs/planning.md:91` — catches
  silent stoppage, not just bad values)

State plainly that the low-latency query path is **designed, not built** — `docs/task.md:20`
requires it, nothing in this repo implements it, and `docs/TODO.md:66` already flags the undefined
latency SLA.

Cover the three write-up items the diagram implies: model-loading strategy per platform
(`docs/TODO.md:61`), why the model is baked rather than fetched, and how rollback works (redeploy
the previous image tag — `docs/TODO.md:68`).

Add one honest caveat: **image reproducibility is not model reproducibility.** Seed pinning is
still open (`docs/TODO.md:52`), so two builds of the same commit produce different models today.

### `docs/what_if.md`
The escalation path, in order of what you would actually reach for:

1. **Nearing the 15-minute cap or 10 GB image limit** → move the batch to an ECS/Fargate scheduled
   task. Same image, same entrypoint, no code change; only the trigger and the config source move.
2. **Model too large to bake, or model releases must decouple from code releases** → stop baking;
   point `INFERENCE_ARTIFACT_DIR` at a mounted volume or fetch from S3 at start. Already supported —
   one env var (`forecasting/artifacts.py:9`, `forecasting/model.py:17`).
3. **Need experiment tracking, a model registry, or staged model promotion** → SageMaker Model
   Registry, or managed MLflow on SageMaker, replacing the S3 + manifest scheme at
   `docs/planning.md:45`. Name these explicitly as *considered and declined for now*, with the
   reason — a reviewer reads "I know this exists and here's why I didn't reach for it" as judgment;
   silence reads as a gap.
4. **Per-request rather than daily predictions** → the batch job is the wrong shape entirely;
   that is a served model behind API Gateway, and the `forecasting` library is already the reusable
   part.

Keep each branch to a trigger, a move, and the cost of the move. This is a decision record, not a
roadmap.

## Refactor
One diagram, not four. If a second is tempting, the first is doing too much. Cross-link rather than
restate: `what_if.md` points at `architecture.md` for the baseline, `architecture.md` points at
`what_if.md` for the exits.

## Verify
Render the Mermaid block (GitHub preview or `mermaid-cli`) — it must draw. Every repo path cited
must resolve, checked against the tree *after* phases 01-05 (line numbers will have shifted). Read
both files against `docs/task.md:16-24` and confirm each asked-for element is present.

## Commit
`docs: add the architecture diagram and the what-if escalation path`  <!-- committed inside the job worktree; squashed at phase merge -->
