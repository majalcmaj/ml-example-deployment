from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pandas as pd

from forecasting.consts import CATEGORY_COLUMN, DATE_COLUMN, TARGET_COLUMN

if TYPE_CHECKING:
    from forecasting.metadata import ForecastMetadata


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


# TODO: build_future_features()'s placeholder-row + create_time_features() block and
# encode_for_model()'s get_dummies + reindex-to-contract block are both near-duplicated in
# src/training/training/daily_product_demand_forecast.py (see the matching TODO there). Share
# one implementation between training and inference. Tracked in docs/TODO.md ("Single shared
# feature extraction implementation").


def build_future_features(
    latest_date: pd.Timestamp, metadata: ForecastMetadata, daily_sales: pd.DataFrame
) -> pd.DataFrame:
    """Append the incoming day and calculate calendar, lag, and rolling features exactly as in training."""
    model_config = metadata.configuration
    forecast_date = cast("pd.Timestamp", latest_date + pd.Timedelta(days=1))
    future_rows = pd.DataFrame(
        {
            model_config.date_column: forecast_date,
            model_config.category_column: metadata.categories,
            model_config.target_column: 0.0,
        }
    )
    history_and_future = pd.concat([daily_sales, future_rows], ignore_index=True)
    future_features = create_time_features(history_and_future)
    return future_features.loc[
        future_features[model_config.date_column] == forecast_date
    ].copy()


def encode_for_model(
    future_features: pd.DataFrame, metadata: ForecastMetadata
) -> pd.DataFrame:
    """Align the encoded columns to the stored model contract before predicting."""
    model_config = metadata.configuration
    X_future = pd.get_dummies(
        future_features[metadata.raw_feature_columns],
        columns=[model_config.category_column],
        dtype=int,
    )
    X_future = X_future.reindex(columns=metadata.model_feature_columns, fill_value=0)
    if X_future.isna().any().any():
        raise ValueError(
            "Recent sales did not provide enough history to calculate every model feature."
        )
    return X_future
