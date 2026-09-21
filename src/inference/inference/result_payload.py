from __future__ import annotations

from datetime import (  # noqa: TC003 -- pydantic resolves field types at runtime
    date,
    datetime,
)

from pydantic import BaseModel, Field


class CategoryPrediction(BaseModel):
    category: str
    predicted_quantity: int = Field(ge=0)


class InferenceResultPayload(BaseModel):
    forecast_date: date
    generated_at_utc: datetime
    predictions: list[CategoryPrediction]
