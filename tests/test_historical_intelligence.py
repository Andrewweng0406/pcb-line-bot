from types import SimpleNamespace

from app.historical_intelligence import (
    find_similar_quotes,
    historical_pricing_summary,
    score_similarity,
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
        "delivery_days": 7,
        "total": 1000,
        "unit_price": 100,
        "quote_outcome": "pending",
        "estimated_margin_pct": None,
        "actual_margin_pct": None,
        "created_at": None,
        "spec_json": {"enig": True},
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
            {"unit_price": 10, "quote_outcome": "won"},
            {"unit_price": 12, "quote_outcome": "lost"},
            {"unit_price": 14, "quote_outcome": "won"},
        ],
        min_sample_size=5,
    )
    assert summary["comparable_count"] == 3
    assert summary["limited_data"] is True
    assert summary["average_quoted_unit_price"] == 12
    assert summary["median_quoted_unit_price"] == 12
    assert summary["lowest_quoted_unit_price"] == 10
    assert summary["highest_quoted_unit_price"] == 14
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
