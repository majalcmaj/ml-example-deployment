<!-- plan-status: pending -->
# Phase 04 — tooling-docs

> **Status:** ⬜ PENDING

Read `docs/package-split/prompt.md` first.

## Goal
Point the mutation harness and every doc at the new layout, and close the two backlog items this
restructure answers. After this phase nothing in the repo refers to a `common` package.

## Red
```
grep -n 'src/common/common/features.py' scripts/mutation_check.sh   # stale path, mutations 1 & 2 would no-op
grep -rn '\bcommon\b' CLAUDE.md docs/*.md src/testkit/README.md     # stale prose
```

Prove the staleness bites rather than assuming it: with the old path in place,
`scripts/mutation_check.sh`'s `sed -i` writes to a file that no longer exists.

## Green
**`scripts/mutation_check.sh:19`** — `FEATURES="src/common/common/features.py"` →
`src/forecasting/forecasting/features.py`. Both feature mutations must still bite: lag
`[1, 7, 14, 28] → [1, 7, 14, 29]` (mutation 1) and `.isin([5, 6]) → .isin([4, 6])` (mutation 2).
The table comment at the top of the script names `features.py` and `common/features_test.py` —
update both. Mutation 2's target suite is now `src/forecasting/forecasting/features_test.py`.

**`CLAUDE.md`** — rewrite "What this is" (member list and dependency direction) and the file paths
in "Config and paths" / "Tests". The invariant line "`training` and `inference` never import each
other — the only link is the artifact files" stays true and is now enforced by a real library
boundary rather than convention. Record the libs/apps shape: `infra` + `forecasting` are
libraries, `training` + `inference` are deployable apps, `testkit` is dev-only.

**`docs/TODO.md`**
- `:11` (P0, shared feature extraction): retarget `common` → `forecasting`; note the *placement*
  half is done and only collapsing the three `get_dummies`+reindex sites, the two future-row
  blocks, the two clip/round blocks and the two panel builds remains. Update the quoted paths
  (`inference/features.py` → `forecasting/features.py`).
- `:50` (P2, "Does data/model need its own top-level module?"): answer and close it —
  `forecasting` is that module.
- `:68` (P1 design-doc note, "shared `common` module sufficient at this scale" as the reason no
  feature store is needed): update the package name, keep the reasoning.

**`docs/planning.md`** — `:34-36` ("UV project with `training`, `inference`, `common`… still
deciding whether data/model concerns need their own top-level module") and `:27` (feature store
skipped because `common` covers it). Update names and record why the libs/apps split was chosen
over a fatter `common`.

**`src/testkit/README.md`** — check the artifact map and mutation-table reference still describe
reality after the phase-02 moves.

## Refactor
`grep -rIn '\bcommon\b' --exclude-dir=.git --exclude='*.ipynb' .` returns only intentional English
prose (e.g. "common case"), never a package reference. The `.ipynb` files are excluded on purpose:
CLAUDE.md forbids editing them and they are slated for deletion (`docs/TODO.md:78-81`).

## Verify
- `uv run ruff check`, `make type-check`, `make test` — green, same pass count.
- Commit first, then `make test-mutation`. It refuses to run with uncommitted changes to the files
  it mutates, so it cannot be verified before the commit. **All 6 mutations must be caught**, with
  1 and 2 exercising the new `forecasting` path. A survivor here means the retarget was wrong.
- Baselines untouched: `git status --porcelain src/*/tests/baseline` is empty.
- Re-read `CLAUDE.md` end to end and confirm every path it names exists.

## Commit
`docs(workspace): retarget tooling and docs at the infra/forecasting split`

Trailer: `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`
