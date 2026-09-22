# src/inference code review (2026-09-22)

`/code-review` (high effort, multi-angle) run against `src/inference`, prompted by: is it
idiomatic/clear, and what blocks refactoring toward high unit-test coverage. All findings below
were independently verified against the current file contents before being recorded. Ranked most
severe first.

## Correctness bugs

- [ ] **`gateway.py:31`** — `_get_api_token` passes `CONFIG.secret_key` (a pydantic `SecretStr`,
  see `config.py:11`) straight into `dbutils.secrets.get(key=...)` instead of
  `.get_secret_value()`. `SecretStr` isn't a `str`; its repr is literally `**********`. First real
  (`simulation_mode=false`) run either breaks py4j marshalling or looks up a secret named
  `**********` — real-mode auth is currently dead and untested (default config is simulation). TODO: fix
- [ ] **`daily_product_demand_inference.py:26`** — startup checks `artifact_dir` and
  `forecast_metadata.joblib` exist, but never checks `xgb_daily_product_demand.json`. A missing
  model file only surfaces deep inside `make_forecast → load_model`, after the network fetch and
  full feature reconstruction already ran — contradicts CLAUDE.md's "inference fails fast if
  outputs/ lacks model + metadata" and wastes a real HTTP round-trip in production mode. TODO: I want a function that will double-check all artifacts presence early.
- [ ] **`preprocess.py:22`** — `source_payload.get("records", source_payload.get("data"))` only
  falls back to `data` when `records` is *absent*, not when present but `null`. An endpoint
  responding `{"records": null, "data": [...]}` discards a perfectly valid `data` payload and
  raises the empty-list error instead. TODO: Fix
- [ ] **`preprocess.py:67`** — the 28-day history check only bounds the *overall* date span
  (`min` vs `latest - 27d`), not per-category contiguity. A category closed for several days
  mid-window, or one filtered out partway by the `isin(metadata.categories)` check, still passes
  because other categories have full history; the gaps are then silently zero-filled by
  `aggregate_per_category` (`common/preprocessing.py:35`) instead of raised — model forecasts off
  fabricated zero-history rather than failing fast as the docstring promises. TODO: Write this as a "todo" comment + add a point in todo.md. I believe this should be a part of data drift detection - some guardrails for the data distribution.
- [ ] **`common/preprocessing.py:16`** — `columns_to_expected_types` mutates the `sales` argument
  in place while also returning a value, implying a pure transform. A future unit-test suite
  reusing one fixture DataFrame across cases will see it silently altered after the first call,
  producing order-dependent failures. TODO: make it a pure transform -> copy the dataframe, never mutate.
- [ ] **`gateway.py:92`** (lower severity) — `_SimulatedGateway.fetch_source_payload` globs every
  CSV in `data_dir` with no de-dup guard. Latent today (one bundled CSV); the moment a second
  overlapping CSV is added, sales get silently double-counted. TODO: write it down as TODO - comment + in todo.md

## Testability blockers (relevant to the stated refactor goal)

- [ ] **`gateway.py:19`** — `make_gateway(config)` only reads `config.simulation_mode`;
  `_RestGateway`, `_get_api_token`, and `_request_headers` all read the module-level `CONFIG`
  singleton directly instead of the injected value. A test building a fake `Config` and calling
  `make_gateway(fake_config)` will still hit real `CONFIG` inside `_RestGateway` — needs a module
  monkeypatch instead of plain construction, and it has to land before `inference.config` is
  first imported anywhere in the test session. **This is the main blocker.** TODO: change this -> should be always injected
- [ ] **`gateway.py:26`** — "not on Databricks" is detected by catching `NameError` on an
  undefined global `dbutils`, and the `except` wraps the *entire* `dbutils.secrets.get(...)` call,
  not just the name lookup. No seam to inject a fake secrets provider without
  `monkeypatch.setattr(gateway, "dbutils", fake, raising=False)`; any unrelated typo'd name inside
  that block also raises `NameError` and gets mislabeled as the Databricks error. TODO: I want to discuss the options for this one.
- [ ] **`preprocess.py:35`** — `validate_required_columns_present` is only called from `__main__`
  (`daily_product_demand_inference.py:50`), not from inside `preprocess_data`/
  `payload_to_dataframe` themselves. A unit test calling `preprocess_data` directly — the natural
  way to test it — bypasses the guard; a frame missing e.g. `Total_Qty` crashes with a raw
  `KeyError` deep in `columns_to_expected_types` instead of the intended `ValueError`. TODO: Let's discuss this. Is this bad? I don't want the validation to run two times and maybe it's not worth to do it during testing?
- [ ] **`daily_product_demand_inference.py:22`** — all orchestration (metadata load, gateway
  creation, preprocessing chain, CSV write) lives inline under `if __name__ == "__main__":`, with
  only a throwaway single-use closure (`obtain_recent_sales`) breaking it up. Nothing is
  importable/unit-testable today beyond the full-subprocess e2e run. Extracting a
  `main(config, gateway, metadata)` function is the direct fix. TODO: do it.

## Clarity / cleanup

- [ ] **`forecaster.py:16`** — parameter `ARTIFACT_DIR` is ALL_CAPS despite being an ordinary
  function argument, inconsistent with every other param and misleading since this codebase
  genuinely has a module-level `CONFIG` constant elsewhere. Rename to lowercase. TODO: fix
- [ ] **`preprocess.py:90`** — `preprocess_data` returns `all_dates`, unpacked at
  `daily_product_demand_inference.py:51`, but never used afterward — dead output. TODO: compare with the logic still existing in the ipynb. If it does not -> see the first commit where the notebooks are actually added. If it is dead indeed - just don't return it.

## Documentation drift (informational, not a code bug)

- Per CLAUDE.md, the `.py` scripts should be `nbconvert` exports of their paired `.ipynb`
  (`# In[n]:` markers kept). `daily_product_demand_inference.py` has none and has been split into
  six modules (`gateway.py`, `features.py`, `forecaster.py`, `preprocess.py`, `result_upload.py`,
  `model_loader.py`) that don't exist in the notebook. The notebook still shows stale logic
  (inline `get_api_token()`, dict-style `artifacts[...]` access, no `SalesGateway` protocol) —
  worth knowing before relying on the notebook for context. TODO: the notebooks will be removed eventually. Fix the docs.

## Suggested order of attack

1. Fix `SecretStr` bug (one-line, real-mode auth is currently broken).
2. Fix the `CONFIG` singleton / `dbutils` seams in `gateway.py` — unblocks everything else on the
   testability list.
3. Extract `main()` out of the `__main__` block in `daily_product_demand_inference.py`.
4. Move `validate_required_columns_present` inside `preprocess_data`/`payload_to_dataframe`.
5. Add the missing model-file existence check, the `records`/`data` null fallback fix, and the
   per-category history check — each is a small, independent correctness fix.
6. Cleanup pass: `ARTIFACT_DIR` naming, drop unused `all_dates`, stop mutating `sales` in place.
