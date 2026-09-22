from typing import TYPE_CHECKING, cast

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

if TYPE_CHECKING:
    from xgboost import XGBRegressor


def evaluate_predictions(
    validation_data: pd.DataFrame,
    X_validation: pd.DataFrame,
    model: XGBRegressor,
    date_column: str,
    category_column: str,
    target_column: str,
) -> tuple[pd.Series, pd.DataFrame]:
    """Report MAE, RMSE, and WMAPE overall and by category against the validation window."""
    predictions = np.clip(model.predict(X_validation), 0, None)
    evaluation = validation_data[[date_column, category_column, target_column]].copy()
    evaluation["Predicted_Qty"] = predictions
    evaluation["Absolute_Error"] = cast(
        "pd.Series", evaluation[target_column] - evaluation["Predicted_Qty"]
    ).abs()

    overall_metrics = pd.Series(
        {
            "MAE": mean_absolute_error(
                evaluation[target_column], evaluation["Predicted_Qty"]
            ),
            "RMSE": mean_squared_error(
                evaluation[target_column], evaluation["Predicted_Qty"]
            )
            ** 0.5,
            "WMAPE_Percent": 100
            * evaluation["Absolute_Error"].sum()
            / evaluation[target_column].sum(),
        },
        name="Overall",
    )

    category_metrics = cast(
        "pd.DataFrame",
        evaluation.groupby(category_column).apply(
            lambda group: pd.Series(
                {
                    "MAE": group["Absolute_Error"].mean(),
                    "RMSE": np.sqrt(
                        np.mean((group[target_column] - group["Predicted_Qty"]) ** 2)
                    ),
                    "WMAPE_Percent": 100
                    * group["Absolute_Error"].sum()
                    / max(group[target_column].sum(), 1),
                }
            ),
            include_groups=False,
        ),
    ).sort_values("WMAPE_Percent")
    return overall_metrics, category_metrics
