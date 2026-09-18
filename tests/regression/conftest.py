from pathlib import Path

import pytest

from tests.regression import lib

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def training_run(repo_root: Path) -> None:
    lib.produce_training_artifacts(repo_root)
