import requests

from common import logger
from inference.config import CONFIG
from inference.http_session import create_http_session

http = create_http_session()

log = logger.get_logger(__name__)


def get_api_token() -> str:
    if CONFIG.simulation_mode:
        return "simulation-token"
    try:
        # This will fail when not on Databricks - abstract away
        return dbutils.secrets.get(
            scope=CONFIG.secret_scope,
            key=CONFIG.secret_key,
        )
    except NameError as error:
        raise RuntimeError("Real API mode requires Databricks Secrets.") from error


def request_headers() -> dict:
    return {
        "Authorization": f"Bearer {get_api_token()}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def fetch_source_payload() -> dict[str, any]:
    response = http.get(
        str(CONFIG.source_endpoint_url),
        headers=request_headers(),
        params={"history_days": CONFIG.history_days},
    )
    response.raise_for_status()
    source_payload = response.json()
    log.info("Recent-sales GET status: %s", response.status_code)
    return source_payload


def upload_inference_results(result_payload: dict) -> None:
    response = http.post(
        CONFIG.result_endpoint_url,
        headers=request_headers(),
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
