from typing import TYPE_CHECKING, cast

import numpy as np
import pandas as pd
from forecasting.consts import (
    CATEGORY_COLUMN,
    DATE_COLUMN,
    PREDICTED_QTY_COLUMN,
    TARGET_COLUMN,
)
from sklearn.metrics import mean_absolute_error, mean_squared_error

if TYPE_CHECKING:
    from xgboost import XGBRegressor


def evaluate_predictions(
    validation_data: pd.DataFrame, X_validation: pd.DataFrame, model: XGBRegressor
) -> tuple[pd.Series, pd.DataFrame]:
    """Report MAE, RMSE, and WMAPE overall and by category against the validation window."""
    predictions = np.clip(model.predict(X_validation), 0, None)
    evaluation = validation_data[[DATE_COLUMN, CATEGORY_COLUMN, TARGET_COLUMN]].copy()
    evaluation[PREDICTED_QTY_COLUMN] = predictions
    evaluation["Absolute_Error"] = cast(
        "pd.Series", evaluation[TARGET_COLUMN] - evaluation[PREDICTED_QTY_COLUMN]
    ).abs()

    overall_metrics = pd.Series(
        {
            "MAE": mean_absolute_error(
                evaluation[TARGET_COLUMN], evaluation[PREDICTED_QTY_COLUMN]
            ),
            "RMSE": mean_squared_error(
                evaluation[TARGET_COLUMN], evaluation[PREDICTED_QTY_COLUMN]
            )
            ** 0.5,
            "WMAPE_Percent": 100
            * evaluation["Absolute_Error"].sum()
            / evaluation[TARGET_COLUMN].sum(),
        },
        name="Overall",
    )

    category_metrics = cast(
        "pd.DataFrame",
        evaluation.groupby(CATEGORY_COLUMN).apply(
            lambda group: pd.Series(
                {
                    "MAE": group["Absolute_Error"].mean(),
                    "RMSE": np.sqrt(
                        np.mean(
                            (group[TARGET_COLUMN] - group[PREDICTED_QTY_COLUMN]) ** 2
                        )
                    ),
                    "WMAPE_Percent": 100
                    * group["Absolute_Error"].sum()
                    / max(group[TARGET_COLUMN].sum(), 1),
                }
            ),
            include_groups=False,
        ),
    ).sort_values("WMAPE_Percent")
    return overall_metrics, category_metrics
