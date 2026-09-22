from typing import TYPE_CHECKING, cast

import pandas as pd
from common.preprocessing import (
    aggregate_per_category,
    columns_to_expected_types,
    get_valid_date_target_array,
    validate_required_columns_present,
)
from infra.logger import get_logger

if TYPE_CHECKING:
    from common.forecast_metadata import ForecastMetadata


def payload_to_dataframe(source_payload: dict) -> pd.DataFrame:
    if isinstance(
        source_payload, list
    ):  # TODO: validate - is this code path even alive?
        source_records = source_payload

    elif isinstance(source_payload, dict):
        records = source_payload.get("records")
        source_records = records if records is not None else source_payload.get("data")

    else:
        source_records = None

    if not isinstance(source_records, list) or not source_records:
        raise ValueError(
            "The recent-sales endpoint must return a non-empty JSON record list."
        )

    return pd.DataFrame.from_records(source_records)


def preprocess_data(metadata: ForecastMetadata, sales: pd.DataFrame) -> pd.DataFrame:
    """Normalize the response into one daily row per known category, fill absent date-category combinations with zero, and verify enough history exists for the model's 28-day features."""
    log = get_logger(__name__)
    validate_required_columns_present(sales)
    model_config = metadata.configuration
    sales = columns_to_expected_types(sales)

    valid_rows = get_valid_date_target_array(sales)
    valid_rows &= sales[model_config.category_column].isin(metadata.categories)
    sales = sales.loc[
        valid_rows,
        [
            model_config.date_column,
            model_config.category_column,
            model_config.target_column,
        ],
    ]

    target_sums = cast(
        "pd.Series",
        sales.groupby([model_config.date_column, model_config.category_column])[
            model_config.target_column
        ].sum(),
    )
    daily_sales = target_sums.reset_index().sort_values(
        [model_config.category_column, model_config.date_column]
    )
    if daily_sales.empty:
        raise ValueError(
            "No sales history available after filtering to known categories."
        )
    latest_date = cast("pd.Timestamp", daily_sales[model_config.date_column].max())
    first_required_date = latest_date - pd.Timedelta(days=27)
    # TODO: this only bounds the pooled min/max date span, not per-category contiguity —
    # a category closed for several days mid-window still passes here and gets zero-filled
    # by aggregate_per_category() below instead of raised. See docs/TODO.md (data-drift
    # guardrails) for the tracked follow-up.
    if daily_sales[model_config.date_column].min() > first_required_date:
        raise ValueError(
            "At least 28 consecutive calendar days of history are required for inference."
        )

    all_dates = pd.date_range(
        daily_sales[model_config.date_column].min(), latest_date, freq="D"
    )
    complete_index = pd.MultiIndex.from_product(
        [all_dates, metadata.categories],
        names=[model_config.date_column, model_config.category_column],
    )
    daily_sales = aggregate_per_category(complete_index, daily_sales)

    log.info(
        "Prepared %d days through %s for %d categories.",
        len(all_dates),
        latest_date.date(),
        len(metadata.categories),
    )

    return daily_sales
