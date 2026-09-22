from pathlib import Path

from infra.config import load_config
from pydantic import BaseModel, ConfigDict, HttpUrl, PositiveInt, SecretStr


class Config(BaseModel):
    source_endpoint_url: HttpUrl
    result_endpoint_url: HttpUrl
    secret_scope: str
    secret_key: SecretStr
    simulation_mode: bool
    history_days: PositiveInt
    data_dir: Path
    artifact_dir: Path
    output_dir: Path
    model_config = ConfigDict(frozen=True)


CONFIG = load_config(Config, Path(__file__).parent / "config.toml", env_prefix="INFERENCE")
