import os
from pathlib import Path

import pytest
from pydantic import BaseModel

from common.config import find_project_root, load_config


class _Model(BaseModel):
    data_dir: Path
    simulation_mode: bool


def _write_toml(path: Path) -> None:
    path.write_text('data_dir = "data"\nsimulation_mode = true\n')


def test_load_config_from_toml(tmp_path: Path) -> None:
    toml_path = tmp_path / "config.toml"
    _write_toml(toml_path)
    model = load_config(_Model, toml_path, env_prefix="X")
    assert model.simulation_mode is True


def test_load_config_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    toml_path = tmp_path / "config.toml"
    _write_toml(toml_path)
    monkeypatch.setenv("X_DATA_DIR", "/tmp/elsewhere")
    model = load_config(_Model, toml_path, env_prefix="X")
    assert model.data_dir == Path("/tmp/elsewhere")


def test_load_config_relative_path_resolves_against_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "uv.lock").touch()
    nested = tmp_path / "pkg"
    nested.mkdir()
    toml_path = nested / "config.toml"
    _write_toml(toml_path)
    model = load_config(_Model, toml_path, env_prefix="X")
    assert model.data_dir == tmp_path / "data"


def test_find_project_root_walks_up_to_uv_lock(tmp_path: Path) -> None:
    (tmp_path / "uv.lock").touch()
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert find_project_root(nested) == tmp_path


def test_find_project_root_falls_back_to_start(tmp_path: Path) -> None:
    isolated = tmp_path / "no-lock-anywhere-above"
    isolated.mkdir()
    assert find_project_root(isolated) == isolated
