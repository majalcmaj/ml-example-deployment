import shutil
from pathlib import Path

import pytest
from forecasting.consts import METADATA_FILENAME, MODEL_FILENAME
from inference.config import Config
from inference.main import run
from stub_gateway import StubSalesGateway

MEMBER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = MEMBER_ROOT.parents[1]
BASELINE_DIR = Path(__file__).parent / "baseline"


@pytest.fixture(scope="session")
def run_root(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, StubSalesGateway]:
    root = tmp_path_factory.mktemp("inference-e2e")
    outputs = root / "outputs"
    outputs.mkdir()
    shutil.copy(BASELINE_DIR / MODEL_FILENAME, outputs / MODEL_FILENAME)
    shutil.copy(BASELINE_DIR / METADATA_FILENAME, outputs / METADATA_FILENAME)

    config = Config.model_validate({
        "source_endpoint_url": "https://example.invalid/api/recent-sales",
        "result_endpoint_url": "https://example.invalid/api/demand-forecast",
        "history_days": 60,
        "artifact_dir": outputs,
        "output_dir": outputs,
    })
    gateway = StubSalesGateway(REPO_ROOT / "data", history_days=60)
    run(config, gateway)
    return root, gateway
