<!-- plan-status: pending -->
# Phase 02 — inference-entrypoint-and-stub

> **Status:** ⬜ PENDING

Read `docs/docker-deploy/prompt.md` first.

## Goal
The simulated data source stops being production code and becomes a test fixture injected through
the existing `SalesGateway` protocol. The inference e2e becomes an in-process `run()` call instead
of a subprocess, without losing any mutation coverage.

## Red
Two checks, both failing today:

1. **New e2e assertion.** Add `test_uploaded_payload_matches_csv` to
   `src/inference/tests/test_inference.py`: exactly one recorded upload, whose `predictions[]`
   categories and quantities match the written CSV row-for-row, and whose `forecast_date` is the
   day after the latest input date. Impossible today — the current `_SimulatedGateway`
   (`gateway.py:138-140`) only *logs* the payload, so nothing can assert on it. `result_upload.py`
   has never been covered by the e2e.

2. **New mutation 7.** In `scripts/mutation_check.sh`, mutate `src/inference/inference/result_upload.py`
   `predicted_quantity=int(...)` → `int(...) + 1` and require `src/inference -m e2e` to go red.
   It survives today.

## Green
### Move the stub into the test tree
New `src/inference/tests/stub_gateway.py` holding `StubSalesGateway` — the body of
`_SimulatedGateway` (`gateway.py:96-140`), reading `REPO_ROOT/data/*.csv` and returning
`{"records": [...]}`. Add `self.uploads: list[dict]` so `upload_inference_results` records rather
than only logging. It satisfies the existing `SalesGateway` protocol (`gateway.py:16-18`) — no new
production seam.

### Delete `_SimulatedGateway` from `src/inference/inference/gateway.py`
`make_gateway` loses the `config.simulation_mode` branch and always returns `_RestGateway`.
(The Databricks secrets provider stays until phase 03; this phase changes *which gateway*, not
*where the token comes from*.)

### Trim `Config` — `src/inference/inference/config.py` + `config.toml`
Drop `simulation_mode` and `data_dir`; nothing reads them once `_SimulatedGateway` is gone.
Knock-on: `src/inference/inference/config_test.py:5` asserts `CONFIG.simulation_mode is True` —
replace with `history_days == 60`. **Keep `test_artifact_dir_points_at_outputs`
(`config_test.py:9-12`)** — mutation 6 (`mutation_check.sh:85`) targets it.

### Extract `run()` — `src/inference/inference/daily_product_demand_inference.py`
**Load-bearing for mutation 5.** `verify_artifacts_present` currently lives in the `__main__` block
(`:59`), not in `main()`. An e2e that calls `main()` directly lets mutation 5
(`mutation_check.sh:81`, metadata renamed away) silently survive. Move everything `__main__` does
above `main()` into:

```python
def run(config: Config, sales_gateway: SalesGateway) -> None:
    log = logger.get_logger(__name__)
    log.info("Running inference with config: %s", config.model_dump_json(indent=2))
    verify_artifacts_present(config.artifact_dir)
    metadata = ForecastMetadata.load(config.artifact_dir / METADATA_FILENAME)
    log.info(
        "Loaded model contract with %s features and %s categories.",
        len(metadata.model_feature_columns),
        len(metadata.categories),
    )
    main(config, sales_gateway, metadata)


if __name__ == "__main__":
    run(CONFIG, make_gateway(CONFIG))
```

**Do not move the `init_context()` call at `:15`.** It sits deliberately *between* imports:
`create_http_session()` snapshots `CORRELATION_ID.get()` at construction (`http_session.py:23`), so
hoisting the `gateway` import above it degrades `X-Correlation-ID` to `"-"`. Leave the ordering and
its comment intact.

### Rewrite `src/inference/tests/conftest.py`
Drop `testkit.runner.run_script`, the `data/` copytree (`conftest.py:16`) and all three
`monkeypatch.setenv` calls (`:28-35`).

**The env-override route is unavailable in-process**: `CONFIG` is an import-time singleton
(`inference/config.py:20`) and `inference/config_test.py:1` imports it at collection time, so by the
time a session fixture runs it is already frozen with repo defaults. The fixture must construct a
`Config(...)` and pass it to `run()`:

```python
@pytest.fixture(scope="session")
def run_root(tmp_path_factory) -> tuple[Path, StubSalesGateway]:
    root = tmp_path_factory.mktemp("inference-e2e")
    outputs = root / "outputs"
    outputs.mkdir()
    shutil.copy(BASELINE_DIR / MODEL_FILENAME, outputs / MODEL_FILENAME)
    shutil.copy(BASELINE_DIR / METADATA_FILENAME, outputs / METADATA_FILENAME)

    config = Config(
        source_endpoint_url="https://example.invalid/api/recent-sales",
        result_endpoint_url="https://example.invalid/api/demand-forecast",
        history_days=60,
        artifact_dir=outputs,
        output_dir=outputs,
    )
    gateway = StubSalesGateway(REPO_ROOT / "data", history_days=60)
    run(config, gateway)
    return root, gateway
```

`CLAUDE.md:45`'s warning still holds: the env-override mechanism stays intact for `training`'s e2e
and for every container deployment — it simply stops being *inference's* e2e lever.

### Baseline
`baseline/inference_next_day_forecast.csv` must **not** change. `StubSalesGateway` reproduces
`_SimulatedGateway`'s payload byte-for-byte, so `test_predictions_match_baseline` stays green
untouched. If it drifts, the stub is wrong — fix the stub, never the baseline.

## Refactor
`testkit/runner.py:11` is now used only by `src/training/tests/` — leave it, do not generalise it
for containers (phase 05 uses a shell script instead). Drop the `data_dir` plumbing that only
existed for simulation, and delete the now-dead `docs/TODO.md:43` note about `_SimulatedGateway`'s
missing de-dup guard along with the code it described.

## Verify
```
make test-inference          # both e2e tests green, no subprocess
make test-training           # unchanged, still subprocess
make lint && make test-unit
make test-mutation           # mutations 1-7 all caught
```
Mutations **4, 5 and 7** are the ones that matter here: 4 proves the prediction diff still bites,
5 proves `run()` kept the fail-fast, 7 proves the new upload assertion bites. `make test-mutation`
needs a clean tree for the files it mutates.

## Commit
`refactor(inference): inject the sales stub from tests, extract run()`
