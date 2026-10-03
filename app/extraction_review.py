"""Build an auditable review layer around AI-extracted RFQ fields."""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from itsdangerous import BadSignature, URLSafeTimedSerializer


EXTRACTION_REVIEW_KEY = "_extraction_review"


FIELD_LABELS = {
    "layer": "Layers",
    "qty": "Quantity",
    "material": "Material",
    "length_mm": "Length",
    "width_mm": "Width",
    "issue_ratio": "Issue Ratio",
    "delivery_days": "Lead Time",
    "thickness_mm": "Board Thickness",
    "surface_finish": "Surface Finish",
    "enig": "ENIG",
    "enig_thickness_uinch": "Gold Thickness",
    "vip": "VIP",
    "back_drill": "Back Drill",
    "bvh": "BVH",
    "impedance": "Impedance",
    "hard_gold": "Hard Gold",
    "copper_weight": "Copper Thickness",
    "copper_outer_oz": "Outer Copper",
    "copper_inner_oz": "Inner Copper",
    "pitch_mm": "Pitch",
    "line_space_mil": "Line / Space",
    "min_hole_mil": "Min Hole",
    "warpage_mil_per_inch": "Warpage",
    "legend_color": "Legend Color",
    "solder_mask_color": "Solder Mask Color",
    "special_requirements": "Special Requirements",
    "area_inch": "Area (in2)",
    "trace_to_hole_mil": "Trace to Hole",
    "hole_land_mil": "Hole / Land",
    "aspect_ratio": "Aspect Ratio",
    "press_count": "Press Count",
    "internal_layers": "Internal Layers",
    "countersunk": "Countersunk",
    "counterbored": "Counterbored",
    "inspection_report_required": "Inspection Report",
    "is_reorder": "Re-order",
    "flatness": "Flatness",
    "hole_size_mil": "Hole Size",
    "copper_weight_oz": "Copper Weight (oz)",
    "back_drill_fee": "Back Drill Fee",
}


REVIEW_FIELDS = list(FIELD_LABELS.keys())
REQUIRED_FIELDS = ("layer", "qty")
SIZE_FIELDS = ("length_mm", "width_mm", "area_inch")
DEFAULT_FIELDS = {"issue_ratio": 1.0}
NUMERIC_FIELDS = {
    "layer", "qty", "length_mm", "width_mm", "issue_ratio", "delivery_days",
    "thickness_mm", "enig_thickness_uinch", "copper_outer_oz", "copper_inner_oz",
    "pitch_mm", "line_space_mil", "min_hole_mil", "warpage_mil_per_inch",
    "area_inch", "trace_to_hole_mil", "hole_land_mil", "aspect_ratio",
    "press_count", "internal_layers",
    "hole_size_mil", "copper_weight_oz", "back_drill_fee",
}


