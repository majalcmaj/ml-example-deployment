<!-- plan-status: done; commit=8adb6b7262e0e517e5a4b13c822a4ed430d0aa77; date=2026-09-22 -->
# phase04 · Job 02 — training-image

> **Status:** ✅ DONE — 8adb6b7262e0e517e5a4b13c822a4ed430d0aa77 (2026-09-22)

Read `docs/docker-deploy/prompt.md` and the parent phase file first. This job runs in its own git
worktree; touch only the files in its slice (jobs are file-disjoint).

## Goal
A minimal training image with two cache layers — deps → code. No model layer: the model is this
job's *output*, not its input.

**Owns:** `docker/training.Dockerfile`, `deploy/config/training.toml`.
Do **not** create or edit `.dockerignore` — job 01 owns it.

## Red
```
docker build -f docker/training.Dockerfile -t fc-training .
docker run --rm -v "$PWD/data:/var/forecast/data:ro" -v /tmp/out:/var/forecast/outputs fc-training
```
Fails — no such file. Once it builds, `/tmp/out` must contain
`xgb_daily_product_demand.json`, `forecast_metadata.joblib` and `next_day_product_forecast.csv`,
and the run must exit 0 with no matplotlib backend warning on stderr.

## Green
Same two-stage builder as job 01, with `--package training`, and:
- `COPY src/infra src/forecasting src/training` for the code layer (no `src/inference`).
- `libgomp1` in the runtime stage — training pulls both xgboost and scikit-learn.
- **`ENV MPLBACKEND=Agg`.** `src/training/training/daily_product_demand_forecast.py` imports
  `matplotlib.pyplot` at `:12` and calls `plt.show()` at `:197` and `:330`. Under a headless
  container the default backend selection warns or stalls; `Agg` makes `show()` a clean no-op.
  This is the zero-code-change fix — stripping the plotting blocks entirely is filed as a
  follow-up in phase 06, not done here.
- `WORKDIR /var/forecast`, `USER app`,
  `ENTRYPOINT ["python", "-m", "training.daily_product_demand_forecast"]`.
  The script is a flat 414-line module with no `main()` and no `__main__` guard; `python -m` runs
  it correctly as-is. Leave that structure alone — refactoring it is out of scope.

`deploy/config/training.toml` — platform-neutral absolute paths, no SageMaker conventions:
```toml
data_dir   = "/var/forecast/data"
output_dir = "/var/forecast/outputs"
```
Set `ENV TRAINING_CONFIG_FILE=/etc/forecast/training.toml` and copy the file there, matching job
01's shape. Phase 06 documents how each platform wires these paths (SageMaker would point them at
`/opt/ml/input/data/training` and `/opt/ml/model` via env, with no image change).

## Refactor
No model, no data, no baseline in the image — data arrives by mount (Compose), S3 sync (Fargate),
or an input channel (SageMaker). Keep the image a pure compute step whose only contract is
"read `TRAINING_DATA_DIR`, write `TRAINING_OUTPUT_DIR`". Do not add an S3 client on spec.

## Verify
```
docker build -f docker/training.Dockerfile -t fc-training .
mkdir -p /tmp/fc-out && docker run --rm \
  -v "$PWD/data:/var/forecast/data:ro" -v /tmp/fc-out:/var/forecast/outputs fc-training
ls -la /tmp/fc-out
docker image inspect --format '{{.Size}}' fc-training
```
All three artifacts present, exit 0, no matplotlib warning. Then `touch
src/training/training/config.py`, rebuild, confirm the dependency layer is `CACHED`.

## Commit
`feat(docker): add the training image`  <!-- committed inside the job worktree; squashed at phase merge -->
