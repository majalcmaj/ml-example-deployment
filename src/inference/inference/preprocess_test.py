import pandas as pd
import pytest
from common.forecast_metadata import ForecastMetadata, ModelConfiguration

from inference.preprocess import preprocess_data


def make_metadata(categories: list[str] | None = None) -> ForecastMetadata:
    return ForecastMetadata(
        model_feature_columns=[],
        raw_feature_columns=[],
        categories=categories or ["Coffee"],
        category_dummy_columns=[],
        configuration=ModelConfiguration(
            date_column="Date",
            category_column="Menu",
            target_column="Total_Qty",
            validation_days=7,
            random_seed=0,
        ),
        outlier_bounds=pd.DataFrame(),
        validation_metrics={},
    )


def test_preprocess_data_raises_value_error_for_missing_columns() -> None:
    metadata = make_metadata()
    sales = pd.DataFrame({"Date": ["2026-01-01"], "Menu": ["Coffee"]})  # no Total_Qty

    with pytest.raises(ValueError, match="missing columns"):
        preprocess_data(metadata, sales)


def test_preprocess_data_succeeds_when_called_directly_with_valid_sales() -> None:
    metadata = make_metadata()
    dates = pd.date_range("2026-01-01", periods=28, freq="D")
    sales = pd.DataFrame(
        {
            "Date": dates.strftime("%Y-%m-%d"),
            "Menu": "Coffee",
            "Total_Qty": 5,
        }
    )

    _all_dates, latest_date, daily_sales = preprocess_data(metadata, sales)

    assert latest_date == dates.max()
    assert len(daily_sales) == 28
