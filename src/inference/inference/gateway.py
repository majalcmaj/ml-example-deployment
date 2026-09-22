from typing import TYPE_CHECKING, Any, Protocol

import pandas as pd
import requests
from common.consts import CATEGORY_COLUMN, DATE_COLUMN, TARGET_COLUMN

from common import logger
from inference.http_session import create_http_session

if TYPE_CHECKING:
    from inference.config import Config

log = logger.get_logger(__name__)


class SalesGateway(Protocol):
    def fetch_source_payload(self) -> dict: ...
    def upload_inference_results(self, payload: dict) -> None: ...


class SecretsProvider(Protocol):
    def get_token(self, config: Config) -> str: ...


class _DatabricksSecretsProvider:
    def get_token(self, config: Config) -> str:
        try:
            dbutils_module = dbutils  # pyright: ignore[reportUndefinedVariable]
        except NameError as error:
            raise RuntimeError("Real API mode requires Databricks Secrets.") from error
        return dbutils_module.secrets.get(
            scope=config.secret_scope,
            key=config.secret_key.get_secret_value(),
        )


def make_gateway(
    config: Config, secrets_provider: SecretsProvider | None = None
) -> SalesGateway:
    """Real mode sends an authenticated GET request and expects either a JSON list or an object containing `records` or `data`. Simulation mode creates the same payload from the latest bundled CSV records. The endpoint must supply at least 28 calendar days of history."""
    if config.simulation_mode:
        return _SimulatedGateway(config)
    return _RestGateway(
        create_http_session(), config, secrets_provider or _DatabricksSecretsProvider()
    )


class _RestGateway:
    def __init__(
        self, http: requests.Session, config: Config, secrets_provider: SecretsProvider
    ) -> None:
        self.http = http
        self.config = config
        self.secrets_provider = secrets_provider

    def _request_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.secrets_provider.get_token(self.config)}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def fetch_source_payload(self) -> dict[str, Any]:
        response = self.http.get(
            str(self.config.source_endpoint_url),
            headers=self._request_headers(),
            params={"history_days": self.config.history_days},
        )
        response.raise_for_status()
        source_payload = response.json()
        log.info("Recent-sales GET status: %s", response.status_code)
        return source_payload

    def upload_inference_results(self, payload: dict) -> None:
        response = self.http.post(
            str(self.config.result_endpoint_url),
            headers=self._request_headers(),
            json=payload,
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
    def __init__(self, config: Config) -> None:
        self.config = config

    def fetch_source_payload(self) -> dict[str, Any]:
        data_directory = self.config.data_dir

        if not data_directory.exists():
            raise FileNotFoundError(
                "Simulation mode requires the bundled data directory."
            )

        # TODO: no de-dup guard — globs every CSV in data_dir, so overlapping/duplicate
        # bundled CSVs would silently double-count sales. Latent today (one bundled CSV).
        # See docs/TODO.md.
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
            >= latest_date - pd.Timedelta(days=self.config.history_days - 1),
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
