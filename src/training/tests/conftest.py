import shutil
from pathlib import Path

import pytest
from testkit.notebooks import run_notebook

MEMBER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = MEMBER_ROOT.parents[1]
NOTEBOOK_PATH = MEMBER_ROOT / "training" / "daily_product_demand_forecast.ipynb"


@pytest.fixture(scope="session")
def run_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("training-e2e")
    shutil.copytree(REPO_ROOT / "data", root / "data")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("TRAINING_DATA_DIR", str(root / "data"))
    monkeypatch.setenv("TRAINING_OUTPUT_DIR", str(root / "outputs"))
    try:
        run_notebook(NOTEBOOK_PATH, cwd=root)
    finally:
        monkeypatch.undo()

    return root
