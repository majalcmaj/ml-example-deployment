from typing import TYPE_CHECKING, cast

import pandas as pd
from common.features import create_time_features

if TYPE_CHECKING:
    from common.forecast_metadata import ForecastMetadata


def reconsturct_features(
    latest_date: pd.Timestamp, metadata: ForecastMetadata, daily_sales: pd.DataFrame
) -> tuple[pd.Timestamp, pd.DataFrame, pd.DataFrame]:
    """Append the incoming day and calculate calendar, lag, and rolling features exactly as in training. Align the encoded columns to the stored model contract before predicting."""
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
    future_features = future_features.loc[
        future_features[model_config.date_column] == forecast_date
    ].copy()

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
    return forecast_date, future_features, X_future
