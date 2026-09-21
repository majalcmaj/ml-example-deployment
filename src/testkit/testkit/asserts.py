import pandas as pd

PREDICTION_ATOL = 1  # rounded-quantity jitter
METRIC_RTOL = 1e-3  # MAE/RMSE/WMAPE
BOUND_RTOL = 1e-6  # IQR bounds from static data — near-exact, tolerance absorbs float summation order


def assert_columns_equal(actual_df: pd.DataFrame, expected_df: pd.DataFrame) -> None:
    assert list(actual_df.columns) == list(expected_df.columns)


def assert_frame_within_tolerance(
    actual_df: pd.DataFrame,
    expected_df: pd.DataFrame,
    *,
    rtol: float = 1e-5,
    atol: float = 1e-8,
) -> None:
    pd.testing.assert_frame_equal(
        actual_df.reset_index(drop=True),
        expected_df.reset_index(drop=True),
        check_exact=False,
        rtol=rtol,
        atol=atol,
    )


def assert_mapping_equal(actual: object, expected: object) -> None:
    assert actual == expected
