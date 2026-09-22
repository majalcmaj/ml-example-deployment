from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Protocol

from infra import logger

if TYPE_CHECKING:
    from datetime import date
    from pathlib import Path

    import boto3
    import pandas as pd

log = logger.get_logger(__name__)

FORECAST_FILENAME = "inference_next_day_forecast.csv"


def _json_default(value: object) -> object:
    # numpy scalars (e.g. from a pandas-backed source payload) aren't JSON-serializable
    # on their own; unwrap them to native Python types instead of stringifying.
    if hasattr(value, "item"):
        return value.item()
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
        log.info(
            "Stored forecast record for %s in %s", forecast_date, self.output_dir
        )


class S3ForecastRecordStore:
    """Writes the same forecast record to S3 instead of local disk, keyed by
    forecast date. Customers read the forecast object directly off the bucket;
    the source payload alongside it is what we use to check predictions against
    actuals and to retrain the model."""

    def __init__(
        self, bucket: str, prefix: str, s3_client: boto3.client | None = None
    ) -> None:
        if s3_client is None:
            import boto3 as _boto3

            s3_client = _boto3.client("s3")
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.s3_client = s3_client

    def _key(self, forecast_date: date, filename: str) -> str:
        return f"{self.prefix}/{forecast_date:%Y-%m-%d}/{filename}"

    def store(
        self,
        forecast_date: date,
        forecast: pd.DataFrame,
        source_payload: dict[str, Any],
    ) -> None:
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=self._key(forecast_date, FORECAST_FILENAME),
            Body=forecast.to_csv(index=False).encode("utf-8"),
            ContentType="text/csv",
        )
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=self._key(forecast_date, _source_payload_filename(forecast_date)),
            Body=json.dumps(
                source_payload, indent=2, default=_json_default
            ).encode("utf-8"),
            ContentType="application/json",
        )
        log.info(
            "Stored forecast record for %s in s3://%s/%s",
            forecast_date,
            self.bucket,
            self.prefix,
        )