FIELD_PATTERNS = {
    "layer": [r"\b\d+\s*(?:l|layer|layers|層)\b"],
    "qty": [r"\b\d+\s*(?:pcs?|pieces?|片|數量|qty|quantity)\b"],
    "material": [r"\bfr[-\s]?4\b", r"\bmegtron\s*\d+\b", r"\bm\d\b"],
    "length_mm": [r"\d+(?:\.\d+)?\s*[x×]\s*\d+(?:\.\d+)?\s*mm"],
    "width_mm": [r"\d+(?:\.\d+)?\s*[x×]\s*\d+(?:\.\d+)?\s*mm"],
    "issue_ratio": [r"issue\s*ratio", r"投料", r"\b\d+\s*片\s*產出\s*\d+\s*片"],
    "delivery_days": [r"\b\d+\s*(?:working\s*)?days?\b", r"交期\s*\d+\s*天", r"\d+\s*天"],
    "thickness_mm": [r"(?:thickness|板厚|厚度)\s*\d+(?:\.\d+)?\s*mm"],
    "surface_finish": [r"\benig\b", r"\bosp\b", r"\bhasl\b", r"hard\s*gold", r"化金", r"表面處理"],
    "enig": [r"\benig\b", r"化金", r"鍍金"],
    "enig_thickness_uinch": [r"\d+(?:\.\d+)?\s*(?:u\"|uinch\b|u\b)"],
    "vip": [r"\bvip\b", r"via[-\s]*in[-\s]*pad", r"塞孔"],
    "back_drill": [r"back\s*drill", r"背鑽"],
    "bvh": [r"\bbvh\b"],
    "impedance": [r"impedance", r"阻抗"],
    "hard_gold": [r"hard\s*gold"],
    "copper_weight": [r"\d+(?:\.\d+)?\s*oz", r"銅厚", r"copper"],
    "copper_outer_oz": [r"outer\s*\d+(?:\.\d+)?\s*oz", r"外層\s*\d+(?:\.\d+)?\s*oz"],
    "copper_inner_oz": [r"inner\s*\d+(?:\.\d+)?\s*oz", r"內層\s*\d+(?:\.\d+)?\s*oz"],
    "pitch_mm": [r"pitch\s*\d+(?:\.\d+)?\s*mm", r"pitch\s*\d+(?:\.\d+)?"],
    "line_space_mil": [r"line\s*/\s*space\s*\d+(?:\.\d+)?\s*mil"],
    "min_hole_mil": [r"(?:min(?:imum)?\s*hole|最小孔)\s*\d+(?:\.\d+)?\s*mil"],
    "warpage_mil_per_inch": [r"warpage\s*\d+(?:\.\d+)?", r"板翹\s*\d+(?:\.\d+)?"],
    "legend_color": [r"legend\s*color", r"文字顏色", r"白色文字"],
    "solder_mask_color": [r"solder\s*mask", r"s/m\s*color", r"防焊", r"綠油"],
    "special_requirements": [r"inspection\s*report", r"特殊", r"檢驗報告"],
}


def _has_value(value: Any) -> bool:
    return value is not None and value != ""


VALUE_PATTERNS = {
    "layer": r"(?<!\w)(?P<value>\d+)\s*(?:layers?\b|l\b|層)",
    "qty": r"(?:\b(?:qty|quantity)\s*[:=]?\s*|數量\s*[:：]?\s*)(?P<value>\d+)",
    "thickness_mm": r"(?:thickness|板厚|厚度)\s*[:：=]?\s*(?P<value>\d+(?:\.\d+)?)\s*mm",
    "delivery_days": r"(?P<value>\d+)\s*(?:working\s*)?(?:days?\b|天)",
}


def _evidence(field: str, value: Any, text: str) -> tuple[list[str], bool, bool]:
    patterns = [VALUE_PATTERNS[field]] if field in VALUE_PATTERNS else FIELD_PATTERNS.get(field, [])
    if field == "qty":
        patterns.append(r"(?P<value>\d+)\s*(?:pcs?\b|pieces?\b|片)")
    if field == "layer":
        patterns.append(r"\blayers?\s*[:=]\s*(?P<value>\d+)")
    matches = [match for pattern in patterns for match in re.finditer(pattern, text, re.IGNORECASE)]
    snippets = list(dict.fromkeys(match.group(0) for match in matches))
    if not isinstance(value, bool) and any(
        re.search(r"(?:\b(?:no|not|without)\b|不要|不使用|非|無)\s*$", text[max(0, match.start() - 32):match.start()], re.IGNORECASE)
        for match in matches
    ):
        return snippets, False, True
    candidates = [float(match.group("value")) for match in matches if "value" in match.groupdict()]
    if candidates:
        try:
            matches_value = all(candidate == float(value) for candidate in candidates)
        except (TypeError, ValueError):
            matches_value = False
        return snippets, matches_value, len(set(candidates)) > 1 or not matches_value
    if field in {"length_mm", "width_mm"} and matches:
        index = 0 if field == "length_mm" else 1
        candidates = [float(re.findall(r"\d+(?:\.\d+)?", match.group(0))[index]) for match in matches]
        return snippets, all(candidate == float(value) for candidate in candidates), len(set(candidates)) > 1 or any(candidate != float(value) for candidate in candidates)
    # Presence of a keyword alone does not establish the extracted value or polarity.
    if isinstance(value, bool):
        return snippets, False, False
    if isinstance(value, (int, float)):
        numbers = [float(number) for snippet in snippets for number in re.findall(r"\d+(?:\.\d+)?", snippet)]
        return snippets, bool(numbers) and all(number == value for number in numbers), len(set(numbers)) > 1
    normalized_value = re.sub(r"[\s-]", "", str(value).lower())
    normalized_snippets = {re.sub(r"[\s-]", "", snippet.lower()) for snippet in snippets}
    conflict = field in {"material", "surface_finish"} and len(normalized_snippets) > 1
    return snippets, normalized_snippets == {normalized_value}, conflict


