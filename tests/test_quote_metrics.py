from app.quote_metrics import (
    calculate_margin,
    calculate_price_per_unit,
    to_non_negative_float,
    to_non_negative_int,
)


def test_margin_calculation_uses_decimal_fraction():
    assert calculate_margin(100, 75) == 0.25
    assert calculate_margin("100", "80") == 0.2


def test_margin_handles_null_zero_and_invalid_values():
    assert calculate_margin(None, 75) is None
    assert calculate_margin(0, 75) is None
    assert calculate_margin("bad", 75) is None


def test_price_per_unit_is_null_safe():
    assert calculate_price_per_unit(100, 4) == 25.0
    assert calculate_price_per_unit(100, 0) is None
    assert calculate_price_per_unit(None, 4) is None


def test_non_negative_parsers_reject_bad_values():
    assert to_non_negative_float("1.5") == 1.5
    assert to_non_negative_float("-1") is None
    assert to_non_negative_float("bad") is None
    assert to_non_negative_int("3") == 3
    assert to_non_negative_int("-3") is None
    assert to_non_negative_int("bad") is None


def test_numeric_parsers_reject_non_finite_booleans_and_fractional_counts():
    for value in (True, False, float("nan"), float("inf"), "NaN", "Infinity"):
        assert to_non_negative_float(value) is None
        assert to_non_negative_int(value) is None
    assert to_non_negative_int(1.5) is None
    assert to_non_negative_int(2.0) == 2
