from typing import TYPE_CHECKING

from common.consts import CATEGORY_COLUMN, DATE_COLUMN, REQUIRED_COLUMNS, TARGET_COLUMN

if TYPE_CHECKING:
    import pandas as pd


def validate_required_columns_present(sales: "pd.DataFrame") -> None:
    missing_columns = REQUIRED_COLUMNS.difference(sales.columns)
    if missing_columns:
        raise ValueError(
            f"Recent-sales JSON is missing columns: {sorted(missing_columns)}"
        )


def columns_to_expected_types(sales: "pd.DataFrame") -> "pd.DataFrame":
    sales[DATE_COLUMN] = pd.to_datetime(sales[DATE_COLUMN], errors="coerce")
    sales[TARGET_COLUMN] = pd.to_numeric(sales[TARGET_COLUMN], errors="coerce")
    sales[CATEGORY_COLUMN] = (
        sales[CATEGORY_COLUMN]
        .astype("string")
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )
    return sales
