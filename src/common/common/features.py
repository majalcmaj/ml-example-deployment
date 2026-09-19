from __future__ import annotations

from typing import TYPE_CHECKING

from common.consts import CATEGORY_COLUMN, DATE_COLUMN, TARGET_COLUMN

if TYPE_CHECKING:
    import pandas as pd


def create_time_features(data: pd.DataFrame) -> pd.DataFrame:
    featured = data.sort_values([CATEGORY_COLUMN, DATE_COLUMN]).copy()
    featured["Day_Of_Week"] = featured[DATE_COLUMN].dt.dayofweek
    featured["Month"] = featured[DATE_COLUMN].dt.month
    featured["Day_Of_Month"] = featured[DATE_COLUMN].dt.day
    featured["Day_Of_Year"] = featured[DATE_COLUMN].dt.dayofyear
    featured["Is_Weekend"] = featured["Day_Of_Week"].isin([5, 6]).astype(int)
    grouped_sales = featured.groupby(CATEGORY_COLUMN)[TARGET_COLUMN]
    for lag in [1, 7, 14, 28]:
        featured[f"Lag_{lag}"] = grouped_sales.shift(lag)

    for window in [7, 14, 28]:
        featured[f"Rolling_Mean_{window}"] = grouped_sales.transform(
            lambda values, window=window: values.shift(1).rolling(window).mean()
        )

        featured[f"Rolling_Std_{window}"] = grouped_sales.transform(
            lambda values, window=window: values.shift(1).rolling(window).std()
        )

    return featured
