from typing import TYPE_CHECKING

from forecasting.consts import METADATA_FILENAME, MODEL_FILENAME

if TYPE_CHECKING:
    from pathlib import Path


def verify_artifacts_present(artifact_dir: Path) -> None:
    """Fail fast on missing model/metadata artifacts, before any network call or
    feature reconstruction runs."""
    if not artifact_dir.exists():
        raise FileNotFoundError(
            "Could not find outputs/. Run training or deploy the model artifacts first."
        )

    missing = [
        filename
        for filename in (METADATA_FILENAME, MODEL_FILENAME)
        if not (artifact_dir / filename).exists()
    ]
    if missing:
        raise FileNotFoundError(
            f"Missing required artifact(s) in {artifact_dir}: {', '.join(missing)}."
        )
