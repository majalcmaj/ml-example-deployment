<!-- plan-status: done; commit=c0e22b801a35dd7a98be157d2c66801013137eeb; date=2026-09-22 -->
# Phase 03 — env-secrets-provider

> **Status:** ✅ DONE — c0e22b801a35dd7a98be157d2c66801013137eeb (2026-09-22)

Read `docs/docker-deploy/prompt.md` first.

## Goal
Inference can authenticate to the source API outside Databricks. Today it cannot, which is the
single blocker stopping the Compose stack (phase 05) from running at all.

## Red
Add to `src/inference/inference/gateway_test.py`:
- `make_gateway(config)` with `INFERENCE_API_TOKEN` set returns a `_RestGateway` whose provider
  yields that token.
- with the variable unset/empty, `get_token()` raises a message naming `INFERENCE_API_TOKEN`.

Both fail today: `make_gateway` (`gateway.py:44`) hardwires `_DatabricksSecretsProvider`, which
raises `RuntimeError("Real API mode requires Databricks Secrets.")` whenever the Databricks
`dbutils` global is absent (`gateway.py:28-30`).

## Green
### Replace the provider — `src/inference/inference/gateway.py`
Delete `_DatabricksSecretsProvider` (`:25-34`) and add:

```python
class SecretsProvider(Protocol):
    def get_token(self) -> str: ...


class _EnvSecretsProvider:
    def get_token(self) -> str:
        token = os.environ.get("INFERENCE_API_TOKEN")
        if not token:
            raise RuntimeError(
                "INFERENCE_API_TOKEN is not set; the source API cannot be authenticated."
            )
        return token
```

**Keep the `SecretsProvider` protocol.** `docs/planning.md:82` names this interface-abstraction
pattern as a deliberate architectural principle, and it is the seam an AWS Secrets Manager backend
plugs into later (`docs/TODO.md:17`). The signature drops its `config` argument because `Config` no
longer carries secret fields.

`make_gateway` defaults to `secrets_provider or _EnvSecretsProvider()`.

### Trim `Config` — `src/inference/inference/config.py` + `config.toml`
Drop `secret_scope` and `secret_key`. This removes the planted inline secret at `config.toml:5`
("`secret_key = "secret_key" # TODO: env var!`") and the `SecretStr` misuse — the field held a
*key name*, not a secret. Remaining fields: `source_endpoint_url`, `result_endpoint_url`,
`history_days`, `artifact_dir`, `output_dir`.

### Drop the Databricks escape hatch
Remove `builtins = ["dbutils"]` from the root `pyproject.toml:30`. Delete the two tests it existed
for: `gateway_test.py:116-138`. Update `make_config` (`gateway_test.py:14-27`) and
`FakeSecretsProvider` (`:30-35`) for the trimmed `Config` and the no-arg `get_token`.

## Refactor
The token is now read from one well-known variable with no indirection — do **not** add a
`secrets_backend` discriminator field or an AWS implementation on spec. `docs/planning.md:26`
records the confirmed YAGNI stance; the protocol alone is the extension point, and phase 06 documents
AWS Secrets Manager as the named, explicitly-declined next step.

## Verify
```
uv run pytest src/inference/inference/gateway_test.py
make lint && make test-unit && make test-inference
make test-mutation
```
`make lint` is the real check here — with `builtins = ["dbutils"]` gone, any surviving reference to
the Databricks global becomes a ruff F821.

## Commit
`feat(inference): read the API token from the environment, drop dbutils`
