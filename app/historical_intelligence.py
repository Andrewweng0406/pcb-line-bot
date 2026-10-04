"""Explainable historical RFQ similarity and pricing summaries."""

from math import isfinite
from statistics import mean, median
from typing import Iterable

from app.quote_metrics import calculate_price_per_unit, to_float
from app.rfq_normalization import normalized_quote_fields
from app.extraction_review import extraction_review_from_spec, release_pending


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
COMPARISON_FIELDS = (
    "layer", "material", "area_in2", "qty", "board_thickness_mm",
    "copper_weight_oz", "surface_finish", "gold_thickness_uin", "delivery_days",
    *SPECIAL_PROCESS_FIELDS, "currency", "pricing_version",
)


def finite_number(value):
    if isinstance(value, bool):
        return None
    number = to_float(value)
    return number if number is not None and isfinite(number) else None


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
    if finite_number(spec.get("delivery_days")) is None:
        spec["delivery_days"] = None

    normalized = normalized_quote_fields(spec, getattr(quote, "breakdown_json", None) or {})
    for field in ("layer", "area_in2", "board_thickness_mm", "copper_weight_oz", "gold_thickness_uin", "delivery_days"):
        normalized[field] = finite_number(normalized.get(field))
    return {
        "id": getattr(quote, "id", None),
        "quote_no": getattr(quote, "quote_no", None),
        "layer": normalized.get("layer"),
        "material": normalized.get("material"),
        "qty": finite_number(spec.get("qty")),
        "area_in2": normalized.get("area_in2"),
        "board_thickness_mm": normalized.get("board_thickness_mm"),
        "copper_weight_oz": normalized.get("copper_weight_oz"),
        "surface_finish": normalized.get("surface_finish"),
        "delivery_days": normalized.get("delivery_days"),
        "gold_thickness_uin": normalized.get("gold_thickness_uin"),
        "process_values": {
            field: spec.get(field) if isinstance(spec.get(field), bool) else None
            for field in SPECIAL_PROCESS_FIELDS
        },
        "currency": (getattr(quote, "currency", None) or "").strip().upper() or None,
        "pricing_version": getattr(quote, "pricing_version", None),
        "review_pending": bool(release_pending(spec)),
        "special_processes": {
            field for field in SPECIAL_PROCESS_FIELDS if bool(spec.get(field))
        },
        "total": finite_number(getattr(quote, "total", None)),
        "unit_price": finite_number(getattr(quote, "unit_price", None)),
        "final_price": finite_number(getattr(quote, "final_price", None)),
        "actual_cost": finite_number(getattr(quote, "actual_cost", None)),
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
    left_value = finite_number(left)
    right_value = finite_number(right)
    if left_value is None or right_value is None:
        return 0
    high = max(abs(left_value), abs(right_value))
    if high == 0:
        return weight
    diff_ratio = abs(left_value - right_value) / high
    return max(0, weight * (1 - diff_ratio))


def _special_process_score(left: dict, right: dict, weight: int) -> float:
    matches = sum(left[field] is not None and right[field] is not None and left[field] == right[field]
                  for field in SPECIAL_PROCESS_FIELDS)
    return weight * matches / len(SPECIAL_PROCESS_FIELDS)


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
        target_profile["process_values"],
        candidate_profile["process_values"],
        SIMILARITY_WEIGHTS["special_processes"],
    )
    return max(0, min(100, round(score)))


def specification_differences(target: dict, candidate: dict) -> list:
    rows = []
    for field in COMPARISON_FIELDS:
        left = target["process_values"].get(field) if field in SPECIAL_PROCESS_FIELDS else target.get(field)
        right = candidate["process_values"].get(field) if field in SPECIAL_PROCESS_FIELDS else candidate.get(field)
        state = "unknown" if left is None or right is None else "same" if left == right else "different"
        delta = None
        if state == "different" and not isinstance(left, bool) and not isinstance(right, bool):
            a, b = finite_number(left), finite_number(right)
            if a is not None and b is not None and a != 0:
                delta = finite_number(round((b - a) / abs(a) * 100, 1))
        rows.append({"field": field, "current": left, "historical": right, "state": state, "delta_pct": delta})
    return rows


