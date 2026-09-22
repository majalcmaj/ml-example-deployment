<!-- plan-status: pending -->
# Phase 06 — docs

> **Status:** ⬜ PENDING

Read `docs/docker-deploy/prompt.md` first.

## Goal
The rationale docs match what was built, the deployment decision is written down explicitly, and
the two remaining submission deliverables — an architecture diagram and the "what if Lambda is too
weak" escalation path — exist.

## Red
`docs/planning.md:49` still names **Databricks the primary recommendation**, while `:53` says
"Baking model into Docker image doesn't transfer to Databricks" — the repo now contains exactly
that. `docs/TODO.md:59` (architecture diagram, P0, required by `docs/task.md:24`) and
`docs/TODO.md:61` (model-loading strategy write-up, P0) are unticked, and no `what_if.md` exists.
Grep for `simulation_mode` across `CLAUDE.md` and `README.md`: it is still documented as current
behaviour after phase 02 removed it.

## Green
Three file-disjoint jobs:

| job | owns |
|---|---|
| 01 architecture-and-what-if | `docs/architecture.md` (new), `docs/what_if.md` (new) |
| 02 planning-and-todo | `docs/planning.md`, `docs/TODO.md` |
| 03 claude-md-and-readme | `CLAUDE.md`, `README.md` |

### The decision to record, consistently across all three jobs
Targets split **by workload**, not by platform:
- **Training** → SageMaker Training Job or ECS/Fargate task. *Not* Lambda: 15-minute execution cap,
  no GPU, 10 GB image and `/tmp` limits. Fine on 20k rows today; does not generalise.
- **Daily inference batch** → Lambda container image. Seconds of compute, 2.5 MB model, cold start
  irrelevant at daily cadence; the baked-in model avoids a startup fetch (`docs/planning.md:54`).

The images stay platform-neutral because `artifact_dir` is already a config field consumed by
`forecasting/artifacts.py:9` and `forecasting/model.py:17` — "baked at `/opt/model`" and "mounted at
`/opt/ml/model`" differ by one env var and zero code. Say this explicitly rather than leaving it
implied by the Dockerfile.

## Refactor
Delete rather than annotate: `docs/planning.md:16` and `docs/TODO.md:47` pose the open question
"local/offline inference mode vs folding entirely into Compose stubs — keep or drop?", which
phase 02 answered by dropping it. Resolve the question and remove the speculation, do not leave a
note next to it. Same for `docs/TODO.md:43` (the `_SimulatedGateway` de-dup guard) — the code it
describes no longer exists.

## Verify
```
grep -rn "simulation_mode\|dbutils\|secret_scope" CLAUDE.md README.md docs/
```
No hits outside a deliberate historical note. Every file path and line reference cited in the
updated docs must still resolve — re-check them against the tree after phases 01-05 landed, since
line numbers will have moved.

Render `docs/architecture.md` (GitHub or `mermaid-cli`) and confirm the diagram draws.

## Commit
`docs: record the container deployment decision, add architecture and what-if`
