import math

from app.extraction_review import release_pending
from app.rfq_completeness import evaluate_rfq_completeness
from app.rfq_normalization import normalized_quote_fields


def _positive(value):
    try:
        return not isinstance(value, bool) and math.isfinite(float(value)) and float(value) > 0
    except (TypeError, ValueError, OverflowError):
        return False


def customer_export_readiness(quote):
    """Evaluate saved evidence without recalculating or modifying historical prices."""
    spec = quote.spec_json if isinstance(quote.spec_json, dict) else {}
    result = quote.breakdown_json if isinstance(quote.breakdown_json, dict) else {}
    shared = []
    if release_pending(spec):
        shared.append({"code": "export_pending_review", "fields": []})
    amounts_valid = result.get("status") == "success"
    for field in ("total", "unit_price"):
        saved, calculated = getattr(quote, field, None), result.get(field)
        try:
            amounts_valid = amounts_valid and all(
                not isinstance(value, bool) and math.isfinite(float(value)) and float(value) >= 0
                for value in (saved, calculated)
            ) and math.isclose(float(saved), float(calculated), rel_tol=0, abs_tol=0.000001)
        except (TypeError, ValueError, OverflowError):
            amounts_valid = False
    if not amounts_valid:
        shared.append({"code": "export_invalid_calculation", "fields": []})
    currency = (quote.currency or "").strip()
    if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
        shared.append({"code": "export_unknown_currency", "fields": []})

    completeness = evaluate_rfq_completeness(spec)
    missing = list(completeness["required_missing_labels"] + completeness["recommended_missing_labels"])
    normalized = normalized_quote_fields(spec)
    core_missing = [label for label, value in (
        ("Layer", normalized.get("layer")), ("Quantity", spec.get("qty")),
        ("Board Size or Area", normalized.get("area_in2")),
    ) if not _positive(value)]
    if core_missing:
        shared.append({"code": "export_missing_specs", "fields": core_missing})
    for label, value in (
        ("Layer", normalized.get("layer")), ("Quantity", spec.get("qty")),
        ("Board Size or Area", normalized.get("area_in2")),
        ("Board Thickness", normalized.get("board_thickness_mm")),
        ("Delivery Days", normalized.get("delivery_days")),
        ("Pitch", spec.get("pitch_mm")),
    ):
        if not _positive(value):
            missing.append(label)
    split_copper = all(_positive(spec.get(field)) for field in ("copper_outer_oz", "copper_inner_oz"))
    if split_copper:
        missing = [label for label in missing if label != "Copper Weight"]
    elif not _positive(normalized.get("copper_weight_oz")):
        missing.append("Copper Weight")
    if normalized.get("surface_finish") in {"ENIG", "Hard Gold"} and not _positive(normalized.get("gold_thickness_uin")):
        missing.append("Gold Thickness")
    if normalized.get("surface_finish") not in {"ENIG", "Hard Gold", "HASL", "OSP"}:
        missing.append("Surface Finish")
    finish = normalized.get("surface_finish")
    process_conflict = (
        (finish == "ENIG" and (not spec.get("enig") or spec.get("hard_gold")))
        or (finish == "Hard Gold" and not spec.get("hard_gold"))
        or (finish not in {"ENIG", "Hard Gold"} and (spec.get("enig") or spec.get("hard_gold")))
    )
    formal = list(shared)
    missing = [label for label in dict.fromkeys(missing) if label not in core_missing]
    if missing:
        formal.append({"code": "export_missing_specs", "fields": missing})
    if process_conflict:
        formal.append({"code": "export_process_conflict", "fields": []})
    pricing = result.get("pricing_review")
    if not isinstance(pricing, dict) or pricing.get("status") not in {"quotable", "estimate", "needs_review"}:
        formal.append({"code": "export_missing_pricing_review", "fields": []})
    elif (pricing["status"] != "quotable" or pricing.get("critical_missing") != []
          or pricing.get("unpriced_factors") != []):
        formal.append({"code": "export_pricing_not_ready", "fields": []})
    if quote.status not in {"approved", "ordered"}:
        formal.append({"code": "export_approval_required", "fields": []})
    return {
        "estimate_ready": not shared,
        "formal_ready": not formal,
        "estimate_blockers": shared,
        "formal_blockers": formal,
    }


def validate_status_transition(quote, status):
    if status not in {"pending", "approved", "ordered"}:
        raise ValueError("Invalid quote status")
    if status != quote.status and status in {"approved", "ordered"} and release_pending(quote.spec_json):
        raise PermissionError("Confirm the pending extraction fields before approving this quote.")
