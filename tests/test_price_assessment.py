from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.historical_intelligence import serialize_similar_quote
from app.price_assessment import assess_quote_price


def quote(**changes):
    values = dict(
        id=100, quote_no="CURRENT", created_at=datetime(2026, 10, 3),
        layer=6, material="FR4", qty=10, area_in2=15.5,
        board_thickness_mm=1.6, copper_weight_oz=1, surface_finish="ENIG",
        gold_thickness_uin=5, delivery_days=7, total=1000, unit_price=100,
        currency="NTD", pricing_version="v1", quote_outcome="pending",
        spec_json={"enig": True, "vip": False, "impedance": False, "back_drill": False, "bvh": False},
        breakdown_json={},
    )
    values.update(changes)
    return SimpleNamespace(**values)


def references(target, prices=(96, 98, 100, 102, 104), **changes):
    return [serialize_similar_quote(quote(
        **{**dict(id=i+1, quote_no=f"REF-{i+1}", unit_price=price,
                  created_at=target.created_at-timedelta(days=i+1)), **changes}
    ), 100, target) for i, price in enumerate(prices)]


@pytest.mark.parametrize("price,status,deviation", [(100, "within_band", 0), (140, "above_band", 40), (60, "below_band", -40), (80, "within_band", -20), (120, "within_band", 20)])
def test_price_band_and_direction(price, status, deviation):
    target = quote(unit_price=price)
    result = assess_quote_price(target, references(target))
    assert result["status"] == status
    assert result["median_unit_price"] == 100
    assert result["mad"] == 2
    assert result["lower_bound"] == 80
    assert result["upper_bound"] == 120
    assert result["deviation_pct"] == deviation
    assert result["reference_count"] == 5
    assert len(result["references"]) == 5


def test_single_outlier_and_zero_mad_keep_stable_band():
    target = quote(unit_price=140)
    result = assess_quote_price(target, references(target, (100, 100, 100, 100, 10000)))
    assert result["status"] == "above_band"
    assert result["mad"] == 0
    assert result["upper_bound"] == 120


def test_variable_history_widens_band():
    target = quote(unit_price=180)
    result = assess_quote_price(target, references(target, (50, 75, 100, 125, 150)))
    assert result["status"] == "within_band"
    assert result["upper_bound"] == 211.19


def test_insufficient_history_has_no_price_judgment():
    target = quote(unit_price=10000)
    result = assess_quote_price(target, references(target, (98, 100, 102, 104)))
    assert result["status"] == "insufficient_evidence"
    assert result["reference_count"] == 4
    assert result["median_unit_price"] is None
    assert result["deviation_pct"] is None


def test_future_and_undated_quotes_are_explained_and_excluded():
    target = quote()
    items = references(target)
    items[0]["created_at"] = (target.created_at+timedelta(days=1)).isoformat()
    items[1]["created_at"] = None
    result = assess_quote_price(target, items)
    assert result["reference_count"] == 3
    assert result["status"] == "insufficient_evidence"
    assert "not_historical" in result["exclusions"][0]["reasons"]
    assert "missing_reference_date" in result["exclusions"][1]["reasons"]


@pytest.mark.parametrize("price", [0, -1, float("nan"), float("inf")])
def test_invalid_current_price_never_produces_a_band(price):
    target = quote(unit_price=price)
    result = assess_quote_price(target, references(target))
    assert result["status"] == "invalid_current_price"
    assert result["upper_bound"] is None


def test_bad_reference_prices_and_wrong_currency_never_enter_basis():
    target = quote()
    items = references(target)
    items[0]["unit_price"] = float("inf")
    items[1]["currency"] = "USD"
    result = assess_quote_price(target, items)
    assert result["reference_count"] == 3
    assert "invalid_reference_price" in result["exclusions"][0]["reasons"]
    assert "different_currency" in result["exclusions"][1]["reasons"]


def test_specification_context_is_traceable_without_causal_claim():
    target = quote()
    result = assess_quote_price(target, references(target, qty=15, area_in2=20))
    assert result["context_fields"] == ["area_in2", "qty"]
    assert all(len(item["differences"]) == 2 for item in result["references"])


def test_pending_extraction_review_defers_assessment():
    from app.extraction_review import build_extraction_review
    target = quote()
    spec = {**target.spec_json, "layer": 6, "qty": 10}
    spec["_extraction_review"] = build_extraction_review(spec, "6 layers, 10 pcs")
    target.spec_json = spec
    result = assess_quote_price(target, references(target))
    assert result["status"] == "review_pending"
    assert result["upper_bound"] is None


def test_missing_date_and_timezone_consistency():
    target = quote()
    items = references(target)
    target.created_at = None
    assert assess_quote_price(target, items)["status"] == "missing_quote_date"
    target.created_at = datetime(2026, 10, 3, tzinfo=timezone.utc)
    assert assess_quote_price(target, items)["status"] == "within_band"


def test_accepted_prices_and_costs_do_not_change_quoted_price_band():
    target = quote(unit_price=140)
    items = references(target, quote_outcome="won", final_price=99999, actual_cost=99998)
    result = assess_quote_price(target, items)
    assert result["status"] == "above_band"
    assert result["median_unit_price"] == 100
    assert result["upper_bound"] == 120


def test_ineligible_revision_and_newer_equal_timestamp_are_excluded():
    target = quote()
    items = references(target)
    items[0]["eligible"] = False
    items[0]["exclusions"] = ["related_revision"]
    items[1]["created_at"] = target.created_at.isoformat()
    items[1]["id"] = target.id + 1
    result = assess_quote_price(target, items)
    assert result["status"] == "insufficient_evidence"
    assert result["reference_count"] == 3
    assert "related_revision" in result["exclusions"][0]["reasons"]
    assert "not_historical" in result["exclusions"][1]["reasons"]
