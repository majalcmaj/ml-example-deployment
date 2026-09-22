<!-- plan-status: pending -->
# phase04 · Job 03 — mock-api-image

> **Status:** ⬜ PENDING

Read `docs/docker-deploy/prompt.md` and the parent phase file first. This job runs in its own git
worktree; touch only the files in its slice (jobs are file-disjoint).

## Goal
A zero-dependency stub of the remote sales API, for local development only: serves prepared sales
history on GET, accepts forecasts on POST.

**Owns:** `docker/mock-api/server.py`, `docker/mock-api.Dockerfile`.
Do **not** create or edit `.dockerignore` — job 01 owns it.

## Red
```
docker build -f docker/mock-api.Dockerfile -t fc-mock-api .
docker run --rm -d -p 8080:8080 -e MOCK_API_TOKEN=local-dev-token fc-mock-api
curl -s localhost:8080/healthz
curl -s -H 'Authorization: Bearer local-dev-token' \
  'localhost:8080/api/recent-sales?history_days=60' | head -c 200
curl -s -o /dev/null -w '%{http_code}\n' 'localhost:8080/api/recent-sales?history_days=60'
```
Fails — no such file. Once built: `/healthz` → 200, the authenticated GET returns
`{"records":[…]}` spanning 60 days, and the unauthenticated GET returns **401**.

## Green
`docker/mock-api/server.py` — stdlib `ThreadingHTTPServer` + `BaseHTTPRequestHandler` + `csv`,
roughly 80 lines, **no third-party imports**. Deliberately *not* a uv workspace member: it must
stay out of `uv.lock` and out of both app images.

Contract, derived from `gateway.py:63-93` and `preprocess.py:16-34`:

- **`GET /api/recent-sales?history_days=N`** — require `Authorization: Bearer $MOCK_API_TOKEN`,
  else 401. Slice the last `N` days from the bundled CSV by max `Date`, respond
  `{"records": [{"Date": "2024-01-01", "Menu": "Green Tea", "Total_Qty": 8}, …]}`.
  Those three columns are `forecasting/consts.py:1-4`'s `REQUIRED_COLUMNS`; the CSV's other
  columns (`Day`, `Promotion`, `Month`, `Sales_Status`, `Year`) are dropped at
  `preprocess.py:46-53` and may be included or not. Must return ≥28 days or
  `preprocess.py:74-77` rejects the response.
- **`POST /api/demand-forecast`** — same auth check; parse the `InferenceResultPayload` shape
  (`result_upload.py:18-26`: `forecast_date`, `generated_at_utc`, `predictions[]`); log a one-line
  summary; respond `200 {"status": "accepted", "received": N}`. Any 2xx body is accepted by
  `gateway.py:81-90`, but returning JSON exercises the `.json()` path rather than the text
  fallback.
- **`GET /healthz`** → 200. Used by the Compose healthcheck in phase 05.

Enforcing the bearer token is the point, not decoration: it is what makes the Compose run exercise
`_EnvSecretsProvider` and the `Authorization` header rather than only the happy path.

```dockerfile
FROM python:3.14-slim-bookworm
RUN useradd --create-home --uid 10001 app
COPY docker/mock-api/server.py /app/server.py
COPY data/coffeeshop_daily_sales_report.csv /srv/data/sales.csv
USER app
EXPOSE 8080
ENTRYPOINT ["python", "/app/server.py"]
```
No `pip install`, no `uv`, no venv.

### Why bespoke here
WireMock/mockserver would mean no code to maintain, but they cannot slice the response by
`history_days`, so the fixture would be a frozen JSON blob that silently drifts from
`data/coffeeshop_daily_sales_report.csv`. FastAPI would add a dependency tree and a workspace member
for two endpoints. The stdlib server keeps the mock honest (same CSV as the baseline) at ~80 lines
and zero dependencies.

## Refactor
Keep it one file with no abstraction layer — it is a test double, and `src/testkit/README.md`'s
rationale about deliberately shallow test infrastructure applies. Read the CSV once at startup
rather than per request; strip anything not needed by the three routes.

## Verify
The Red commands above, plus:
```
curl -s -X POST -H 'Authorization: Bearer local-dev-token' \
  -H 'Content-Type: application/json' \
  -d '{"forecast_date":"2025-01-01","generated_at_utc":"2025-01-01T00:00:00Z","predictions":[{"category":"Green Tea","predicted_quantity":7}]}' \
  localhost:8080/api/demand-forecast
python3 -c "import json,urllib.request;r=urllib.request.Request('http://localhost:8080/api/recent-sales?history_days=60',headers={'Authorization':'Bearer local-dev-token'});d=json.load(urllib.request.urlopen(r));print(len({x['Date'] for x in d['records']}))"
```
POST → `{"status":"accepted","received":1}`; the last command prints `60`.

## Commit
`feat(docker): add a zero-dependency mock sales API image`  <!-- committed inside the job worktree; squashed at phase merge -->
