from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

IS_OUTLIER_COLUMN = "Is_Outlier"


def flag_outliers(
    daily_sales: pd.DataFrame,
    validation_start: pd.Timestamp,
    category_column: str,
    date_column: str,
    target_column: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Flag 1.5x-IQR outliers per category, using bounds from dates before the validation window only."""
    bounds_source = daily_sales.loc[daily_sales[date_column] < validation_start]
    category_quartiles = (
        bounds_source.groupby(category_column)[target_column]
        .quantile([0.25, 0.75])
        .unstack()
    )
    category_quartiles.columns = ["Q1", "Q3"]
    category_quartiles["IQR"] = category_quartiles["Q3"] - category_quartiles["Q1"]
    category_quartiles["Lower_Bound"] = (
        category_quartiles["Q1"] - 1.5 * category_quartiles["IQR"]
    ).clip(lower=0)
    category_quartiles["Upper_Bound"] = (
        category_quartiles["Q3"] + 1.5 * category_quartiles["IQR"]
    )

    daily_sales = daily_sales.join(
        category_quartiles[["Lower_Bound", "Upper_Bound"]], on=category_column
    )
    daily_sales[IS_OUTLIER_COLUMN] = (
        daily_sales[date_column] < validation_start
    ) & ~daily_sales[target_column].between(
        daily_sales["Lower_Bound"], daily_sales["Upper_Bound"]
    )
    return daily_sales, category_quartiles
