from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd
from forecasting.consts import CATEGORY_COLUMN, DATE_COLUMN, TARGET_COLUMN
from forecasting.csv_loading import load_csv_directory

from infra import logger

if TYPE_CHECKING:
    from pathlib import Path

log = logger.get_logger(__name__)


class StubSalesGateway:
    def __init__(self, data_dir: Path, *, history_days: int) -> None:
        self.data_dir = data_dir
        self.history_days = history_days
        self.uploads: list[dict] = []

    def fetch_source_payload(self) -> dict[str, Any]:
        simulated_sales, _ = load_csv_directory(self.data_dir)

        simulated_sales[DATE_COLUMN] = pd.to_datetime(
            simulated_sales[DATE_COLUMN], errors="coerce"
        )

        latest_date = simulated_sales[DATE_COLUMN].max()

        recent_sales = simulated_sales.loc[
            simulated_sales[DATE_COLUMN]
            >= latest_date - pd.Timedelta(days=self.history_days - 1),
            [DATE_COLUMN, CATEGORY_COLUMN, TARGET_COLUMN],
        ].copy()

        recent_sales[DATE_COLUMN] = recent_sales[DATE_COLUMN].dt.strftime("%Y-%m-%d")

        source_payload = {"records": recent_sales.to_dict(orient="records")}

        log.info(
            "Stub GET returned %d JSON records.", len(source_payload["records"])
        )
        return source_payload

    def upload_inference_results(self, payload: dict) -> None:
        self.uploads.append(payload)
        log.info("Stub POST with %d predictions.", len(payload["predictions"]))
