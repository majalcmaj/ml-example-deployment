import pandas as pd

from forecasting.consts import (
    CATEGORY_COLUMN,
    DATE_COLUMN,
    REQUIRED_COLUMNS,
    TARGET_COLUMN,
)


def validate_required_columns_present(sales: pd.DataFrame) -> None:
    missing_columns = REQUIRED_COLUMNS.difference(sales.columns)
    if missing_columns:
        raise ValueError(
            f"Recent-sales JSON is missing columns: {sorted(missing_columns)}"
        )


# TODO: consider splitting
def columns_to_expected_types(sales: pd.DataFrame) -> pd.DataFrame:
    sales = sales.copy()
    sales[DATE_COLUMN] = pd.to_datetime(sales[DATE_COLUMN], errors="coerce")
    sales[TARGET_COLUMN] = pd.to_numeric(sales[TARGET_COLUMN], errors="coerce")
    sales[CATEGORY_COLUMN] = (
        sales[CATEGORY_COLUMN]
        .astype("string")
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )
    return sales


def get_valid_date_target_array(sales: pd.DataFrame) -> pd.DataFrame:
    return (
        sales[DATE_COLUMN].notna()
        & sales[TARGET_COLUMN].notna()
        & sales[TARGET_COLUMN].ge(0)
    )


def aggregate_per_category(
    complete_index: pd.MultiIndex, daily_sales: pd.DataFrame
) -> pd.DataFrame:

    return (
        daily_sales.set_index([DATE_COLUMN, CATEGORY_COLUMN])
        .reindex(complete_index, fill_value=0)
        .reset_index()
        .sort_values([CATEGORY_COLUMN, DATE_COLUMN])
        .reset_index(drop=True)
    )
