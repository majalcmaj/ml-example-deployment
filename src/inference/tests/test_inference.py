from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import pytest
from forecasting.consts import PREDICTED_QTY_COLUMN
from testkit.asserts import (
    PREDICTION_ATOL,
    assert_columns_equal,
    assert_frame_within_tolerance,
)

if TYPE_CHECKING:
    from stub_gateway import StubSalesGateway

pytestmark = pytest.mark.e2e

BASELINE_DIR = Path(__file__).parent / "baseline"


def test_predictions_match_baseline(run_root: tuple[Path, StubSalesGateway]) -> None:
    root, _gateway = run_root
    actual = pd.read_csv(root / "outputs" / "inference_next_day_forecast.csv")
    expected = pd.read_csv(BASELINE_DIR / "inference_next_day_forecast.csv")

    assert_columns_equal(actual, expected)
    assert_frame_within_tolerance(
        actual.loc[:, [PREDICTED_QTY_COLUMN]],
        expected.loc[:, [PREDICTED_QTY_COLUMN]],
        atol=PREDICTION_ATOL,
    )


def test_uploaded_payload_matches_csv(run_root: tuple[Path, StubSalesGateway]) -> None:
    root, gateway = run_root
    csv_forecast = pd.read_csv(root / "outputs" / "inference_next_day_forecast.csv")

    assert len(gateway.uploads) == 1
    payload = gateway.uploads[0]

    assert len(payload["predictions"]) == len(csv_forecast)
    uploaded_by_category = {
        p["category"]: p["predicted_quantity"] for p in payload["predictions"]
    }
    csv_by_category = dict(
        zip(csv_forecast["Menu"], csv_forecast[PREDICTED_QTY_COLUMN], strict=True)
    )
    assert uploaded_by_category == csv_by_category

    latest_input_date = pd.read_csv(
        Path(__file__).parents[3] / "data" / "coffeeshop_daily_sales_report.csv"
    )["Date"].pipe(pd.to_datetime).max()
    assert payload["forecast_date"] == (
        latest_input_date + pd.Timedelta(days=1)
    ).strftime("%Y-%m-%d")
