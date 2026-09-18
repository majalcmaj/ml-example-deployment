from pathlib import Path

import pandas as pd
import pytest

from tests.regression import lib

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def _training_run() -> None:
    lib.produce_training_artifacts(REPO_ROOT)


def test_schema_contract_unchanged(_training_run: None) -> None:
    actual = lib.load_joblib("forecast_metadata.joblib", repo_root=REPO_ROOT)
    expected = lib.load_joblib("forecast_metadata.joblib", repo_root=REPO_ROOT, baseline=True)
    lib.assert_mapping_equal(actual["configuration"], expected["configuration"])
    lib.assert_mapping_equal(actual["categories"], expected["categories"])
    lib.assert_mapping_equal(actual["model_feature_columns"], expected["model_feature_columns"])
    lib.assert_mapping_equal(
        actual["category_dummy_columns"], expected["category_dummy_columns"]
    )

    actual_csv = lib.load_csv("next_day_product_forecast.csv", repo_root=REPO_ROOT)
    expected_csv = lib.load_csv("next_day_product_forecast.csv", repo_root=REPO_ROOT, baseline=True)
    lib.assert_columns_equal(actual_csv, expected_csv)


def test_outlier_bounds_within_tolerance(_training_run: None) -> None:
    actual = lib.load_joblib("forecast_metadata.joblib", repo_root=REPO_ROOT)
    expected = lib.load_joblib("forecast_metadata.joblib", repo_root=REPO_ROOT, baseline=True)
    lib.assert_frame_within_tolerance(
        actual["outlier_bounds"], expected["outlier_bounds"], rtol=lib.BOUND_RTOL
    )


def test_validation_metrics_within_tolerance(_training_run: None) -> None:
    actual = lib.load_joblib("forecast_metadata.joblib", repo_root=REPO_ROOT)
    expected = lib.load_joblib("forecast_metadata.joblib", repo_root=REPO_ROOT, baseline=True)
    lib.assert_frame_within_tolerance(
        pd.DataFrame([actual["validation_metrics"]]),
        pd.DataFrame([expected["validation_metrics"]]),
        rtol=lib.METRIC_RTOL,
    )


def test_predictions_within_tolerance(_training_run: None) -> None:
    actual = lib.load_csv("next_day_product_forecast.csv", repo_root=REPO_ROOT)
    expected = lib.load_csv("next_day_product_forecast.csv", repo_root=REPO_ROOT, baseline=True)
    lib.assert_frame_within_tolerance(
        actual[["Predicted_Qty"]], expected[["Predicted_Qty"]], atol=lib.PREDICTION_ATOL
    )
