import pandas as pd
import pytest

from forecasting.preprocessing import (
    aggregate_per_category,
    columns_to_expected_types,
    get_valid_date_target_array,
    validate_required_columns_present,
)


def test_columns_to_expected_types_does_not_mutate_input_frame() -> None:
    original = pd.DataFrame(
        {
            "Date": ["2026-01-01"],
            "Menu": [" Coffee  Latte "],
            "Total_Qty": ["3"],
        }
    )
    before = original.copy()

    columns_to_expected_types(original)

    pd.testing.assert_frame_equal(original, before)


def test_columns_to_expected_types_returns_normalized_frame() -> None:
    original = pd.DataFrame(
        {
            "Date": ["2026-01-01"],
            "Menu": [" Coffee  Latte "],
            "Total_Qty": ["3"],
        }
    )

    result = columns_to_expected_types(original)

    assert result["Menu"].iloc[0] == "Coffee Latte"
    assert result["Total_Qty"].iloc[0] == 3
    assert pd.api.types.is_datetime64_any_dtype(result["Date"])


def test_validate_required_columns_present_raises_for_missing_column() -> None:
    sales = pd.DataFrame({"Date": ["2026-01-01"], "Menu": ["Coffee"]})

    with pytest.raises(ValueError, match="missing columns"):
        validate_required_columns_present(sales)


def test_validate_required_columns_present_passes_for_complete_frame() -> None:
    sales = pd.DataFrame(
        {"Date": ["2026-01-01"], "Menu": ["Coffee"], "Total_Qty": [3]}
    )

    validate_required_columns_present(sales)


def test_get_valid_date_target_array_flags_negative_and_missing_values() -> None:
    sales = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-01-01", None, "2026-01-03"]),
            "Total_Qty": [3, 5, -1],
        }
    )

    valid = get_valid_date_target_array(sales)

    assert list(valid) == [True, False, False]


def test_aggregate_per_category_zero_fills_missing_combinations() -> None:
    daily_sales = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-01-01"]),
            "Menu": ["Coffee"],
            "Total_Qty": [3],
        }
    )
    complete_index = pd.MultiIndex.from_product(
        [pd.date_range("2026-01-01", periods=2, freq="D"), ["Coffee", "Tea"]],
        names=["Date", "Menu"],
    )

    result = aggregate_per_category(complete_index, daily_sales)

    assert len(result) == 4
    assert result["Total_Qty"].sum() == 3