def comparison_exclusions(target: dict, candidate: dict, similarity: int) -> list:
    reasons = []
    for field in ("currency", "pricing_version"):
        if not target.get(field) or not candidate.get(field):
            reasons.append(f"missing_{field}")
        elif target[field] != candidate[field]:
            reasons.append(f"different_{field}")
    if target["review_pending"] or candidate["review_pending"]:
        reasons.append("review_pending")
    # These are conservative matching rules, not model probabilities.
    for field in ("layer", "material", "board_thickness_mm", "copper_weight_oz", "surface_finish"):
        if target.get(field) is None or candidate.get(field) is None:
            reasons.append("missing_specification")
        elif field in {"layer", "board_thickness_mm", "copper_weight_oz"} and min(target[field], candidate[field]) <= 0:
            reasons.append("missing_specification")
        elif target[field] != candidate[field]:
            reasons.append("different_specification")
    if target.get("surface_finish") in {"ENIG", "Hard Gold"} and (
        target.get("gold_thickness_uin") is None or candidate.get("gold_thickness_uin") is None
        or min(target["gold_thickness_uin"], candidate["gold_thickness_uin"]) <= 0
    ):
        reasons.append("missing_specification")
    elif target.get("gold_thickness_uin") != candidate.get("gold_thickness_uin"):
        reasons.append("different_specification")
    for field in ("area_in2", "qty", "delivery_days"):
        a, b = finite_number(target.get(field)), finite_number(candidate.get(field))
        if a is None or b is None or min(a, b) <= 0:
            reasons.append("missing_specification")
        elif max(a, b) / min(a, b) > 2:
            reasons.append("scale_difference")
    for field in SPECIAL_PROCESS_FIELDS:
        a, b = target["process_values"][field], candidate["process_values"][field]
        if a is None or b is None:
            reasons.append("unknown_processes")
        elif a != b:
            reasons.append("different_specification")
    if similarity < 75:
        reasons.append("low_similarity")
    return list(dict.fromkeys(reasons))


def serialize_similar_quote(quote, similarity: int, target=None) -> dict:
    profile = quote_profile(quote)
    target_profile = quote_profile(target) if target is not None else None
    qty = profile["qty"]
    unit_price = profile["unit_price"]
    if getattr(quote, "unit_price", None) is None and qty and qty > 0:
        unit_price = finite_number(calculate_price_per_unit(profile["total"], qty))
    unit_price = unit_price if unit_price is not None and unit_price > 0 else None
    accepted = profile["final_price"]
    cost = profile["actual_cost"]
    won = profile["quote_outcome"] == "won"
    exclusions = comparison_exclusions(target_profile, profile, similarity) if target_profile else ["missing_specification"]
    return {
        "id": quote.id,
        "quote_no": quote.quote_no or str(quote.id),
        "similarity": similarity,
        "layer": profile["layer"],
        "material": profile["material"],
        "qty": profile["qty"],
        "total": profile["total"],
        "unit_price": unit_price,
        "accepted_unit_price": finite_number(round(accepted / qty, 2)) if won and accepted is not None and accepted > 0 and qty and qty > 0 else None,
        "actual_unit_cost": finite_number(round(cost / qty, 2)) if won and cost is not None and cost >= 0 and qty and qty > 0 else None,
        "currency": profile["currency"],
        "pricing_version": profile["pricing_version"],
        "eligible": not exclusions,
        "exclusions": exclusions,
        "differences": specification_differences(target_profile, profile) if target_profile else [],
        "quote_outcome": quote.quote_outcome or "pending",
        "created_at": quote.created_at.isoformat() if quote.created_at else None,
    }