def _review_item(field: str, value: Any, source: str, confidence: str, reason: str) -> dict:
    return {
        "field": field,
        "label": FIELD_LABELS.get(field, field),
        "value": value,
        "source": source,
        "confidence": confidence,
        "needs_review": confidence != "high",
        "reason": reason,
    }


def build_extraction_review(parsed: dict, raw_input: str = "", input_type: str = "text") -> dict:
    """Classify extracted fields by evidence and review risk.

    The goal is operator trust, not pretending the model knows its own
    confidence. Explicit textual evidence gets high confidence; extracted image
    values are medium until a human reviews them; defaults and missing required
    fields are low/missing.
    """
    parsed = parsed or {}
    text = raw_input or ""
    fields = []

    for field in REVIEW_FIELDS:
        value = parsed.get(field)
        if not _has_value(value):
            if field in DEFAULT_FIELDS:
                fields.append(
                    _review_item(
                        field,
                        DEFAULT_FIELDS[field],
                        "default",
                        "low",
                        "System default; confirm before sending.",
                    )
                )
            elif field in REQUIRED_FIELDS:
                fields.append(
                    _review_item(
                        field,
                        None,
                        "missing",
                        "missing",
                        "Required field was not extracted.",
                    )
                )
            continue

        evidence, supported, conflict = _evidence(field, value, text)
        if input_type == "image":
            fields.append(
                _review_item(
                    field,
                    value,
                    "image",
                    "medium",
                    "Extracted from uploaded image; verify against the drawing/spec.",
                )
            )
        elif conflict:
            fields.append(_review_item(field, value, "conflict", "low", "RFQ values disagree with each other or with the extracted value."))
        elif supported:
            fields.append(
                _review_item(
                    field,
                    value,
                    "explicit",
                    "high",
                    "Direct evidence found in the RFQ text.",
                )
            )
        else:
            fields.append(
                _review_item(
                    field,
                    value,
                    "inferred",
                    "medium",
                    "Value was extracted, but direct evidence was not obvious.",
                )
            )
        fields[-1]["evidence"] = evidence

    if not (_has_value(parsed.get("area_inch")) or all(_has_value(parsed.get(field)) for field in ("length_mm", "width_mm"))):
        fields.append(
            _review_item(
                "size",
                None,
                "missing",
                "missing",
                "Size or area is required before pricing.",
            )
        )

    counts = {
        "high": sum(1 for item in fields if item["confidence"] == "high"),
        "medium": sum(1 for item in fields if item["confidence"] == "medium"),
        "low": sum(1 for item in fields if item["confidence"] == "low"),
        "missing": sum(1 for item in fields if item["confidence"] == "missing"),
        "needs_review": sum(1 for item in fields if item["needs_review"]),
    }
    return {
        "version": 2,
        "input_type": input_type,
        "raw_input": raw_input if input_type == "text" else "",
        "summary": counts,
        "fields": fields,
    }


def attach_extraction_review(parsed: dict, review: dict | None) -> dict:
    parsed = dict(parsed or {})
    if review:
        parsed[EXTRACTION_REVIEW_KEY] = review
    return parsed


def extraction_review_from_spec(spec_json: dict | None) -> dict | None:
    if not isinstance(spec_json, dict):
        return None
    review = spec_json.get(EXTRACTION_REVIEW_KEY)
    return review if isinstance(review, dict) else None


def sign_review(review: dict, user_id: int) -> str:
    from app.core.config import settings
    return URLSafeTimedSerializer(settings.SECRET_KEY, salt="extraction-review").dumps({"review": review, "user_id": user_id})


def read_review(token: str, user_id: int) -> dict:
    from app.core.config import settings
    try:
        payload = URLSafeTimedSerializer(settings.SECRET_KEY, salt="extraction-review").loads(token, max_age=86400)
        if payload["user_id"] != user_id or not isinstance(payload["review"], dict):
            raise ValueError("Invalid review owner")
        return payload["review"]
    except (BadSignature, ValueError, KeyError, TypeError) as exc:
        raise ValueError("Extraction review expired or was modified. Parse the RFQ again.") from exc


