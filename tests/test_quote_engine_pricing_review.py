from app.quote_engine import calculate_quote


def _base_spec(**overrides):
    spec = {
        "layer": 6,
        "qty": 3,
        "length_mm": 100,
        "width_mm": 100,
        "material": "FR4",
        "thickness_mm": 1.6,
        "pitch_mm": 0.6,
        "delivery_days": 7,
    }
    spec.update(overrides)
    return spec


def test_quantity_does_not_create_reorder_discount_by_itself():
    result = calculate_quote(_base_spec(qty=3))

    assert result["status"] == "success"
    assert result["discount"] == 1.0


def test_reorder_flag_applies_discount():
    result = calculate_quote(_base_spec(qty=3, is_reorder=True))

    assert result["status"] == "success"
    assert result["discount"] == 0.9
    assert "Re-order discount" in " ".join(result["pricing_review"]["applied_factors"])


def test_extended_specs_apply_pricing_factors_and_review_status():
    result = calculate_quote(
        _base_spec(
            line_space_mil=3,
            min_hole_mil=7,
            copper_outer_oz=2,
            copper_inner_oz=1,
            warpage_mil_per_inch=2,
            countersunk=True,
            counterbored=True,
            inspection_report_required=True,
        )
    )

    assert result["status"] == "success"
    assert result["specification_multiplier"] > 1
    assert result["extra_fee"] == 6000
    assert result["pricing_review"]["status"] == "needs_review"
    applied = " ".join(result["pricing_review"]["applied_factors"])
    assert "Line/Space" in applied
    assert "最小孔徑" in applied
    assert "銅厚" in applied
    assert "板翹" in applied
    assert "Countersunk" in applied
    assert result["pricing_review"]["unpriced_factors"] == [
        "Inspection report requested; confirm whether to charge separately."
    ]


def test_hard_gold_is_priced_separately_from_enig():
    hard_gold = calculate_quote(
        _base_spec(enig=True, hard_gold=True, surface_finish="Hard Gold", enig_thickness_uinch=20)
    )
    enig = calculate_quote(_base_spec(enig=True, enig_thickness_uinch=20))

    assert hard_gold["status"] == "success"
    assert enig["status"] == "success"
    assert hard_gold["extra_fee"] > enig["extra_fee"]
    assert "Hard Gold" in " ".join(hard_gold["pricing_review"]["applied_factors"])


def test_missing_delivery_marks_quote_as_estimate():
    result = calculate_quote(_base_spec(delivery_days=None))

    assert result["status"] == "success"
    assert result["pricing_review"]["status"] == "estimate"
    assert "交期" in result["pricing_review"]["critical_missing"]
