"""Shared helpers for the notebook regression suite.

Runs each notebook end-to-end against a pytest-managed tmp mirror of `outputs/`/`data/`
(matching a human run) and compares the artifacts it writes against a frozen `baseline/` copy.

Thin shim over `testkit` — dies once the legacy suite is removed.
"""

from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from testkit.asserts import (  # noqa: F401
    BOUND_RTOL,
    METRIC_RTOL,
    PREDICTION_ATOL,
    assert_columns_equal,
    assert_frame_within_tolerance,
    assert_mapping_equal,
)
from testkit.notebooks import run_notebook

BASELINE_DIR = Path(__file__).parent / "baseline"


def produce_training_artifacts(repo_root: Path, outputs_root: Path) -> None:
    run_notebook(
        repo_root / "src" / "training" / "training" / "daily_product_demand_forecast.ipynb",
        outputs_root,
    )


def produce_inference_artifacts(repo_root: Path, outputs_root: Path) -> None:
    # cwd is 2 levels deep (not 3, matching the real src/inference/inference/ path) so the
    # notebook's own `cwd.parent.parent / "outputs"` autodetect (untouched until phase04) still
    # reaches outputs_root/outputs. nbclient's cwd is independent of the .ipynb file's own path.
    run_notebook(
        repo_root / "src" / "inference" / "inference" / "daily_product_demand_inference.ipynb",
        outputs_root / "src" / "inference",
    )


def load_csv(name: str, *, outputs_root: Path, baseline: bool = False) -> pd.DataFrame:
    base = BASELINE_DIR if baseline else outputs_root / "outputs"
    return pd.read_csv(base / name)


def load_joblib(
    name: str, *, outputs_root: Path, baseline: bool = False
) -> dict[str, object]:
    base = BASELINE_DIR if baseline else outputs_root / "outputs"
    return joblib.load(base / name)
