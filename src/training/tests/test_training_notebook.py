from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
import pytest
from testkit.asserts import (
    BOUND_RTOL,
    METRIC_RTOL,
    PREDICTION_ATOL,
    assert_columns_equal,
    assert_frame_within_tolerance,
    assert_mapping_equal,
)

pytestmark = pytest.mark.e2e

BASELINE_DIR = Path(__file__).parent / "baseline"


def test_schema_contract_unchanged(run_root: Path) -> None:
    actual = joblib.load(run_root / "outputs" / "forecast_metadata.joblib")
    expected = joblib.load(BASELINE_DIR / "forecast_metadata.joblib")
    assert_mapping_equal(actual["configuration"], expected["configuration"])
    assert_mapping_equal(actual["categories"], expected["categories"])
    assert_mapping_equal(actual["model_feature_columns"], expected["model_feature_columns"])
    assert_mapping_equal(actual["category_dummy_columns"], expected["category_dummy_columns"])

    actual_csv = pd.read_csv(run_root / "outputs" / "next_day_product_forecast.csv")
    expected_csv = pd.read_csv(BASELINE_DIR / "next_day_product_forecast.csv")
    assert_columns_equal(actual_csv, expected_csv)


def test_outlier_bounds_within_tolerance(run_root: Path) -> None:
    actual = joblib.load(run_root / "outputs" / "forecast_metadata.joblib")
    expected = joblib.load(BASELINE_DIR / "forecast_metadata.joblib")
    assert_frame_within_tolerance(
        actual["outlier_bounds"], expected["outlier_bounds"], rtol=BOUND_RTOL
    )


def test_validation_metrics_within_tolerance(run_root: Path) -> None:
    actual = joblib.load(run_root / "outputs" / "forecast_metadata.joblib")
    expected = joblib.load(BASELINE_DIR / "forecast_metadata.joblib")
    assert_frame_within_tolerance(
        pd.DataFrame([actual["validation_metrics"]]),
        pd.DataFrame([expected["validation_metrics"]]),
        rtol=METRIC_RTOL,
    )


def test_predictions_within_tolerance(run_root: Path) -> None:
    actual = pd.read_csv(run_root / "outputs" / "next_day_product_forecast.csv")
    expected = pd.read_csv(BASELINE_DIR / "next_day_product_forecast.csv")
    assert_frame_within_tolerance(
        actual[["Predicted_Qty"]], expected[["Predicted_Qty"]], atol=PREDICTION_ATOL
    )
