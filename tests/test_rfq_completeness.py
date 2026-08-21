from app.rfq_completeness import evaluate_rfq_completeness
from types import SimpleNamespace


def test_completeness_complete_case():
    result = evaluate_rfq_completeness(
        {
            "layer": 6,
            "qty": 2,
            "length_mm": 100,
            "width_mm": 100,
            "material": "FR4",
            "surface_finish": "ENIG",
            "copper_weight": "1oz",
            "thickness_mm": 1.6,
            "delivery_days": 7,
        }
    )
    assert result["quotable"] is True
    assert result["required_missing"] == []
    assert result["recommended_missing"] == []
    assert result["completeness_score"] == 1.0


def test_completeness_separates_required_and_recommended_missing():
    result = evaluate_rfq_completeness({"layer": 6, "qty": 1, "area_inch": 12})
    assert result["quotable"] is True
    assert result["required_missing"] == []
    assert "surface_finish" in result["recommended_missing"]
    assert "copper_weight" in result["recommended_missing"]


def test_completeness_legacy_null_heavy_record_is_not_quotable_but_safe():
    result = evaluate_rfq_completeness({})
    assert result["quotable"] is False
    assert "layer" in result["required_missing"]
    assert "qty" in result["required_missing"]
    assert 0 <= result["completeness_score"] <= 1


def test_completeness_reads_persisted_v2_quote_fields():
    quote = SimpleNamespace(
        spec_json={},
        layer=6,
        qty=1,
        length_mm=100,
        width_mm=100,
        material="FR4",
        area_in2=15.5,
        board_thickness_mm=1.6,
        copper_weight_oz=1.0,
        surface_finish="ENIG",
        delivery_days=7,
    )
    result = evaluate_rfq_completeness(quote)
    assert result["quotable"] is True
    assert result["recommended_missing"] == []
