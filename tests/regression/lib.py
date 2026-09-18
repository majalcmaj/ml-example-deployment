"""Shared helpers for the notebook regression suite.

Runs each notebook end-to-end against the real `outputs/`/`data/` dirs (matching a
human run) and compares the artifacts it writes against a frozen `baseline/` copy.
"""

from __future__ import annotations

from pathlib import Path

import joblib
import nbformat
import pandas as pd
from nbclient import NotebookClient

PREDICTION_ATOL = 1  # rounded-quantity jitter
METRIC_RTOL = 1e-3  # MAE/RMSE/WMAPE
BOUND_RTOL = 1e-6  # IQR bounds from static data — near-exact, tolerance absorbs float summation order

BASELINE_DIR = Path(__file__).parent / "baseline"


def _run_notebook(notebook_path: Path, repo_root: Path) -> None:
    nb = nbformat.read(notebook_path, as_version=4)
    NotebookClient(nb, resources={"metadata": {"path": str(repo_root)}}).execute()


def produce_training_artifacts(repo_root: Path) -> None:
    _run_notebook(repo_root / "src" / "daily_product_demand_forecast.ipynb", repo_root)


def produce_inference_artifacts(repo_root: Path) -> None:
    _run_notebook(repo_root / "src" / "daily_product_demand_inference.ipynb", repo_root)


def load_csv(name: str, *, repo_root: Path, baseline: bool = False) -> pd.DataFrame:
    base = BASELINE_DIR if baseline else repo_root / "outputs"
    return pd.read_csv(base / name)


def load_joblib(name: str, *, repo_root: Path, baseline: bool = False) -> dict[str, object]:
    base = BASELINE_DIR if baseline else repo_root / "outputs"
    return joblib.load(base / name)


def assert_columns_equal(actual_df: pd.DataFrame, expected_df: pd.DataFrame) -> None:
    assert list(actual_df.columns) == list(expected_df.columns)


def assert_frame_within_tolerance(
    actual_df: pd.DataFrame,
    expected_df: pd.DataFrame,
    *,
    rtol: float | None = None,
    atol: float | None = None,
) -> None:
    kwargs: dict[str, float] = {}
    if rtol is not None:
        kwargs["rtol"] = rtol
    if atol is not None:
        kwargs["atol"] = atol
    pd.testing.assert_frame_equal(
        actual_df.reset_index(drop=True),
        expected_df.reset_index(drop=True),
        check_exact=False,
        **kwargs,
    )


def assert_mapping_equal(actual: object, expected: object) -> None:
    assert actual == expected
