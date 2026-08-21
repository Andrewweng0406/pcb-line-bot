"""Informational RFQ data quality scoring."""

from app.rfq_normalization import normalized_quote_fields


REQUIRED_FIELDS = ("layer", "qty", "size")
RECOMMENDED_FIELDS = (
    "material",
    "surface_finish",
    "copper_weight",
    "board_thickness",
    "delivery_days",
)

FIELD_LABELS = {
    "layer": "Layer",
    "qty": "Quantity",
    "size": "Board Size or Area",
    "material": "Material",
    "surface_finish": "Surface Finish",
    "copper_weight": "Copper Weight",
    "board_thickness": "Board Thickness",
    "delivery_days": "Delivery Days",
}


def _quote_to_spec(quote) -> dict:
    spec = dict(getattr(quote, "spec_json", None) or {})
    for attr in (
        "layer",
        "qty",
        "material",
        "length_mm",
        "width_mm",
        "area_in2",
        "board_thickness_mm",
        "copper_weight_oz",
        "surface_finish",
        "delivery_days",
    ):
        value = getattr(quote, attr, None)
        if value is not None:
            spec[attr] = value
    if spec.get("area_in2") is not None and spec.get("area_inch") is None:
        spec["area_inch"] = spec["area_in2"]
    return spec


def evaluate_rfq_completeness(rfq) -> dict:
    spec = _quote_to_spec(rfq) if not isinstance(rfq, dict) else dict(rfq)
    normalized = normalized_quote_fields(spec, {})

    required_missing = []
    if normalized.get("layer") is None:
        required_missing.append("layer")
    if spec.get("qty") is None:
        required_missing.append("qty")
    has_size = (
        normalized.get("area_in2") is not None
        or (spec.get("length_mm") is not None and spec.get("width_mm") is not None)
    )
    if not has_size:
        required_missing.append("size")

    recommended_missing = []
    if not normalized.get("material"):
        recommended_missing.append("material")
    if not normalized.get("surface_finish"):
        recommended_missing.append("surface_finish")
    if normalized.get("copper_weight_oz") is None:
        recommended_missing.append("copper_weight")
    if normalized.get("board_thickness_mm") is None:
        recommended_missing.append("board_thickness")
    if normalized.get("delivery_days") is None:
        recommended_missing.append("delivery_days")

    total_fields = len(REQUIRED_FIELDS) + len(RECOMMENDED_FIELDS)
    missing_count = len(required_missing) + len(recommended_missing)
    score = round(max(0, total_fields - missing_count) / total_fields, 2)

    return {
        "quotable": not required_missing,
        "required_missing": required_missing,
        "recommended_missing": recommended_missing,
        "completeness_score": score,
        "required_missing_labels": [FIELD_LABELS[f] for f in required_missing],
        "recommended_missing_labels": [FIELD_LABELS[f] for f in recommended_missing],
    }
