from types import SimpleNamespace
import pytest

from app.historical_intelligence import (
    find_similar_quotes,
    historical_pricing_summary,
    score_similarity,
    serialize_similar_quote,
    specification_differences,
    quote_profile,
)


def _quote(**kwargs):
    defaults = {
        "id": 1,
        "quote_no": "PCB-1",
        "layer": 6,
        "material": "FR4",
        "qty": 10,
        "length_mm": 100,
        "width_mm": 100,
        "area_in2": 15.5,
        "board_thickness_mm": 1.6,
        "copper_weight_oz": 1.0,
        "surface_finish": "ENIG",
        "gold_thickness_uin": 5,
        "delivery_days": 7,
        "total": 1000,
        "unit_price": 100,
        "quote_outcome": "pending",
        "estimated_margin_pct": None,
        "actual_margin_pct": None,
        "created_at": None,
        "spec_json": {"enig": True, "vip": False, "impedance": False, "back_drill": False, "bvh": False},
        "currency": "USD",
        "pricing_version": "v1",
        "final_price": None,
        "actual_cost": None,
        "breakdown_json": {},
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_identical_quotes_score_very_high():
    assert score_similarity(_quote(id=1), _quote(id=2)) >= 95


def test_unrelated_quotes_score_low():
    score = score_similarity(
        _quote(id=1),
        _quote(
            id=2,
            layer=20,
            material="MEGTRON 6",
            qty=100,
            length_mm=300,
            width_mm=200,
            area_in2=93,
            board_thickness_mm=5.0,
            copper_weight_oz=3.0,
            surface_finish="OSP",
            delivery_days=20,
            spec_json={},
        ),
    )
    assert score < 40


def test_similarity_handles_missing_values_and_stays_bounded():
    score = score_similarity(_quote(id=1), _quote(id=2, layer=None, material=None, spec_json={}))
    assert 0 <= score <= 100


def test_historical_summary_calculates_reference_stats():
    summary = historical_pricing_summary(
        [
            {"unit_price": 10, "quote_outcome": "won", "eligible": True, "currency": "USD", "pricing_version": "v1"},
            {"unit_price": 12, "quote_outcome": "lost", "eligible": True, "currency": "USD", "pricing_version": "v1"},
            {"unit_price": 14, "quote_outcome": "won", "eligible": True, "currency": "USD", "pricing_version": "v1"},
        ],
        min_sample_size=5,
    )
    assert summary["comparable_count"] == 3
    assert summary["limited_data"] is True
    assert "average_quoted_unit_price" not in summary
    assert summary["evidence"][0] == {"kind": "quoted", "count": 3, "available": False, "median": None}
    assert summary["won_count"] == 2
    assert summary["lost_count"] == 1
    assert summary["win_rate"] == 0.6667


def test_find_similar_quotes_orders_by_score(temp_db):
    temp_db.save_quote(
        "web:1",
        {"layer": 6, "material": "FR4", "qty": 10, "length_mm": 100, "width_mm": 100, "enig": True},
        {"status": "success", "total": 1000, "unit_price": 100},
    )
    temp_db.save_quote(
        "web:1",
        {"layer": 6, "material": "FR4", "qty": 10, "length_mm": 101, "width_mm": 100, "enig": True},
        {"status": "success", "total": 1010, "unit_price": 101},
    )
    temp_db.save_quote(
        "web:1",
        {"layer": 8, "material": "FR4", "qty": 50, "length_mm": 200, "width_mm": 150},
        {"status": "success", "total": 5000, "unit_price": 100},
    )

    db = temp_db.SessionLocal()
    target = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.asc()).first()
    matches = find_similar_quotes(db, temp_db.QuoteHistory, target, limit=2)
    db.close()

    assert len(matches) == 2
    assert matches[0]["similarity"] >= matches[1]["similarity"]
    assert matches[0]["quote_no"].startswith("PCB-")


