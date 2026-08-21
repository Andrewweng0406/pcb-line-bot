"""Explainable historical RFQ similarity and pricing summaries."""

from statistics import median
from typing import Iterable, Optional

from app.quote_metrics import calculate_price_per_unit, to_float
from app.rfq_normalization import normalized_quote_fields


SIMILARITY_WEIGHTS = {
    "layer": 20,
    "material": 15,
    "area": 15,
    "quantity": 15,
    "thickness": 10,
    "copper": 10,
    "surface_finish": 5,
    "delivery": 5,
    "special_processes": 5,
}

SPECIAL_PROCESS_FIELDS = ("enig", "vip", "impedance", "back_drill", "bvh")


def quote_profile(quote) -> dict:
    spec = dict(getattr(quote, "spec_json", None) or {})
    for attr in (
        "layer",
        "material",
        "qty",
        "length_mm",
        "width_mm",
        "area_in2",
        "board_thickness_mm",
        "copper_weight_oz",
        "surface_finish",
        "gold_thickness_uin",
        "delivery_days",
    ):
        value = getattr(quote, attr, None)
        if value is not None:
            spec[attr] = value
    if spec.get("area_in2") is not None and spec.get("area_inch") is None:
        spec["area_inch"] = spec["area_in2"]

    normalized = normalized_quote_fields(spec, getattr(quote, "breakdown_json", None) or {})
    return {
        "id": getattr(quote, "id", None),
        "quote_no": getattr(quote, "quote_no", None),
        "layer": normalized.get("layer"),
        "material": normalized.get("material"),
        "qty": to_float(spec.get("qty")),
        "area_in2": normalized.get("area_in2"),
        "board_thickness_mm": normalized.get("board_thickness_mm"),
        "copper_weight_oz": normalized.get("copper_weight_oz"),
        "surface_finish": normalized.get("surface_finish"),
        "delivery_days": normalized.get("delivery_days"),
        "special_processes": {
            field for field in SPECIAL_PROCESS_FIELDS if bool(spec.get(field))
        },
        "total": to_float(getattr(quote, "total", None)),
        "unit_price": to_float(getattr(quote, "unit_price", None)),
        "quote_outcome": getattr(quote, "quote_outcome", None) or "pending",
        "estimated_margin_pct": to_float(getattr(quote, "estimated_margin_pct", None)),
        "actual_margin_pct": to_float(getattr(quote, "actual_margin_pct", None)),
        "created_at": getattr(quote, "created_at", None),
    }


def _exact_score(left, right, weight: int) -> float:
    if left is None or right is None:
        return 0
    return weight if left == right else 0


def _ratio_similarity(left, right, weight: int) -> float:
    left_value = to_float(left)
    right_value = to_float(right)
    if left_value is None or right_value is None:
        return 0
    high = max(abs(left_value), abs(right_value))
    if high == 0:
        return weight
    diff_ratio = abs(left_value - right_value) / high
    return max(0, weight * (1 - diff_ratio))


def _special_process_score(left: set, right: set, weight: int) -> float:
    if not left and not right:
        return weight
    union = left | right
    if not union:
        return weight
    return weight * (len(left & right) / len(union))


def score_similarity(target, candidate) -> int:
    target_profile = quote_profile(target)
    candidate_profile = quote_profile(candidate)
    score = 0.0
    score += _exact_score(target_profile["layer"], candidate_profile["layer"], SIMILARITY_WEIGHTS["layer"])
    score += _exact_score(target_profile["material"], candidate_profile["material"], SIMILARITY_WEIGHTS["material"])
    score += _ratio_similarity(target_profile["area_in2"], candidate_profile["area_in2"], SIMILARITY_WEIGHTS["area"])
    score += _ratio_similarity(target_profile["qty"], candidate_profile["qty"], SIMILARITY_WEIGHTS["quantity"])
    score += _ratio_similarity(target_profile["board_thickness_mm"], candidate_profile["board_thickness_mm"], SIMILARITY_WEIGHTS["thickness"])
    score += _ratio_similarity(target_profile["copper_weight_oz"], candidate_profile["copper_weight_oz"], SIMILARITY_WEIGHTS["copper"])
    score += _exact_score(target_profile["surface_finish"], candidate_profile["surface_finish"], SIMILARITY_WEIGHTS["surface_finish"])
    score += _ratio_similarity(target_profile["delivery_days"], candidate_profile["delivery_days"], SIMILARITY_WEIGHTS["delivery"])
    score += _special_process_score(
        target_profile["special_processes"],
        candidate_profile["special_processes"],
        SIMILARITY_WEIGHTS["special_processes"],
    )
    return max(0, min(100, round(score)))


def serialize_similar_quote(quote, similarity: int) -> dict:
    unit_price = quote.unit_price
    if unit_price is None:
        unit_price = calculate_price_per_unit(quote.total, quote.qty)
    return {
        "id": quote.id,
        "quote_no": quote.quote_no or str(quote.id),
        "similarity": similarity,
        "layer": quote.layer,
        "material": quote.material,
        "qty": quote.qty,
        "total": quote.total,
        "unit_price": unit_price,
        "quote_outcome": quote.quote_outcome or "pending",
        "created_at": quote.created_at.isoformat() if quote.created_at else None,
    }


def get_candidate_quotes(session, QuoteHistory, target, limit: int = 200) -> list:
    query = session.query(QuoteHistory).filter(QuoteHistory.id != target.id)
    if target.layer is not None:
        query = query.filter(QuoteHistory.layer.between(target.layer - 2, target.layer + 2))
    if target.material:
        query = query.filter(QuoteHistory.material.ilike(f"%{target.material}%"))
    return query.order_by(QuoteHistory.created_at.desc()).limit(limit).all()


def find_similar_quotes(session, QuoteHistory, target, limit: int = 10) -> list:
    candidates = get_candidate_quotes(session, QuoteHistory, target)
    scored = [
        (score_similarity(target, candidate), candidate)
        for candidate in candidates
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        serialize_similar_quote(candidate, score)
        for score, candidate in scored[:limit]
        if score > 0
    ]


def historical_pricing_summary(similar_quotes: Iterable[dict], min_sample_size: int = 5) -> dict:
    comparable = list(similar_quotes)
    quoted_prices = [
        to_float(item.get("unit_price"))
        for item in comparable
        if to_float(item.get("unit_price")) is not None
    ]
    won_count = sum(1 for item in comparable if item.get("quote_outcome") == "won")
    lost_count = sum(1 for item in comparable if item.get("quote_outcome") == "lost")
    resolved_count = won_count + lost_count

    summary = {
        "comparable_count": len(comparable),
        "limited_data": len(comparable) < min_sample_size,
        "won_count": won_count,
        "lost_count": lost_count,
        "win_rate": round(won_count / resolved_count, 4) if resolved_count else None,
    }
    if quoted_prices:
        summary.update({
            "average_quoted_unit_price": round(sum(quoted_prices) / len(quoted_prices), 2),
            "median_quoted_unit_price": round(median(quoted_prices), 2),
            "lowest_quoted_unit_price": round(min(quoted_prices), 2),
            "highest_quoted_unit_price": round(max(quoted_prices), 2),
        })
    return summary
