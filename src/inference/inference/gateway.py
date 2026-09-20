from typing import Protocol

import pandas as pd
import requests
from common.consts import CATEGORY_COLUMN, DATE_COLUMN, TARGET_COLUMN

from common import logger
from inference.config import CONFIG, Config
from inference.http_session import create_http_session

log = logger.get_logger(__name__)


class SalesGateway(Protocol):
    def fetch_source_payload(self) -> dict: ...
    def upload_inference_results(self, payload: dict) -> None: ...


def make_gateway(config: Config) -> SalesGateway:
    if config.simulation_mode:
        return _SimulatedGateway()
    return _RestGateway(create_http_session())


def _get_api_token() -> str:
    try:
        # This will fail when not on Databricks - abstract away
        return dbutils.secrets.get(
            scope=CONFIG.secret_scope,
            key=CONFIG.secret_key,
        )
    except NameError as error:
        raise RuntimeError("Real API mode requires Databricks Secrets.") from error


def _request_headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_api_token()}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


class _RestGateway:
    def __init__(self, http: requests.Session) -> None:
        self.http = http

    def fetch_source_payload(self) -> dict[str, any]:
        response = self.http.get(
            str(CONFIG.source_endpoint_url),
            headers=_request_headers(),
            params={"history_days": CONFIG.history_days},
        )
        response.raise_for_status()
        source_payload = response.json()
        log.info("Recent-sales GET status: %s", response.status_code)
        return source_payload

    def upload_inference_results(self, result_payload: dict) -> None:
        response = self.http.post(
            CONFIG.result_endpoint_url,
            headers=_request_headers(),
            json=result_payload,
        )

        response.raise_for_status()

        try:
            response_body = response.json()

        except requests.exceptions.JSONDecodeError:
            response_body = response.text

        outbound_result = {
            "status_code": response.status_code,
            "response": response_body,
        }

        log.info("Forecast POST status: %d", response.status_code)
        log.info(outbound_result)


class _SimulatedGateway:
    def fetch_source_payload(self) -> dict[str, any]:
        data_directory = CONFIG.data_dir

        if not data_directory.exists():
            raise FileNotFoundError(
                "Simulation mode requires the bundled data directory."
            )

        source_frames = [
            pd.read_csv(path) for path in sorted(data_directory.glob("*.csv"))
        ]

        simulated_sales = pd.concat(source_frames, ignore_index=True)

        simulated_sales[DATE_COLUMN] = pd.to_datetime(
            simulated_sales[DATE_COLUMN], errors="coerce"
        )

        latest_date = simulated_sales[DATE_COLUMN].max()

        recent_sales = simulated_sales.loc[
            simulated_sales[DATE_COLUMN]
            >= latest_date - pd.Timedelta(days=CONFIG.history_days - 1),
            [DATE_COLUMN, CATEGORY_COLUMN, TARGET_COLUMN],
        ].copy()

        recent_sales[DATE_COLUMN] = recent_sales[DATE_COLUMN].dt.strftime("%Y-%m-%d")

        source_payload = {"records": recent_sales.to_dict(orient="records")}

        log.info(
            "Simulated GET returned %d JSON records.", len(source_payload["records"])
        )
        return source_payload

    def upload_inference_results(self, payload: dict) -> None:
        log.info("Simulated POST with %d predictions.", len(payload["predictions"]))
        log.info(pd.DataFrame(payload["predictions"]))
