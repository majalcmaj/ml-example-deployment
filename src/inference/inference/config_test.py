from inference.config import CONFIG


def test_config_validation() -> None:
    assert CONFIG.simulation_mode is True
    assert CONFIG.history_days == 60


def test_artifact_dir_points_at_outputs() -> None:
    # The e2e suite always overrides INFERENCE_ARTIFACT_DIR for hermetic runs, so it can't catch
    # a bad config.toml default; this guards the checked-in value directly.
    assert CONFIG.artifact_dir.name == "outputs"
