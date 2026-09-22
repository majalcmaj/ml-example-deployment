import json
from datetime import date
from typing import TYPE_CHECKING

import pandas as pd

from inference import record_store

if TYPE_CHECKING:
    from pathlib import Path


class FakeS3Client:
    def __init__(self) -> None:
        self.put_calls: list[dict] = []

    def put_object(self, **kwargs: object) -> None:
        self.put_calls.append(kwargs)


def make_forecast() -> pd.DataFrame:
    return pd.DataFrame({"Menu": ["Coffee", "Tea"], "Predicted_Qty": [5, 3]})


def test_local_store_writes_forecast_csv_and_source_payload(tmp_path: Path) -> None:
    store = record_store.LocalForecastRecordStore(tmp_path)
    forecast = make_forecast()
    source_payload = {"records": [{"Menu": "Coffee", "Total_Qty": 4}]}

    store.store(date(2026, 9, 23), forecast, source_payload)

    csv_path = tmp_path / record_store.FORECAST_FILENAME
    assert csv_path.exists()
    assert pd.read_csv(csv_path).equals(forecast)

    payload_path = tmp_path / "source_payload_2026-09-23.json"
    assert json.loads(payload_path.read_text()) == source_payload


def test_local_store_unwraps_numpy_scalars_in_source_payload(tmp_path: Path) -> None:
    import numpy as np

    store = record_store.LocalForecastRecordStore(tmp_path)
    source_payload = {"records": [{"Total_Qty": np.int64(7)}]}

    store.store(date(2026, 9, 23), make_forecast(), source_payload)

    stored = json.loads((tmp_path / "source_payload_2026-09-23.json").read_text())
    assert stored == {"records": [{"Total_Qty": 7}]}
    assert isinstance(stored["records"][0]["Total_Qty"], int)


def test_s3_store_puts_forecast_and_source_payload_under_dated_key() -> None:
    client = FakeS3Client()
    store = record_store.S3ForecastRecordStore(
        "forecast-bucket", "predictions", s3_client=client
    )
    forecast = make_forecast()
    source_payload = {"records": [{"Menu": "Coffee", "Total_Qty": 4}]}

    store.store(date(2026, 9, 23), forecast, source_payload)

    assert len(client.put_calls) == 2
    forecast_call, payload_call = client.put_calls

    assert forecast_call["Bucket"] == "forecast-bucket"
    assert forecast_call["Key"] == "predictions/2026-09-23/inference_next_day_forecast.csv"
    assert forecast_call["Body"].decode("utf-8") == forecast.to_csv(index=False)

    assert payload_call["Key"] == "predictions/2026-09-23/source_payload_2026-09-23.json"
    assert json.loads(payload_call["Body"]) == source_payload


def test_s3_store_strips_leading_and_trailing_slashes_from_prefix() -> None:
    store = record_store.S3ForecastRecordStore(
        "bucket", "/predictions/", s3_client=FakeS3Client()
    )
    assert store.prefix == "predictions"
