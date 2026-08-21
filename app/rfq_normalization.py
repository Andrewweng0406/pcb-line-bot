"""Centralized RFQ field normalization for structured quote analytics."""

import re
from typing import Optional

from app.quote_metrics import to_float, to_non_negative_int


def normalize_layer(value) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip().lower()
    match = re.search(r"(\d+)", text)
    if not match:
        return None
    return int(match.group(1))


def normalize_material(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    compact = re.sub(r"[\s_-]+", "", text).upper()
    if compact == "FR4":
        return "FR-4"
    megtron = re.match(r"MEGTRON(\d+)$", compact)
    if megtron:
        return f"MEGTRON {megtron.group(1)}"
    return re.sub(r"\s+", " ", text).strip()


def normalize_surface_finish(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    compact = re.sub(r"[\s_-]+", "", text).upper()
    if compact in {"ENIG", "NIAU", "IMMERSIONGOLD", "ELECTROLESSNICKELIMMERSIONGOLD"}:
        return "ENIG"
    if compact in {"HARDGOLD", "GOLD"}:
        return "Hard Gold"
    if compact in {"HASL", "LEADFREEHASL"}:
        return "HASL"
    if compact in {"OSP"}:
        return "OSP"
    return text


def normalize_copper_weight_oz(value) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower()
    if "/" in text or "inner" in text or "outer" in text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*oz", text)
    if not match:
        return None
    return float(match.group(1))


def normalize_gold_thickness_uin(value, unit: Optional[str] = None) -> Optional[float]:
    number = to_float(value)
    if number is None:
        return None
    normalized_unit = (unit or "uin").lower().replace("μ", "u").strip()
    if normalized_unit in {"um", "u m", "micron", "microns"}:
        return round(number * 39.37, 2)
    return number


def normalize_area_in2(parsed: dict, result: dict = None) -> Optional[float]:
    result = result or {}
    area = to_float(result.get("area_inch"))
    if area is not None:
        return area
    area = to_float(parsed.get("area_inch") or parsed.get("area_in2"))
    if area is not None:
        return area
    length = to_float(parsed.get("length_mm"))
    width = to_float(parsed.get("width_mm"))
    if length is None or width is None:
        return None
    return round((length / 25.4) * (width / 25.4), 2)


def normalized_quote_fields(parsed: dict, result: dict = None) -> dict:
    parsed = parsed or {}
    result = result or {}
    surface_finish = parsed.get("surface_finish")
    if not surface_finish and parsed.get("enig"):
        surface_finish = "ENIG"

    return {
        "layer": normalize_layer(parsed.get("layer")),
        "material": normalize_material(parsed.get("material")),
        "area_in2": normalize_area_in2(parsed, result),
        "board_thickness_mm": to_float(
            parsed.get("thickness_mm")
            or parsed.get("thickness")
            or parsed.get("board_thickness_mm")
        ),
        "copper_weight_oz": normalize_copper_weight_oz(
            parsed.get("copper_weight")
            if parsed.get("copper_weight") is not None
            else parsed.get("copper_weight_oz")
        ),
        "surface_finish": normalize_surface_finish(surface_finish),
        "gold_thickness_uin": normalize_gold_thickness_uin(
            parsed.get("enig_thickness_uinch")
            or parsed.get("enig_thickness_uin")
            or parsed.get("gold_thickness_uin")
            or parsed.get("enig_thickness_um"),
            "um" if parsed.get("enig_thickness_um") and not parsed.get("enig_thickness_uinch") else "uin",
        ),
        "delivery_days": to_non_negative_int(parsed.get("delivery_days")),
    }
