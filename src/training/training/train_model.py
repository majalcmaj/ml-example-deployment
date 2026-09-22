from typing import TYPE_CHECKING

from xgboost import XGBRegressor

if TYPE_CHECKING:
    import pandas as pd


def fit_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_validation: pd.DataFrame,
    y_validation: pd.Series,
    random_seed: int,
) -> XGBRegressor:
    model = XGBRegressor(
        objective="count:poisson",
        n_estimators=400,
        learning_rate=0.05,
        max_depth=6,
        min_child_weight=3,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_lambda=1.0,
        random_state=random_seed,
        n_jobs=-1,
        eval_metric="mae",
    )
    model.fit(X_train, y_train, eval_set=[(X_validation, y_validation)], verbose=False)
    return model
