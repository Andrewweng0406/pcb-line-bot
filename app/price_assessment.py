"""Explainable price review based on independent historical quoted prices."""

from datetime import datetime, timezone
from statistics import median

from app.historical_intelligence import eligible_reference_quotes, finite_number, quote_profile


MINIMUM_REFERENCES = 5
MINIMUM_DEVIATION = 0.20
MAD_MULTIPLIER = 3 * 1.4826
CONTEXT_FIELDS = ("area_in2", "qty", "delivery_days")


def _timestamp(value):
    try:
        stamp = value if isinstance(value, datetime) else datetime.fromisoformat(value)
        return stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def assess_quote_price(quote, candidates: list[dict]) -> dict:
    profile = quote_profile(quote)
    current = profile["unit_price"]
    if getattr(quote, "unit_price", None) is None and profile["total"] is not None and profile["qty"] and profile["qty"] > 0:
        current = finite_number(profile["total"] / profile["qty"])
    as_of = _timestamp(profile["created_at"])
    result = {
        "rule_version": "median-mad-v1",
        "status": "insufficient_evidence",
        "currency": profile["currency"],
        "current_unit_price": current,
        "minimum_references": MINIMUM_REFERENCES,
        "reference_count": 0,
        "as_of": as_of.isoformat() if as_of else None,
        "median_unit_price": None,
        "mad": None,
        "lower_bound": None,
        "upper_bound": None,
        "deviation_pct": None,
        "references": [],
        "exclusions": [],
        "context_fields": [],
    }
    for item in candidates:
        reasons = list(item.get("exclusions", []))
        if not item.get("eligible") and not reasons:
            reasons.append("ineligible_reference")
        if not item.get("currency") or not profile["currency"]:
            reasons.append("missing_currency")
        elif item.get("currency") != profile["currency"]:
            reasons.append("different_currency")
        if not item.get("pricing_version") or not profile["pricing_version"]:
            reasons.append("missing_pricing_version")
        elif item.get("pricing_version") != profile["pricing_version"]:
            reasons.append("different_pricing_version")
        stamp = _timestamp(item.get("created_at"))
        if stamp is None:
            reasons.append("missing_reference_date")
        elif as_of is not None and (
            stamp > as_of or (stamp == as_of and item["id"] >= quote.id)
        ):
            reasons.append("not_historical")
        price = finite_number(item.get("unit_price"))
        if price is None or price <= 0:
            reasons.append("invalid_reference_price")
        if reasons:
            result["exclusions"].append({"id": item["id"], "quote_no": item["quote_no"], "reasons": list(dict.fromkeys(reasons))})
            continue
        result["references"].append({
            "id": item["id"], "quote_no": item["quote_no"], "unit_price": price,
            "currency": item["currency"], "created_at": item["created_at"],
            "differences": [row for row in item.get("differences", []) if row["field"] in CONTEXT_FIELDS and row["state"] != "same"],
        })

    # The same eligibility checks used for benchmark summaries remain mandatory.
    eligible = eligible_reference_quotes([
        item for item in candidates if item.get("currency") == profile["currency"]
        and item.get("pricing_version") == profile["pricing_version"]
    ])
    eligible_ids = {item["id"] for item in eligible}
    result["references"] = [item for item in result["references"] if item["id"] in eligible_ids]
    result["reference_count"] = len(result["references"])
    result["context_fields"] = [field for field in CONTEXT_FIELDS if any(
        row["field"] == field for item in result["references"] for row in item["differences"]
    )]
    if profile["review_pending"]:
        result["status"] = "review_pending"
        return result
    if current is None or current <= 0:
        result["status"] = "invalid_current_price"
        return result
    if as_of is None:
        result["status"] = "missing_quote_date"
        return result
    if len(result["references"]) < MINIMUM_REFERENCES:
        return result

    prices = [item["unit_price"] for item in result["references"]]
    center = finite_number(median(prices))
    if center is None or center <= 0:
        return result
    mad = finite_number(median([abs(price - center) for price in prices]))
    if mad is None:
        return result
    width = finite_number(max(center * MINIMUM_DEVIATION, MAD_MULTIPLIER * mad))
    upper = finite_number(center + width) if width is not None else None
    deviation = finite_number((current / center - 1) * 100)
    if upper is None or deviation is None:
        return result
    lower = max(0, center - width)
    result.update({
        "median_unit_price": round(center, 2), "mad": round(mad, 2),
        "lower_bound": round(lower, 2), "upper_bound": round(upper, 2),
        "deviation_pct": round(deviation, 1),
        "status": "above_band" if current > upper else "below_band" if current < lower else "within_band",
    })
    return result
