"""Diffs the Compose stack's forecast output against the inference baseline.

Split out of scripts/compose_smoke.sh so the check is real, lintable/typed Python
rather than an inline `python3 -c "..."` block in bash.
"""

import pandas as pd
from forecasting.consts import PREDICTED_QTY_COLUMN
from testkit.asserts import (
    PREDICTION_ATOL,
    assert_columns_equal,
    assert_frame_within_tolerance,
)

ACTUAL_PATH = "outputs/inference_next_day_forecast.csv"
EXPECTED_PATH = "src/inference/tests/baseline/inference_next_day_forecast.csv"


def main() -> None:
    actual = pd.read_csv(ACTUAL_PATH)
    expected = pd.read_csv(EXPECTED_PATH)

    assert_columns_equal(actual, expected)
    assert_frame_within_tolerance(
        actual.loc[:, [PREDICTED_QTY_COLUMN]],
        expected.loc[:, [PREDICTED_QTY_COLUMN]],
        atol=PREDICTION_ATOL,
    )
    print("compose smoke: predictions within tolerance")


if __name__ == "__main__":
    main()
