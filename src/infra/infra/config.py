import os
import tomllib
from pathlib import Path

from pydantic import BaseModel


def find_project_root(start: Path | None = None) -> Path:
    current = start or Path.cwd()
    for candidate in (current, *current.parents):
        if (candidate / "uv.lock").exists():
            return candidate
    return current


def load_config[T: BaseModel](model: type[T], path: Path, *, env_prefix: str) -> T:
    override_var = f"{env_prefix}_CONFIG_FILE"
    override = os.environ.get(override_var)
    if override is not None:
        path = Path(override)
        if not path.exists():
            raise FileNotFoundError(f"{override_var} points at a missing file: {path}")

    with path.open("rb") as f:
        raw = tomllib.load(f)

    for name in model.model_fields:
        env_value = os.environ.get(f"{env_prefix}_{name.upper()}")
        if env_value is not None:
            raw[name] = env_value

    project_root = find_project_root()
    for name, field in model.model_fields.items():
        if field.annotation is Path and name in raw:
            value = Path(raw[name])
            if not value.is_absolute():
                raw[name] = project_root / value

    return model(**raw)
