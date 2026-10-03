"""Build an auditable review layer around AI-extracted RFQ fields."""

from __future__ import annotations

import re
from typing import Any


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
}


REVIEW_FIELDS = list(FIELD_LABELS.keys())
REQUIRED_FIELDS = ("layer", "qty")
SIZE_FIELDS = ("length_mm", "width_mm", "area_inch")
DEFAULT_FIELDS = {"issue_ratio": 1.0}


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
    "enig_thickness_uinch": [r"\d+(?:\.\d+)?\s*(?:u\"|uinch|um|μm|μ|u)\b"],
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


def _normalize_text(text: str | None) -> str:
    return (text or "").lower().replace("μ", "u")


def _has_evidence(field: str, text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in FIELD_PATTERNS.get(field, []))


def _review_item(field: str, value: Any, source: str, confidence: str, reason: str) -> dict:
    return {
        "field": field,
        "label": FIELD_LABELS.get(field, field),
        "value": value,
        "source": source,
        "confidence": confidence,
        "needs_review": confidence in {"low", "missing"} or source in {"default", "missing"},
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
    text = _normalize_text(raw_input)
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
        elif _has_evidence(field, text):
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

    if not any(_has_value(parsed.get(field)) for field in SIZE_FIELDS):
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
        "input_type": input_type,
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
