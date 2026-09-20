from typing import TYPE_CHECKING

from xgboost import XGBRegressor

if TYPE_CHECKING:
    from pathlib import Path


def load_model(artifact_dir: Path) -> XGBRegressor:
    model_path = artifact_dir / "xgb_daily_product_demand.json"

    if not model_path.exists():
        raise FileNotFoundError(f"The trained model is missing from {artifact_dir}.")

    model = XGBRegressor()
    model.load_model(model_path)
    return model
