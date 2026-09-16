import tomllib
from pathlib import Path
from dataclasses import dataclass
from urllib.parse import urlparse
from pydantic import BaseModel, ConfigDict, HttpUrl, PositiveInt


class Config(BaseModel):
    source_endpoint_url: HttpUrl
    result_endpoint_url: HttpUrl
    secret_scope: str
    secret_key: str
    simulation_mode: bool
    history_days: PositiveInt
    request_timeout_s: PositiveInt

    model_config = ConfigDict(frozen=True)


def _parse_config() -> Config:
    with Path("config.toml").open() as f:
        content = f.read()
        return Config(**tomllib.loads(content))


CONFIG = _parse_config()
