from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from testkit.asserts import (
    PREDICTION_ATOL,
    assert_columns_equal,
    assert_frame_within_tolerance,
)

pytestmark = pytest.mark.e2e

BASELINE_DIR = Path(__file__).parent / "baseline"


def test_predictions_match_baseline(run_root: Path) -> None:
    actual = pd.read_csv(run_root / "outputs" / "inference_next_day_forecast.csv")
    expected = pd.read_csv(BASELINE_DIR / "inference_next_day_forecast.csv")

    assert_columns_equal(actual, expected)
    assert_frame_within_tolerance(
        actual.loc[:, ["Predicted_Qty"]],
        expected.loc[:, ["Predicted_Qty"]],
        atol=PREDICTION_ATOL,
    )
