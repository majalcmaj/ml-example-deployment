<!-- plan-status: done; commit=ac5542c7c52be58c260eb07a42e4f4c58bfecad5; date=2026-09-22 -->
# phase06 · Job 02 — planning-and-todo

> **Status:** ✅ DONE — ac5542c7c52be58c260eb07a42e4f4c58bfecad5 (2026-09-22)

Read `docs/docker-deploy/prompt.md` and the parent phase file first. This job runs in its own git
worktree; touch only the files in its slice (jobs are file-disjoint).

## Goal
The rationale doc and the backlog stop contradicting the code. The deployment decision is recorded
as an explicit decision, not inferred from a Dockerfile.

**Owns:** `docs/planning.md`, `docs/TODO.md`.

## Red
`docs/planning.md:49` names Databricks the **primary recommendation**; `:53` says baking the model
into a Docker image "doesn't transfer to Databricks" — and phases 04-05 built exactly that.
`docs/planning.md:14-16` still frames local/offline inference mode as an open question that
phase 02 closed. `docs/TODO.md:14` (Compose e2e) and `:47` (keep-or-drop simulation) describe work
now done.

## Green
### `docs/planning.md`
Rewrite **"Deployment — general" (`:47-50`)** and **"Model loading — architectural fork"
(`:52-56`)**:
- Docker-first, with targets split by workload: training → SageMaker Training Job / Fargate task;
  daily inference batch → Lambda container image. Give the reason Lambda is wrong for training
  (15-min cap, no GPU, 10 GB limits) — that split *is* the tradeoff reasoning `:48` says the
  assignment is asking for.
- Demote Databricks from "primary recommendation" to the named alternative, and say why the
  recommendation moved.
- Add a paragraph naming SageMaker Model Registry and managed MLflow on SageMaker as the managed
  replacement for the S3 + manifest scheme at `:45`, with an explicit reason for not adopting them.
- State the platform-neutral image decision outright: `artifact_dir` is a config field
  (`forecasting/artifacts.py:9`, `forecasting/model.py:17`), so baked-at-`/opt/model` and
  mounted-at-`/opt/ml/model` differ by one env var and zero code. The image picks no platform.

Update **"Local dev / environment parity" (`:13-16`)**: the open question at `:16` is resolved —
simulation mode was dropped, the Compose stubs are the local path, and the real `_RestGateway` now
runs locally. Update **"Config & secrets" (`:8-11`)**: the planted TOML secret is gone; the token
comes from `INFERENCE_API_TOKEN` through the retained `SecretsProvider` seam; a vault
implementation is still open.

Add to **"Still open" (`:95-98`)**: image reproducibility ≠ model reproducibility — seed pinning
(`docs/TODO.md:52`) is still open, so two builds of the same commit produce different models.

### `docs/TODO.md`
- Tick `:14` (Compose e2e — done in phase 05).
- Partially tick `:17` (env backend done, `SecretsProvider` seam retained, AWS/vault impl still
  open).
- Resolve and remove the open question at `:47` — folded into Compose stubs.
- Remove `:43` — `_SimulatedGateway` no longer exists.
- Tick `:54` (dependency/environment pinning — digest-pinned bases + `--frozen`).
- Tick `:68` (rollback — redeploy the previous image tag).
- Tick `:61` (model-loading strategy write-up — job 01).
- Note against `:23-38` that `make test-compose` now covers the train→infer path it asks for, and
  say whether that closes the item or only narrows it.
- Add new items: strip matplotlib from the training script (phase 04 job 02 used `MPLBACKEND=Agg`
  as the zero-code fix); POST retry (`:41`) is now testable against the mock.

## Refactor
Delete resolved speculation rather than annotating it — `docs/planning.md:16` and `docs/TODO.md:43`
and `:47` describe code and questions that no longer exist. Keep `planning.md`'s existing
note-fragment voice; do not restructure the document.

## Verify
```
grep -rn "simulation_mode\|dbutils\|secret_scope\|_SimulatedGateway" docs/
```
No hits outside a deliberate historical note. Spot-check every `file:line` citation added or kept —
phases 01-05 moved line numbers in `gateway.py`, `config.py` and the inference entrypoint.

## Commit
`docs: retarget planning and backlog at the container deployment`  <!-- committed inside the job worktree; squashed at phase merge -->