@pytest.mark.parametrize("changes,reason", [
    ({"currency": None}, "missing_currency"),
    ({"currency": "NTD"}, "different_currency"),
    ({"pricing_version": "v2"}, "different_pricing_version"),
    ({"material": "MEGTRON6"}, "different_specification"),
    ({"qty": 21}, "scale_difference"),
    ({"qty": float("nan")}, "missing_specification"),
    ({"delivery_days": float("inf")}, "missing_specification"),
    ({"gold_thickness_uin": None}, "missing_specification"),
    ({"gold_thickness_uin": -1}, "missing_specification"),
    ({"board_thickness_mm": -1}, "missing_specification"),
    ({"spec_json": {"enig": True}}, "unknown_processes"),
])
def test_comparison_explains_exclusions(changes, reason):
    item = serialize_similar_quote(_quote(id=2, **changes), 100, _quote())
    assert not item["eligible"]
    assert reason in item["exclusions"]


def test_material_alias_and_false_process_values_are_comparable():
    item = serialize_similar_quote(_quote(id=2, material="FR-4"), 100, _quote())
    assert item["eligible"]
    assert all(row["state"] == "same" for row in item["differences"] if row["field"] != "gold_thickness_uin")


def test_difference_direction_and_unknown_values():
    rows = specification_differences(quote_profile(_quote()), quote_profile(_quote(qty=15, spec_json={})))
    assert next(row for row in rows if row["field"] == "qty")["delta_pct"] == 50
    assert next(row for row in rows if row["field"] == "vip")["state"] == "unknown"


def test_evidence_metrics_have_independent_sample_thresholds():
    items = [serialize_similar_quote(_quote(id=i + 2, quote_outcome="won" if i < 2 else "pending", final_price=900, actual_cost=0), 100, _quote()) for i in range(5)]
    summary = historical_pricing_summary(items)
    assert summary["median_quoted_unit_price"] == 100
    assert summary["evidence"][0]["available"]
    assert summary["evidence"][1]["count"] == 2
    assert summary["evidence"][2]["count"] == 2
    assert not summary["evidence"][1]["available"]
    assert items[0]["accepted_unit_price"] == 90
    assert items[0]["actual_unit_cost"] == 0
    assert items[2]["accepted_unit_price"] is None
    assert items[2]["actual_unit_cost"] is None


def test_summary_never_pools_currencies_or_nonfinite_prices():
    items = [serialize_similar_quote(_quote(id=i + 2, unit_price=float("inf")), 100, _quote()) for i in range(5)]
    assert historical_pricing_summary(items)["evidence"][0]["count"] == 0
    items[0]["currency"] = "NTD"
    assert historical_pricing_summary(items)["comparable_count"] == 0


def test_review_pending_excludes_reference():
    from app.extraction_review import build_extraction_review
    spec = dict(_quote().spec_json)
    spec.update({"layer": 6, "qty": 10, "material": "FR4"})
    spec["_extraction_review"] = build_extraction_review(spec, "6 layers FR4 10 pcs")
    item = serialize_similar_quote(_quote(id=2, spec_json=spec), 100, _quote())
    assert "review_pending" in item["exclusions"]
    assert not item["eligible"]


def test_candidate_query_discovers_normalized_material_aliases(temp_db):
    for material in ("FR4", "FR-4"):
        temp_db.save_quote("web:1", {"layer": 6, "material": material, "qty": 10}, {"status": "success", "total": 1000})
    with temp_db.SessionLocal() as session:
        target = session.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id).first()
        matches = find_similar_quotes(session, temp_db.QuoteHistory, target)
        assert len(matches) == 1
        assert next(row for row in matches[0]["differences"] if row["field"] == "material")["state"] == "same"


def test_revisions_do_not_count_as_independent_references(temp_db):
    for _ in range(4):
        temp_db.save_quote("web:1", {"layer": 6, "material": "FR4", "qty": 10}, {"status": "success", "total": 1000})
    with temp_db.SessionLocal() as session:
        quotes = session.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id).all()
        # Two candidates belong to the target family, one is independent.
        for child, parent in ((quotes[1], quotes[0]), (quotes[2], quotes[1])):
            child.spec_json = {**child.spec_json, "_extraction_review": {"revision_of": parent.id, "fields": [], "summary": {}}}
        session.commit()
        matches = find_similar_quotes(session, temp_db.QuoteHistory, quotes[0])
        assert sum("related_revision" in item["exclusions"] for item in matches) == 2
