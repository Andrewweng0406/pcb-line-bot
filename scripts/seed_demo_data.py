#!/usr/bin/env python3
"""Seed interview-ready demo customers and PCB RFQs.

The script is idempotent: it upserts records by customer company name and
quote number, so it can be rerun before a demo without creating duplicates.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.core.database as db
from app.quote_engine import calculate_quote
from app.quote_metrics import calculate_margin
from app.rfq_normalization import normalized_quote_fields


CUSTOMERS = [
    {
        "company_name": "Apex Robotics",
        "contact": "Mia Chen",
        "phone": "+1-408-555-0131",
        "email": "mia.chen@apexrobotics.example",
        "common_specs": {"segment": "Industrial automation", "default_currency": "NTD"},
    },
    {
        "company_name": "Nova Medical Devices",
        "contact": "Ethan Brooks",
        "phone": "+1-617-555-0198",
        "email": "ethan.brooks@novamed.example",
        "common_specs": {"segment": "Medical electronics", "default_currency": "NTD"},
    },
    {
        "company_name": "Orion EV Systems",
        "contact": "Priya Shah",
        "phone": "+1-512-555-0172",
        "email": "priya.shah@orionev.example",
        "common_specs": {"segment": "EV power systems", "default_currency": "NTD"},
    },
    {
        "company_name": "HelioSense IoT",
        "contact": "Daniel Park",
        "phone": "+1-949-555-0144",
        "email": "daniel.park@heliosense.example",
        "common_specs": {"segment": "IoT sensors", "default_currency": "NTD"},
    },
]


DEMO_QUOTES = [
    {
        "quote_no": "DEMO-RFQ-001",
        "customer": "Apex Robotics",
        "days_ago": 0,
        "status": "approved",
        "quote_outcome": "pending",
        "notes": "Demo: urgent prototype build for motor-control board.",
        "spec": {
            "layer": 8,
            "material": "FR-4",
            "qty": 12,
            "issue_ratio": 1.5,
            "length_mm": 92,
            "width_mm": 64,
            "thickness_mm": 1.6,
            "pitch_mm": 0.45,
            "trace_to_hole_mil": 4.5,
            "line_space_mil": 4,
            "min_hole_mil": 8,
            "surface_finish": "ENIG",
            "enig": True,
            "enig_thickness_uinch": 8,
            "vip": True,
            "back_drill": False,
            "press_count": 1,
            "internal_layers": 6,
            "delivery_days": 7,
        },
    },
    {
        "quote_no": "DEMO-RFQ-002",
        "customer": "Nova Medical Devices",
        "days_ago": 2,
        "status": "ordered",
        "quote_outcome": "won",
        "notes": "Demo: customer accepted after engineering review.",
        "final_price_multiplier": 1.02,
        "actual_cost_multiplier": 0.68,
        "actual_production_days": 8,
        "spec": {
            "layer": 10,
            "material": "FR-4",
            "qty": 25,
            "issue_ratio": 1.2,
            "length_mm": 78,
            "width_mm": 52,
            "thickness_mm": 1.6,
            "pitch_mm": 0.5,
            "trace_to_hole_mil": 5,
            "line_space_mil": 4,
            "min_hole_mil": 8,
            "surface_finish": "ENIG",
            "enig": True,
            "enig_thickness_uinch": 5,
            "vip": False,
            "back_drill": False,
            "press_count": 1,
            "internal_layers": 8,
            "delivery_days": 8,
        },
    },
    {
        "quote_no": "DEMO-RFQ-003",
        "customer": "Orion EV Systems",
        "days_ago": 5,
        "status": "approved",
        "quote_outcome": "lost",
        "notes": "Demo: lost on lead time; useful for historical intelligence.",
        "final_price_multiplier": 0.98,
        "actual_cost_multiplier": 0.74,
        "lost_reason": "lead_time",
        "lost_reason_note": "Customer needed a five-day delivery window.",
        "competitor_name": "FastBoard Asia",
        "competitor_price_multiplier": 0.94,
        "actual_production_days": 10,
        "spec": {
            "layer": 12,
            "material": "MEGTRON 6",
            "qty": 8,
            "issue_ratio": 2.0,
            "length_mm": 110,
            "width_mm": 75,
            "thickness_mm": 2.0,
            "pitch_mm": 0.4,
            "trace_to_hole_mil": 4.3,
            "line_space_mil": 3.5,
            "min_hole_mil": 7,
            "surface_finish": "ENIG",
            "enig": True,
            "enig_thickness_uinch": 10,
            "vip": True,
            "back_drill": True,
            "press_count": 2,
            "internal_layers": 10,
            "delivery_days": 10,
        },
    },
    {
        "quote_no": "DEMO-RFQ-004",
        "customer": "HelioSense IoT",
        "days_ago": 8,
        "status": "ordered",
        "quote_outcome": "won",
        "notes": "Demo: compact IoT sensor board, repeatable volume order.",
        "final_price_multiplier": 1.0,
        "actual_cost_multiplier": 0.63,
        "actual_production_days": 6,
        "spec": {
            "layer": 6,
            "material": "FR-4",
            "qty": 100,
            "issue_ratio": 1.1,
            "length_mm": 45,
            "width_mm": 32,
            "thickness_mm": 1.0,
            "pitch_mm": 0.55,
            "trace_to_hole_mil": 5,
            "line_space_mil": 4,
            "min_hole_mil": 8,
            "surface_finish": "OSP",
            "enig": False,
            "vip": False,
            "back_drill": False,
            "press_count": 1,
            "internal_layers": 4,
            "delivery_days": 6,
            "is_reorder": True,
        },
    },
    {
        "quote_no": "DEMO-RFQ-005",
        "customer": "Apex Robotics",
        "days_ago": 12,
        "status": "approved",
        "quote_outcome": "no_response",
        "notes": "Demo: no response after quote sent; shows sales follow-up tracking.",
        "lost_reason": "no_response",
        "lost_reason_note": "Followed up twice after formal quote.",
        "spec": {
            "layer": 4,
            "material": "FR-4",
            "qty": 40,
            "issue_ratio": 1.15,
            "length_mm": 70,
            "width_mm": 40,
            "thickness_mm": 1.6,
            "pitch_mm": 0.6,
            "trace_to_hole_mil": 5,
            "line_space_mil": 5,
            "min_hole_mil": 10,
            "surface_finish": "HASL",
            "enig": False,
            "vip": False,
            "back_drill": False,
            "press_count": 1,
            "internal_layers": 2,
            "delivery_days": 5,
        },
    },
]


def upsert_customers(session) -> dict[str, db.Customer]:
    customers = {}
    for item in CUSTOMERS:
        customer = (
            session.query(db.Customer)
            .filter(db.Customer.company_name == item["company_name"])
            .first()
        )
        if customer is None:
            customer = db.Customer(company_name=item["company_name"])
            session.add(customer)
        customer.contact = item["contact"]
        customer.phone = item["phone"]
        customer.email = item["email"]
        customer.common_specs = item["common_specs"]
        customers[customer.company_name] = customer
    session.flush()
    return customers


def upsert_quotes(session, customers: dict[str, db.Customer]) -> int:
    now = datetime.utcnow()
    owner = session.query(db.User).order_by(db.User.id.asc()).first()
    count = 0

    for item in DEMO_QUOTES:
        spec = item["spec"]
        result = calculate_quote(spec)
        if result.get("status") != "success":
            raise RuntimeError(f"{item['quote_no']} failed: {result}")

        normalized = normalized_quote_fields(spec, result)
        total = result["total"]
        final_price = round(total * item.get("final_price_multiplier", 1.0), 2)
        actual_cost = round(total * item.get("actual_cost_multiplier", 0.7), 2)
        competitor_price = None
        if item.get("competitor_price_multiplier"):
            competitor_price = round(total * item["competitor_price_multiplier"], 2)
        created_at = now - timedelta(days=item["days_ago"])

        quote = (
            session.query(db.QuoteHistory)
            .filter(db.QuoteHistory.quote_no == item["quote_no"])
            .first()
        )
        if quote is None:
            quote = db.QuoteHistory(quote_no=item["quote_no"])
            session.add(quote)

        quote.source_channel_id = f"demo:{item['quote_no']}"
        quote.customer_id = customers[item["customer"]].id
        quote.layer = normalized.get("layer") or spec.get("layer")
        quote.material = spec.get("material")
        quote.length_mm = spec.get("length_mm")
        quote.width_mm = spec.get("width_mm")
        quote.qty = spec.get("qty")
        quote.issue_ratio = result.get("issue_ratio", 1.0)
        quote.total = total
        quote.unit_price = result["unit_price"]
        quote.status = item["status"]
        quote.notes = item["notes"]
        quote.spec_json = spec
        quote.breakdown_json = result
        quote.rfq_received_at = created_at
        quote.quote_sent_at = created_at + timedelta(hours=4)
        quote.area_in2 = normalized.get("area_in2")
        quote.board_thickness_mm = normalized.get("board_thickness_mm")
        quote.copper_weight_oz = normalized.get("copper_weight_oz")
        quote.surface_finish = normalized.get("surface_finish")
        quote.gold_thickness_uin = normalized.get("gold_thickness_uin")
        quote.delivery_days = normalized.get("delivery_days")
        quote.estimated_cost = actual_cost
        quote.estimated_margin_pct = calculate_margin(total, actual_cost)
        quote.quote_outcome = item["quote_outcome"]
        quote.final_price = final_price if item["quote_outcome"] in {"won", "lost"} else None
        quote.actual_cost = actual_cost if item["quote_outcome"] == "won" else None
        quote.actual_margin_pct = (
            calculate_margin(final_price, actual_cost)
            if item["quote_outcome"] == "won"
            else None
        )
        quote.lost_reason = item.get("lost_reason")
        quote.lost_reason_note = item.get("lost_reason_note")
        quote.competitor_name = item.get("competitor_name")
        quote.competitor_price = competitor_price
        quote.production_lead_time_actual = item.get("actual_production_days")
        quote.currency = "NTD"
        quote.source_channel = "web"
        quote.product_type = "pcb"
        quote.pricing_version = "demo-v1"
        quote.created_by_user_id = owner.id if owner else None
        quote.updated_by_user_id = owner.id if owner else None
        quote.created_at = created_at
        count += 1

    return count


def main() -> None:
    db.init_db()
    session = db.SessionLocal()
    try:
        customers = upsert_customers(session)
        quote_count = upsert_quotes(session, customers)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print(f"Seeded {len(customers)} demo customers and {quote_count} demo RFQs.")


if __name__ == "__main__":
    main()
