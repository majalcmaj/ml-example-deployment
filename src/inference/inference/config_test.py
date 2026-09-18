from pathlib import Path

import pytest


def test_config_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    # config.py's module-level parse reads a cwd-relative "config.toml", so the import
    # itself must happen with cwd set to the package dir (fixed properly in phase03/04).
    monkeypatch.chdir(Path(__file__).parent)
    from inference.config import CONFIG

    assert CONFIG.simulation_mode is True
    assert CONFIG.history_days == 60
