from pathlib import Path

from infra.config import load_config
from pydantic import BaseModel, ConfigDict


class Config(BaseModel):
    data_dir: Path
    output_dir: Path
    validation_days: int
    model_config = ConfigDict(frozen=True)


CONFIG = load_config(Config, Path(__file__).parent / "config.toml", env_prefix="TRAINING")
