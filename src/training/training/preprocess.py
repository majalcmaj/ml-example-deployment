from typing import cast

import pandas as pd
from forecasting.consts import CATEGORY_COLUMN, DATE_COLUMN, TARGET_COLUMN
from forecasting.preprocessing import (
    aggregate_per_category,
    columns_to_expected_types,
    get_valid_date_target_array,
    validate_required_columns_present,
)


def clean_sales(raw_sales: pd.DataFrame) -> pd.DataFrame:
    """Drop invalid/duplicate rows; keep only rows with a valid date, target, and category."""
    validate_required_columns_present(raw_sales)
    sales = raw_sales.copy()

    unnamed_columns = [
        column for column in sales.columns if column.lower().startswith("unnamed:")
    ]
    sales = sales.drop(columns=unnamed_columns)
    sales = columns_to_expected_types(sales)
    sales = sales.drop_duplicates()

    valid_rows = get_valid_date_target_array(sales)
    valid_rows &= sales[CATEGORY_COLUMN].notna() & sales[CATEGORY_COLUMN].ne("")
    return sales.loc[valid_rows].copy()


def build_daily_panel(sales: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Sum repeated date-category rows, then fill every date x category combination absent from the data with zero."""
    daily_sales = cast(
        "pd.DataFrame",
        sales.groupby([DATE_COLUMN, CATEGORY_COLUMN], as_index=False)[TARGET_COLUMN].sum(),
    ).sort_values([CATEGORY_COLUMN, DATE_COLUMN])
    all_categories = sorted(daily_sales[CATEGORY_COLUMN].unique())
    all_dates = pd.date_range(
        daily_sales[DATE_COLUMN].min(), daily_sales[DATE_COLUMN].max(), freq="D"
    )
    complete_index = pd.MultiIndex.from_product(
        [all_dates, all_categories], names=[DATE_COLUMN, CATEGORY_COLUMN]
    )
    return aggregate_per_category(complete_index, daily_sales), all_categories
