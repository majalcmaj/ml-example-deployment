import shutil
from pathlib import Path

import pytest
from testkit.runner import run_script

MEMBER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = MEMBER_ROOT.parents[1]
SCRIPT_PATH = MEMBER_ROOT / "inference" / "daily_product_demand_inference.py"
BASELINE_DIR = Path(__file__).parent / "baseline"


@pytest.fixture(scope="session")
def run_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("inference-e2e")
    shutil.copytree(REPO_ROOT / "data", root / "data")

    outputs = root / "outputs"
    outputs.mkdir()
    shutil.copy(
        BASELINE_DIR / "xgb_daily_product_demand.json",
        outputs / "xgb_daily_product_demand.json",
    )
    shutil.copy(
        BASELINE_DIR / "forecast_metadata.joblib", outputs / "forecast_metadata.joblib"
    )

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("INFERENCE_DATA_DIR", str(root / "data"))
    monkeypatch.setenv("INFERENCE_ARTIFACT_DIR", str(outputs))
    monkeypatch.setenv("INFERENCE_OUTPUT_DIR", str(outputs))
    try:
        run_script(SCRIPT_PATH, cwd=root)
    finally:
        monkeypatch.undo()

    return root
