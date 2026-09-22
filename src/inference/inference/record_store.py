from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Protocol

from infra import logger

if TYPE_CHECKING:
    from datetime import date
    from pathlib import Path

    import pandas as pd

log = logger.get_logger(__name__)

FORECAST_FILENAME = "inference_next_day_forecast.csv"


def _json_default(value: object) -> object:
    # numpy scalars (e.g. from a pandas-backed source payload) aren't JSON-serializable
    # on their own; unwrap them to native Python types instead of stringifying.
    item = getattr(value, "item", None)
    if callable(item):
        return item()
    return str(value)


def _source_payload_filename(forecast_date: date) -> str:
    return f"source_payload_{forecast_date:%Y-%m-%d}.json"


class ForecastRecordStore(Protocol):
    """Persists a forecast run: the predictions themselves (for comparison against
    actuals once the forecast date has passed) and the source payload they were
    built from (for retraining)."""

    def store(
        self,
        forecast_date: date,
        forecast: pd.DataFrame,
        source_payload: dict[str, Any],
    ) -> None: ...


class LocalForecastRecordStore:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir

    def store(
        self,
        forecast_date: date,
        forecast: pd.DataFrame,
        source_payload: dict[str, Any],
    ) -> None:
        forecast.to_csv(self.output_dir / FORECAST_FILENAME, index=False)

        source_payload_path = self.output_dir / _source_payload_filename(forecast_date)
        source_payload_path.write_text(
            json.dumps(source_payload, indent=2, default=_json_default)
        )
        log.info("Stored forecast record for %s in %s", forecast_date, self.output_dir)
