"""Safe Excel historical quote import with mapping, preview, and confirm."""

import json
import re
from datetime import datetime
from io import BytesIO
from typing import Dict, Iterable, Optional

from openpyxl import load_workbook

from app.quote_metrics import to_non_negative_float, to_non_negative_int
from app.quote_outcomes import normalize_outcome
from app.rfq_normalization import normalize_layer, normalize_material


DEFAULT_MAPPING = {
    "customer": "Customer Name",
    "layer": "Layers",
    "material": "Material",
    "qty": "Qty",
    "size": "Size",
    "total": "Quote",
    "quote_date": "Date",
    "quote_outcome": "Result",
}


def parse_mapping_json(raw: str = "") -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return {str(k): str(v) for k, v in data.items() if v}


def load_excel_rows(file_bytes: bytes) -> tuple[list[str], list[dict]]:
    workbook = load_workbook(BytesIO(file_bytes), data_only=True, read_only=True)
    worksheet = workbook.active
    rows = list(worksheet.iter_rows(values_only=True))
    if not rows:
        return [], []
    headers = [str(value).strip() if value is not None else "" for value in rows[0]]
    records = []
    for index, row in enumerate(rows[1:], start=2):
        if not any(value is not None and str(value).strip() for value in row):
            continue
        records.append({
            "row_number": index,
            "data": {
                headers[col_index]: row[col_index]
                for col_index in range(min(len(headers), len(row)))
                if headers[col_index]
            },
        })
    return headers, records


def _field(row: dict, mapping: dict, field: str):
    column = mapping.get(field)
    if not column:
        return None
    return row.get(column)


def parse_size(value) -> tuple[Optional[float], Optional[float]]:
    if value is None:
        return None, None
    text = str(value).lower().replace("mm", "")
    match = re.search(r"(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)", text)
    if not match:
        return None, None
    return float(match.group(1)), float(match.group(2))


def parse_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def normalize_result(value):
    if value is None or value == "":
        return "pending"
    text = str(value).strip().lower()
    aliases = {
        "win": "won",
        "won": "won",
        "order": "won",
        "ordered": "won",
        "lost": "lost",
        "loss": "lost",
        "no response": "no_response",
        "no_response": "no_response",
        "cancelled": "cancelled",
        "canceled": "cancelled",
        "pending": "pending",
    }
    return normalize_outcome(aliases.get(text, text)) or "pending"


def validate_import_rows(records: Iterable[dict], mapping: dict) -> list[dict]:
    validated = []
    for record in records:
        raw = record["data"]
        errors = []
        warnings = []

        layer = normalize_layer(_field(raw, mapping, "layer"))
        qty = to_non_negative_int(_field(raw, mapping, "qty"))
        total = to_non_negative_float(_field(raw, mapping, "total"))
        material = normalize_material(_field(raw, mapping, "material"))
        length_mm = to_non_negative_float(_field(raw, mapping, "length_mm"))
        width_mm = to_non_negative_float(_field(raw, mapping, "width_mm"))
        if (length_mm is None or width_mm is None) and mapping.get("size"):
            length_mm, width_mm = parse_size(_field(raw, mapping, "size"))
        quote_date = parse_date(_field(raw, mapping, "quote_date"))
        outcome = normalize_result(_field(raw, mapping, "quote_outcome"))

        if layer is None:
            errors.append("Missing or invalid layer")
        if qty is None or qty == 0:
            errors.append("Missing or invalid quantity")
        if total is None:
            errors.append("Missing or invalid quote total")
        if material is None:
            warnings.append("Missing material")
        if length_mm is None or width_mm is None:
            warnings.append("Missing board size")
        if mapping.get("quote_date") and quote_date is None:
            warnings.append("Could not parse quote date")

        validated.append({
            "row_number": record["row_number"],
            "status": "invalid" if errors else "valid",
            "errors": errors,
            "warnings": warnings,
            "mapped": {
                "customer": _field(raw, mapping, "customer"),
                "layer": layer,
                "material": material,
                "qty": qty,
                "length_mm": length_mm,
                "width_mm": width_mm,
                "total": total,
                "unit_price": round(total / qty, 2) if total is not None and qty else None,
                "quote_date": quote_date,
                "quote_outcome": outcome,
            },
        })
    return validated


def preview_import(file_bytes: bytes, mapping: dict = None) -> dict:
    headers, records = load_excel_rows(file_bytes)
    mapping = mapping or DEFAULT_MAPPING
    rows = validate_import_rows(records, mapping) if mapping else []
    valid = [row for row in rows if row["status"] == "valid"]
    invalid = [row for row in rows if row["status"] == "invalid"]
    warnings = [row for row in rows if row["warnings"]]
    return {
        "headers": headers,
        "rows_detected": len(records),
        "valid": len(valid),
        "warnings": len(warnings),
        "invalid": len(invalid),
        "rows": rows,
        "preview_rows": rows[:50],
    }


def confirm_import(session, db_module, file_bytes: bytes, mapping: dict = None, user_id: int = None) -> dict:
    preview = preview_import(file_bytes, mapping or DEFAULT_MAPPING)
    valid_rows = [row for row in preview["rows"] if row["status"] == "valid"]
    if preview["invalid"]:
        return {**preview, "committed": 0, "status": "error"}

    committed = 0
    for row in valid_rows:
        mapped = row["mapped"]
        customer_id = None
        customer_name = mapped.get("customer")
        if customer_name:
            customer_name = str(customer_name).strip()
            customer = (
                session.query(db_module.Customer)
                .filter(db_module.Customer.company_name == customer_name)
                .first()
            )
            if customer is None:
                customer = db_module.Customer(company_name=customer_name)
                session.add(customer)
                session.flush()
            customer_id = customer.id

        quote = db_module.QuoteHistory(
            source_channel_id="excel_import",
            source_channel="excel_import",
            product_type="pcb",
            customer_id=customer_id,
            layer=mapped["layer"],
            material=mapped["material"],
            length_mm=mapped["length_mm"],
            width_mm=mapped["width_mm"],
            qty=mapped["qty"],
            total=mapped["total"],
            unit_price=mapped["unit_price"],
            status="pending",
            quote_outcome=mapped["quote_outcome"],
            rfq_received_at=mapped["quote_date"],
            quote_sent_at=mapped["quote_date"],
            spec_json={
                "source": "excel_import",
                "row_number": row["row_number"],
                "layer": mapped["layer"],
                "material": mapped["material"],
                "qty": mapped["qty"],
                "length_mm": mapped["length_mm"],
                "width_mm": mapped["width_mm"],
            },
            breakdown_json={"source": "excel_import"},
            created_by_user_id=user_id,
        )
        session.add(quote)
        committed += 1
    session.commit()
    return {**preview, "committed": committed, "status": "success"}
