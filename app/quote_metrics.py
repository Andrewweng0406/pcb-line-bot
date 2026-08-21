"""Null-safe quote metric helpers.

Margin values are stored as decimal fractions: 0.25 means 25%.
"""

from typing import Optional


def to_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_non_negative_float(value) -> Optional[float]:
    number = to_float(value)
    if number is None or number < 0:
        return None
    return number


def to_non_negative_int(value) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return number


def calculate_margin(revenue, cost) -> Optional[float]:
    revenue_value = to_float(revenue)
    cost_value = to_float(cost)
    if revenue_value is None or cost_value is None or revenue_value <= 0:
        return None
    return round((revenue_value - cost_value) / revenue_value, 4)


def calculate_price_per_unit(total, qty) -> Optional[float]:
    total_value = to_float(total)
    qty_value = to_float(qty)
    if total_value is None or qty_value is None or qty_value <= 0:
        return None
    return round(total_value / qty_value, 2)
