from __future__ import annotations

from typing import TYPE_CHECKING

import joblib
import pandas as pd  # noqa: TC002 -- pydantic resolves field types at runtime
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from pathlib import Path


class ModelConfiguration(BaseModel):
    date_column: str
    category_column: str
    target_column: str
    validation_days: int
    random_seed: int


class ForecastMetadata(BaseModel):
    """Contract between training and inference for the columns, categories, and
    preprocessing the trained model expects. Persisted next to the model as
    `forecast_metadata.joblib`.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model_feature_columns: list[str]
    raw_feature_columns: list[str]
    categories: list[str]
    category_dummy_columns: list[str]
    configuration: ModelConfiguration
    outlier_bounds: pd.DataFrame
    validation_metrics: dict[str, float]

    def save(self, path: Path) -> None:
        joblib.dump(self.model_dump(), path)

    @classmethod
    def load(cls, path: Path) -> ForecastMetadata:
        return cls(**joblib.load(path))
