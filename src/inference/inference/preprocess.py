from typing import TYPE_CHECKING, cast

import pandas as pd
from forecasting.features import latest_sale_date
from forecasting.preprocessing import (
    aggregate_per_category,
    columns_to_expected_types,
    get_valid_date_target_array,
    validate_required_columns_present,
)
from infra.logger import get_logger

if TYPE_CHECKING:
    from forecasting.metadata import ForecastMetadata


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

    date_valid = get_valid_date_target_array(sales)
    category_valid = sales[model_config.category_column].isin(metadata.categories)
    dropped_unknown_category = int((date_valid & ~category_valid).sum())
    if dropped_unknown_category:
        log.warning(
            "Dropped %d row(s) with a category not in the model's known categories.",
            dropped_unknown_category,
        )
    valid_rows = date_valid & category_valid
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
    latest_date = latest_sale_date(daily_sales, metadata)
    first_required_date = latest_date - pd.Timedelta(days=27)
    if daily_sales[model_config.date_column].min() > first_required_date:
        raise ValueError(
            "At least 28 consecutive calendar days of history are required for inference."
        )

    # NOTE: per-category contiguity (a category closed for several days mid-window still passes
    # here and gets zero-filled by aggregate_per_category() below instead of raised) is NOT
    # fixed by counting distinct dates per category against the window span: real sales data has
    # categories that legitimately sell zero units on plenty of days (a raw sales-event feed has
    # no row for a zero-sale day at all), so "fewer rows than window days" fires on almost every
    # category in practice and can't be told apart from an actual reporting gap without a
    # separate assortment/availability signal. See docs/TODO.md (data-drift guardrails).
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
