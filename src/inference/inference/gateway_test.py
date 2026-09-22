from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

from inference import gateway
from inference.config import Config

if TYPE_CHECKING:
    import requests


def make_config(**overrides: object) -> Config:
    defaults: dict[str, object] = {
        "source_endpoint_url": "https://example.invalid/api/recent-sales",
        "result_endpoint_url": "https://example.invalid/api/demand-forecast",
        "history_days": 45,
        "artifact_dir": Path("outputs"),
        "output_dir": Path("outputs"),
    }
    defaults.update(overrides)
    return Config.model_validate(defaults)


class FakeSecretsProvider:
    def __init__(self, token: str = "fake-token") -> None:
        self.token = token

    def get_token(self) -> str:
        return self.token


class FakeResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.get_calls: list[dict] = []
        self.post_calls: list[dict] = []

    def get(self, url: str, headers: dict, params: dict) -> FakeResponse:
        self.get_calls.append({"url": url, "headers": headers, "params": params})
        return self.response

    def post(self, url: str, headers: dict, json: dict) -> FakeResponse:
        self.post_calls.append({"url": url, "headers": headers, "json": json})
        return self.response


def test_rest_gateway_injects_config_and_secrets_provider() -> None:
    config = make_config()
    secrets_provider = FakeSecretsProvider()
    result = gateway.RestGateway(config, secrets_provider=secrets_provider)
    assert isinstance(result, gateway.RestGateway)
    assert result.config is config
    assert result.secrets_provider is secrets_provider


def test_rest_gateway_fetch_source_payload_uses_injected_config_and_token() -> None:
    config = make_config(history_days=45)
    response = FakeResponse(payload={"records": [{"a": 1}]})
    session = FakeSession(response)
    rest_gateway = gateway.RestGateway(
        config, FakeSecretsProvider("tok-123"), cast("requests.Session", session)
    )

    payload = rest_gateway.fetch_source_payload()

    assert payload == {"records": [{"a": 1}]}
    assert len(session.get_calls) == 1
    call = session.get_calls[0]
    assert call["url"] == str(config.source_endpoint_url)
    assert call["headers"]["Authorization"] == "Bearer tok-123"
    assert call["params"] == {"history_days": 45}


def test_rest_gateway_upload_inference_results_uses_injected_config_and_token() -> None:
    config = make_config()
    response = FakeResponse(payload={"status": "ok"})
    session = FakeSession(response)
    rest_gateway = gateway.RestGateway(
        config, FakeSecretsProvider("tok-456"), cast("requests.Session", session)
    )

    rest_gateway.upload_inference_results({"predictions": []})

    assert len(session.post_calls) == 1
    call = session.post_calls[0]
    assert call["url"] == str(config.result_endpoint_url)
    assert call["headers"]["Authorization"] == "Bearer tok-456"
    assert call["json"] == {"predictions": []}


def test_rest_gateway_uses_env_secrets_provider_by_default() -> None:
    config = make_config()
    result = gateway.RestGateway(config)
    assert isinstance(result, gateway.RestGateway)
    assert isinstance(result.secrets_provider, gateway._EnvSecretsProvider)


def test_env_secrets_provider_reads_injected_env() -> None:
    provider = gateway._EnvSecretsProvider({"INFERENCE_API_TOKEN": "env-token"})
    assert provider.get_token() == "env-token"


def test_env_secrets_provider_raises_when_token_unset() -> None:
    provider = gateway._EnvSecretsProvider({})
    with pytest.raises(RuntimeError, match="INFERENCE_API_TOKEN"):
        provider.get_token()
