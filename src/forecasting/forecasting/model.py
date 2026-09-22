from typing import TYPE_CHECKING, cast

import numpy as np
from infra.logger import get_logger
from xgboost import XGBRegressor

from forecasting.consts import MODEL_FILENAME

if TYPE_CHECKING:
    from pathlib import Path

    import pandas as pd

    from forecasting.metadata import ModelConfiguration


def load_model(artifact_dir: Path) -> XGBRegressor:
    model_path = artifact_dir / MODEL_FILENAME

    if not model_path.exists():
        raise FileNotFoundError(f"The trained model is missing from {artifact_dir}.")

    model = XGBRegressor()
    model.load_model(model_path)
    return model


def make_forecast(
    artifact_dir: Path,
    future_features: pd.DataFrame,
    X_future: pd.DataFrame,
    model_config: ModelConfiguration,
) -> pd.DataFrame:
    log = get_logger(__name__)
    model = load_model(artifact_dir)
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
    log.info("Forecast total units: %d", forecast["Predicted_Qty"].sum())
    return forecast.sort_values(model_config.category_column).reset_index(drop=True)
