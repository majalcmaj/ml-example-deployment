from typing import TYPE_CHECKING, cast

import numpy as np

from inference.model_loader import load_model

if TYPE_CHECKING:
    from pathlib import Path

    import pandas as pd
    from common.forecast_metadata import ModelConfiguration


def make_forecast(
    ARTIFACT_DIR: Path,
    future_features: pd.DataFrame,
    X_future: pd.DataFrame,
    model_config: ModelConfiguration,
) -> pd.DataFrame:
    model = load_model(ARTIFACT_DIR)
    predicted_quantities = np.rint(np.clip(model.predict(X_future), 0, None)).astype(
        int
    )
    forecast = cast(
        "pd.DataFrame",
        future_features[
            [model_config.date_column, model_config.category_column]
        ].copy(),
    )
    forecast["Predicted_Qty"] = predicted_quantities
    return forecast.sort_values(model_config.category_column).reset_index(drop=True)