def reconcile_review(review: dict, spec: dict) -> dict:
    result = deepcopy(review)
    known = {item["field"] for item in result["fields"]}
    for field in REVIEW_FIELDS:
        if field not in known and _has_value(spec.get(field)) and spec.get(field) is not False:
            result["fields"].append(_review_item(field, None, "missing", "missing", "Added during human review."))
    for item in result["fields"]:
        item["needs_review"] = item.get("needs_review", False) or item["confidence"] != "high"
        field = item["field"]
        value = spec.get(field, DEFAULT_FIELDS.get(field))
        if field == "size":
            value = spec.get("area_inch") or (f'{float(spec["length_mm"]):g} x {float(spec["width_mm"]):g} mm' if spec.get("length_mm") and spec.get("width_mm") else None)
        previous = item.get("final_value", item.get("value"))
        item["final_value"] = value
        if not _same_value(field, previous, value):
            item["changed"] = not _same_value(field, value, item.get("value"))
            item["needs_review"] = True
            item.pop("confirmation", None)
    for confidence in ("high", "medium", "low", "missing"):
        result["summary"][confidence] = sum(item["confidence"] == confidence for item in result["fields"])
    result["summary"]["needs_review"] = len(pending_fields(result))
    return result


def _same_value(field: str, left: Any, right: Any) -> bool:
    if field in NUMERIC_FIELDS and _has_value(left) and _has_value(right):
        try:
            return float(left) == float(right)
        except (TypeError, ValueError):
            return False
    return left == right


def pending_fields(review: dict | None) -> list[dict]:
    return [item for item in (review or {}).get("fields", []) if item.get("needs_review") and not item.get("confirmation")]


def confirm_review(review: dict, fields: list[str], user_id: int, email: str, note: str) -> dict:
    result = deepcopy(review)
    stamp = datetime.now(timezone.utc).isoformat()
    for item in result["fields"]:
        if item["field"] not in fields or item.get("confirmation"):
            continue
        value = item.get("final_value", item.get("value"))
        removable = item.get("changed") and _has_value(item.get("value")) and item["field"] not in {*REQUIRED_FIELDS, *DEFAULT_FIELDS, "size"}
        if not _has_value(value) and not removable:
            raise ValueError(f'{item["label"]}: supply a value before confirming.')
        if (item.get("changed") or item.get("source") == "conflict") and not note.strip():
            raise ValueError("A review note is required when correcting extracted values or resolving conflicts.")
        event = {"field": item["field"], "original_value": item.get("value"), "final_value": item.get("final_value", item.get("value")), "user_id": user_id, "email": email, "at": stamp, "note": note.strip(), "action": "corrected" if item.get("changed") else "confirmed"}
        item["confirmation"] = event
        result.setdefault("events", []).append(event)
    result["summary"]["needs_review"] = len(pending_fields(result))
    return result


def clarification_draft(review: dict | None) -> str:
    pending = [item for item in pending_fields(review) if item["field"] != "issue_ratio"]
    if not pending:
        return ""
    questions = []
    for item in pending:
        evidence = "; ".join(item.get("evidence", []))
        if item.get("source") == "conflict":
            questions.append(f'- {item["label"]}: conflicting specifications ({evidence}). Please confirm the intended value.')
        elif item.get("source") == "missing":
            questions.append(f'- Please provide {item["label"].lower()}.')
        elif item.get("final_value", item.get("value")) is None:
            questions.append(f'- Please confirm that {item["label"].lower()} is not specified.')
        else:
            questions.append(f'- Please confirm {item["label"].lower()}: {item.get("final_value", item.get("value"))}.')
    return "Subject: PCB RFQ specification confirmation\n\nHello,\n\nBefore we finalize your quotation, please confirm the following:\n\n" + "\n".join(questions) + "\n\nThank you."


def release_pending(spec: dict | None) -> list[dict]:
    review = extraction_review_from_spec(spec)
    return pending_fields(reconcile_review(review, spec)) if review else []
