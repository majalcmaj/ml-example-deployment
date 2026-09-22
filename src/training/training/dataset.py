from typing import TYPE_CHECKING

from forecasting.features import one_hot_encode_categories, reindex_to_contract

from training.outliers import IS_OUTLIER_COLUMN

if TYPE_CHECKING:
    import pandas as pd


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
