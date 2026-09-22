<!-- plan-status: done; commit=ac5542c7c52be58c260eb07a42e4f4c58bfecad5; date=2026-09-22 -->
# phase06 · Job 03 — claude-md-and-readme

> **Status:** ✅ DONE — ac5542c7c52be58c260eb07a42e4f4c58bfecad5 (2026-09-22)

Read `docs/docker-deploy/prompt.md` and the parent phase file first. This job runs in its own git
worktree; touch only the files in its slice (jobs are file-disjoint).

## Goal
The contributor-facing docs describe the code as it now is: no simulation mode, no Databricks
secrets, a container story, and an inference e2e that no longer shells out.

**Owns:** `CLAUDE.md`, `README.md`.

## Red
`CLAUDE.md:18` still describes inference as "simulation mode by default"; `:47-53` describes the
inference e2e as a `run_script` subprocess with env-var redirection; `:78` documents
`inference/config.toml`'s inline `secret_key`. `README.md:12` says inference "loads the model,
serves next-day forecasts" with no mention of images. None of that survives phases 02-05.

## Green
### `CLAUDE.md`
- **"What this is" (`:18`)** — inference always uses the real HTTP path; the stub lives in
  `src/inference/tests/` and is injected through the `SalesGateway` protocol. Drop "simulation mode
  by default".
- **"Commands" (`:24-36`)** — add the new make targets: `images`, `image-inference`,
  `image-training`, `image-mock-api`, `compose-up`, `compose-down`, `test-compose`. Keep the
  reminder at `:29-31` that `## ` descriptions live on the target lines.
- **"Config and paths" (`:40-46`)** — document `<PREFIX>_CONFIG_FILE`. Keep the existing warning
  about the env-override mechanism, and add the container-specific consequence: `find_project_root`
  walks up for `uv.lock`, silently falls back to `cwd`, and there is no `uv.lock` in a lean image —
  so container configs use **absolute** paths.
- **"Tests" (`:47-66`)** — inference's e2e is now in-process (`run()` + injected
  `StubSalesGateway`, config constructed in the fixture, *not* env vars, because `CONFIG` is an
  import-time singleton); training's is still a subprocess via `testkit.runner`. Document
  `make test-compose` and mutations 7 and 8. Keep the rule at `:57-59` — a new e2e assertion needs
  a mutation that proves it bites, and a mutation is never weakened to make it pass.
- **"Known drift / gotchas" (`:68-81`)** — drop the `simulation_mode` and `secret_key` lines; add
  the new ones: `libgomp1` is required for xgboost in slim images; the training script calls
  `plt.show()` twice and needs `MPLBACKEND=Agg`; the inference image bakes a model at `/opt/model`
  that `INFERENCE_ARTIFACT_DIR` overrides.
- Add a short **layout** note for the new `docker/` and `deploy/` trees.

### `README.md`
- Extend the layout block (`:8-15`) with `docker/`, `deploy/`, and the Compose entry point.
- Replace/extend "Deploying a subset" (`:25-28`) with how to build each image and run the stack:
  `make images`, `make compose-up`, `make test-compose`.
- One short paragraph on the deployment shape, pointing at `docs/architecture.md` and
  `docs/what_if.md` rather than restating them.

## Refactor
`CLAUDE.md` is instructions for an agent, not a changelog — replace stale statements outright, do
not append "(was X)" notes. Cut any line that phases 01-05 made irrelevant rather than rewording it,
and keep the file scannable.

## Verify
```
grep -n "simulation_mode\|secret_key\|secret_scope\|dbutils" CLAUDE.md README.md
make          # the help target lists every new target with a description
```
First command returns nothing. Then walk `CLAUDE.md`'s Commands section top to bottom and run each
command as written — every one must work on a fresh checkout.

## Commit
`docs: update CLAUDE.md and README for the container workflow`  <!-- committed inside the job worktree; squashed at phase merge -->
