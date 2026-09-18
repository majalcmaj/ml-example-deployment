from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.regression import lib

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.usefixtures("training_run", "inference_run")


@pytest.fixture(scope="session")
def inference_run(training_run: None, repo_root: Path) -> None:  # noqa: ARG001 (fixture ordering)
    lib.produce_inference_artifacts(repo_root)


def test_schema_contract_unchanged(repo_root: Path) -> None:
    actual = lib.load_csv("inference_next_day_forecast.csv", repo_root=repo_root)
    expected = lib.load_csv(
        "inference_next_day_forecast.csv", repo_root=repo_root, baseline=True
    )
    lib.assert_columns_equal(actual, expected)


def test_predictions_within_tolerance(repo_root: Path) -> None:
    actual = lib.load_csv("inference_next_day_forecast.csv", repo_root=repo_root)
    expected = lib.load_csv(
        "inference_next_day_forecast.csv", repo_root=repo_root, baseline=True
    )
    lib.assert_frame_within_tolerance(
        actual[["Predicted_Qty"]], expected[["Predicted_Qty"]], atol=lib.PREDICTION_ATOL
    )
