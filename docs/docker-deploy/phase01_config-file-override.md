<!-- plan-status: pending -->
# Phase 01 — config-file-override

> **Status:** ⬜ PENDING

Read `docs/docker-deploy/prompt.md` first.

## Goal
`load_config` accepts an alternate TOML path from `<PREFIX>_CONFIG_FILE`, so the packaged
`config.toml` (which ships *inside the wheel*) can be replaced by a Compose bind mount, a k8s
ConfigMap, an ECS EFS volume, or a SageMaker S3 input channel — one mechanism, every platform.

## Red
Add to `src/infra/infra/config_test.py`:
- `INFERENCE_CONFIG_FILE` pointing at a tmp TOML → `load_config` reads that file, not the packaged
  one.
- unset → packaged path still used (guards against regressing the default).
- set but missing on disk → raises, with the offending path in the message.

Run `uv run pytest src/infra` — the first and third fail today; `load_config`
(`src/infra/infra/config.py:16`) uses its `path` argument unconditionally.

## Green
Prepend the override to `load_config`, before the file is opened:

```python
override = os.environ.get(f"{env_prefix}_CONFIG_FILE")
if override is not None:
    path = Path(override)
```

Constraints:
- **Keep the per-field `<PREFIX>_<FIELD>` loop** (`config.py:20-23`) exactly as-is. That is the
  layer Lambda actually uses — Lambda cannot bind-mount files (EFS-via-VPC aside).
- **Do not touch `find_project_root`** (`config.py:8-13`). Its silent `cwd` fallback is a real
  container hazard, but the fix is absolute paths in the container config files (phase 04), not
  loosening a function whose behaviour is pinned by `config_test.py:51-60`.
- No collision risk: neither `Config` declares a `config_file` field, so the new env var cannot be
  swallowed by the field loop.

## Refactor
Fold the missing-file case into one clear `FileNotFoundError` naming both the path and the env var
that supplied it — an operator mis-mounting a ConfigMap should not have to read a traceback to
learn which variable pointed where. Keep `load_config` a single linear function; no helper class,
no `Settings` subclass (`docs/planning.md:26` — confirmed YAGNI).

## Verify
```
uv run pytest src/infra
make lint
make test-unit
```
All green, including the existing `test_find_project_root_*` contract tests.

## Commit
`feat(infra): allow config.toml path override via <PREFIX>_CONFIG_FILE`
