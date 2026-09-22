import os
from typing import TYPE_CHECKING, Any, Protocol

import requests

from inference.http_session import create_http_session
from infra import logger

if TYPE_CHECKING:
    from inference.config import Config

log = logger.get_logger(__name__)


class SalesGateway(Protocol):
    def fetch_source_payload(self) -> dict: ...
    def upload_inference_results(self, payload: dict) -> None: ...


class SecretsProvider(Protocol):
    def get_token(self) -> str: ...


class _EnvSecretsProvider:
    def get_token(self) -> str:
        token = os.environ.get("INFERENCE_API_TOKEN")
        if not token:
            raise RuntimeError(
                "INFERENCE_API_TOKEN is not set; the source API cannot be authenticated."
            )
        return token


def make_gateway(
    config: Config, secrets_provider: SecretsProvider | None = None
) -> SalesGateway:
    """Sends an authenticated GET request and expects either a JSON list or an object containing `records` or `data`. The endpoint must supply at least 28 calendar days of history."""
    return _RestGateway(
        create_http_session(), config, secrets_provider or _EnvSecretsProvider()
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
            "Authorization": f"Bearer {self.secrets_provider.get_token()}",
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
