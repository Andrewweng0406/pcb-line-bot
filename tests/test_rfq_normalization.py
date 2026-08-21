from app.rfq_normalization import (
    normalize_copper_weight_oz,
    normalize_gold_thickness_uin,
    normalize_layer,
    normalize_material,
    normalize_surface_finish,
    normalized_quote_fields,
)


def test_material_normalization_preserves_known_variants():
    assert normalize_material("FR4") == "FR-4"
    assert normalize_material("fr 4") == "FR-4"
    assert normalize_material("FR-4") == "FR-4"
    assert normalize_material("Megtron6") == "MEGTRON 6"


def test_surface_finish_normalization():
    assert normalize_surface_finish("enig") == "ENIG"
    assert normalize_surface_finish("Electroless Nickel Immersion Gold") == "ENIG"
    assert normalize_surface_finish("Hard Gold") == "Hard Gold"


def test_layer_normalization_handles_text_and_bad_values():
    assert normalize_layer("6L") == 6
    assert normalize_layer("6-layer") == 6
    assert normalize_layer("unknown") is None


def test_copper_weight_normalization_is_conservative():
    assert normalize_copper_weight_oz("1oz") == 1.0
    assert normalize_copper_weight_oz("2 OZ") == 2.0
    assert normalize_copper_weight_oz("outer 1oz inner 0.5oz") is None
    assert normalize_copper_weight_oz("bad") is None


def test_gold_thickness_normalization_units():
    assert normalize_gold_thickness_uin(10, "uinch") == 10
    assert normalize_gold_thickness_uin(0.635, "um") == 25.0
    assert normalize_gold_thickness_uin("bad") is None


def test_normalized_quote_fields_derives_area_and_enig_finish():
    fields = normalized_quote_fields(
        {
            "layer": "6L",
            "length_mm": 100,
            "width_mm": 100,
            "enig": True,
            "enig_thickness_uinch": 5,
            "copper_weight": "1oz",
        },
        {},
    )
    assert fields["layer"] == 6
    assert fields["area_in2"] == 15.5
    assert fields["surface_finish"] == "ENIG"
    assert fields["gold_thickness_uin"] == 5
    assert fields["copper_weight_oz"] == 1.0
