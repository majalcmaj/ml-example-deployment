from __future__ import annotations

from datetime import (  # noqa: TC003 -- pydantic resolves field types at runtime
    date,
    datetime,
)
from typing import TYPE_CHECKING, cast

import pandas as pd
from forecasting.consts import PREDICTED_QTY_COLUMN
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from forecasting.metadata import ForecastMetadata

    from inference.gateway import SalesGateway


class CategoryPrediction(BaseModel):
    category: str
    predicted_quantity: int = Field(ge=0)


class InferenceResultPayload(BaseModel):
    forecast_date: date
    generated_at_utc: datetime
    predictions: list[CategoryPrediction]


def upload_inference_results(
    sales_gateway: SalesGateway,
    forecast_date: pd.Timestamp,
    forecast: pd.DataFrame,
    metadata: ForecastMetadata,
) -> None:
    result_payload = InferenceResultPayload(
        forecast_date=forecast_date.date(),
        generated_at_utc=pd.Timestamp.now(tz="UTC"),
        predictions=[
            CategoryPrediction(
                category=str(row[metadata.configuration.category_column]),
                predicted_quantity=int(cast("int", row[PREDICTED_QTY_COLUMN])),
            )
            for _, row in forecast.iterrows()
        ],
    )

    sales_gateway.upload_inference_results(result_payload.model_dump(mode="json"))
