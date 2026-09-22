from dataclasses import dataclass
from typing import cast

import pandas as pd
from forecasting.features import one_hot_encode_categories, reindex_to_contract

from training.outliers import IS_OUTLIER_COLUMN


@dataclass
class TrainValidationSplit:
    X_train: pd.DataFrame
    y_train: pd.Series
    X_validation: pd.DataFrame
    y_validation: pd.Series


def compute_validation_start(
    daily_sales: pd.DataFrame, validation_days: int, date_column: str
) -> pd.Timestamp:
    """Start of the final `validation_days`-day window in the panel, used as the train/validation cutoff."""
    return cast(
        "pd.Timestamp",
        daily_sales[date_column].max() - pd.Timedelta(days=validation_days - 1),
    )


def split_train_validation(
    featured_sales: pd.DataFrame, validation_start: pd.Timestamp, date_column: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Chronological split: training excludes flagged outliers, validation is the final window."""
    train_mask = (featured_sales[date_column] < validation_start) & ~featured_sales[
        IS_OUTLIER_COLUMN
    ]
    validation_mask = featured_sales[date_column] >= validation_start
    return featured_sales.loc[train_mask].copy(), featured_sales.loc[validation_mask].copy()


def encode_train_validation(
    train_data: pd.DataFrame,
    validation_data: pd.DataFrame,
    feature_columns: list[str],
    category_column: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    X_train = one_hot_encode_categories(train_data, feature_columns, category_column)
    X_validation = one_hot_encode_categories(
        validation_data, feature_columns, category_column
    )
    X_validation = reindex_to_contract(X_validation, X_train.columns.tolist())
    return X_train, X_validation


def prepare_train_validation(
    train_data: pd.DataFrame,
    validation_data: pd.DataFrame,
    feature_columns: list[str],
    category_column: str,
    target_column: str,
) -> TrainValidationSplit:
    """Encode features and pull out targets, so callers never index a DataFrame by a
    non-literal column name (which pandas-stubs can't type as `Series` without a cast)."""
    X_train, X_validation = encode_train_validation(
        train_data, validation_data, feature_columns, category_column
    )
    y_train = cast("pd.Series", train_data[target_column])
    y_validation = cast("pd.Series", validation_data[target_column])
    return TrainValidationSplit(X_train, y_train, X_validation, y_validation)
