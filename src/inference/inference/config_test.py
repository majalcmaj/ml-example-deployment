from inference.config import CONFIG


def test_config_validation() -> None:
    assert CONFIG.simulation_mode is True
    assert CONFIG.history_days == 60
