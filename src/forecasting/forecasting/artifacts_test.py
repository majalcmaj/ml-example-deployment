from typing import TYPE_CHECKING

import pytest

from forecasting.artifacts import verify_artifacts_present
from forecasting.consts import METADATA_FILENAME, MODEL_FILENAME

if TYPE_CHECKING:
    from pathlib import Path


def test_verify_artifacts_present_raises_when_artifact_dir_missing(tmp_path: Path) -> None:
    missing_dir = tmp_path / "outputs"

    with pytest.raises(FileNotFoundError, match="Run training or deploy"):
        verify_artifacts_present(missing_dir)


def test_verify_artifacts_present_raises_when_model_file_missing(tmp_path: Path) -> None:
    (tmp_path / METADATA_FILENAME).write_bytes(b"")

    with pytest.raises(FileNotFoundError, match=MODEL_FILENAME):
        verify_artifacts_present(tmp_path)


def test_verify_artifacts_present_raises_when_metadata_file_missing(tmp_path: Path) -> None:
    (tmp_path / MODEL_FILENAME).write_bytes(b"")

    with pytest.raises(FileNotFoundError, match=METADATA_FILENAME):
        verify_artifacts_present(tmp_path)


def test_verify_artifacts_present_passes_when_both_files_exist(tmp_path: Path) -> None:
    (tmp_path / METADATA_FILENAME).write_bytes(b"")
    (tmp_path / MODEL_FILENAME).write_bytes(b"")

    verify_artifacts_present(tmp_path)