def get_candidate_quotes(session, QuoteHistory, target, limit: int = 200) -> list:
    query = session.query(QuoteHistory).filter(QuoteHistory.id != target.id)
    if target.layer is not None:
        query = query.filter(QuoteHistory.layer.between(target.layer - 2, target.layer + 2))
    # Material aliases are normalized in Python (FR4 and FR-4 are equivalent).
    return query.order_by(QuoteHistory.created_at.desc(), QuoteHistory.id.desc()).limit(limit).all()


def find_similar_quotes(session, QuoteHistory, target, limit: int = 10) -> list:
    candidates = get_candidate_quotes(session, QuoteHistory, target)
    cache = {quote.id: quote for quote in [target, *candidates]}

    def family_root(quote):
        visited = set()
        while quote is not None and quote.id not in visited:
            visited.add(quote.id)
            parent = (extraction_review_from_spec(quote.spec_json) or {}).get("revision_of")
            if parent is None:
                return quote.id
            if not isinstance(parent, int) or len(visited) > 50:
                return None
            if parent not in cache:
                cache[parent] = session.get(QuoteHistory, parent)
            quote = cache[parent]
        return None

    target_family = family_root(target)
    seen_families = set()
    serialized = []
    for candidate in candidates:
        score = score_similarity(target, candidate)
        item = serialize_similar_quote(candidate, score, target)
        family = family_root(candidate)
        if family is None or target_family is None:
            item["exclusions"].append("unknown_lineage")
        elif family == target_family or family in seen_families:
            item["exclusions"].append("related_revision")
        seen_families.add(family)
        item["eligible"] = not item["exclusions"]
        serialized.append(item)
    serialized.sort(key=lambda item: item["similarity"], reverse=True)
    return [item for item in serialized if item["similarity"] > 0][:limit]


def historical_pricing_summary(similar_quotes: Iterable[dict], min_sample_size: int = 5) -> dict:
    candidates = list(similar_quotes)
    comparable = [item for item in candidates if item.get("eligible")]
    currencies = {item.get("currency") for item in comparable}
    versions = {item.get("pricing_version") for item in comparable}
    if None in currencies or len(currencies) > 1 or None in versions or len(versions) > 1:
        comparable = []
    quoted_prices = [
        finite_number(item.get("unit_price"))
        for item in comparable
        if finite_number(item.get("unit_price")) is not None and finite_number(item.get("unit_price")) > 0
    ]
    won_count = sum(1 for item in comparable if item.get("quote_outcome") == "won")
    lost_count = sum(1 for item in comparable if item.get("quote_outcome") == "lost")
    resolved_count = won_count + lost_count

    summary = {
        "comparable_count": len(comparable),
        "candidate_count": len(candidates),
        "excluded_count": len(candidates) - len(comparable),
        "currency": next(iter(currencies)) if comparable else None,
        "minimum_samples": min_sample_size,
        "limited_data": len(quoted_prices) < min_sample_size,
        "won_count": won_count,
        "lost_count": lost_count,
        "win_rate": round(won_count / resolved_count, 4) if resolved_count else None,
    }
    if len(quoted_prices) >= min_sample_size:
        summary.update({
            "average_quoted_unit_price": round(mean(quoted_prices), 2),
            "median_quoted_unit_price": round(median(quoted_prices), 2),
            "lowest_quoted_unit_price": round(min(quoted_prices), 2),
            "highest_quoted_unit_price": round(max(quoted_prices), 2),
        })
    evidence = []
    for key, values in (
        ("quoted", quoted_prices),
        ("accepted", [item["accepted_unit_price"] for item in comparable if item.get("quote_outcome") == "won" and finite_number(item.get("accepted_unit_price")) is not None and item["accepted_unit_price"] > 0]),
        ("cost", [item["actual_unit_cost"] for item in comparable if item.get("quote_outcome") == "won" and finite_number(item.get("actual_unit_cost")) is not None and item["actual_unit_cost"] >= 0]),
    ):
        evidence.append({"kind": key, "count": len(values), "available": len(values) >= min_sample_size,
                         "median": round(median(values), 2) if len(values) >= min_sample_size else None})
    summary["evidence"] = evidence
    return summary
