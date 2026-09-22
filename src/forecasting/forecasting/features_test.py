import pandas as pd

from forecasting.consts import (
    CATEGORY_COLUMN,
    DATE_COLUMN,
    IS_WEEKEND_COLUMN,
    TARGET_COLUMN,
)
from forecasting.features import create_time_features


def test_is_weekend_flags_saturday_and_sunday() -> None:
    dates = pd.date_range("2026-01-01", periods=7, freq="D")
    frame = pd.DataFrame(
        {DATE_COLUMN: dates, CATEGORY_COLUMN: "Coffee", TARGET_COLUMN: 1}
    )

    featured = create_time_features(frame)

    flags = dict(
        zip(
            featured[DATE_COLUMN].dt.day_name(),
            featured[IS_WEEKEND_COLUMN],
            strict=True,
        )
    )
    assert flags["Saturday"] == 1
    assert flags["Sunday"] == 1
    for weekday in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday"):
        assert flags[weekday] == 0


# TODO: Improve the unit test coverage
