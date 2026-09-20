from typing import TYPE_CHECKING

from common.consts import REQUIRED_COLUMNS

if TYPE_CHECKING:
    import pandas as pd


def validate_required_columns_present(sales: pd.DataFrame) -> None:
    missing_columns = REQUIRED_COLUMNS.difference(sales.columns)
    if missing_columns:
        raise ValueError(
            f"Recent-sales JSON is missing columns: {sorted(missing_columns)}"
        )
