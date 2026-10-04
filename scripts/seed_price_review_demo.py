"""Create clearly labelled synthetic price review cases in local or staging data.

Usage: python scripts/seed_price_review_demo.py
Existing rows are preserved. This command refuses Railway production.
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core import database as db  # noqa: E402
from app.rfq_normalization import normalized_quote_fields  # noqa: E402


def seed_cases(session) -> dict:
    anchor = datetime(2026, 10, 3, 12)
    spec = {
        "layer": 6, "material": "FR4", "qty": 10,
        "length_mm": 100, "width_mm": 100, "area_inch": 15.5,
        "thickness_mm": 1.6, "copper_weight": "1oz", "delivery_days": 7,
        "surface_finish": "ENIG", "enig_thickness_uinch": 5,
        "enig": True, "vip": False, "impedance": False, "back_drill": False, "bvh": False,
    }
    fixtures = []
    for index, price in enumerate((96, 98, 100, 102, 104), 1):
        fixtures.append((f"SYNTH-PRICE-REF-{index}", price, anchor-timedelta(days=index+2), {
            **spec, "qty": 15 if index == 4 else 10,
            "area_inch": 18 if index == 4 else 15.5,
        }))
    fixtures.extend([
        ("SYNTH-PRICE-NORMAL", 100, anchor-timedelta(days=1), spec),
        ("SYNTH-PRICE-HIGH", 160, anchor, spec),
    ])
    sparse = {**spec, "layer": 12, "material": "MEGTRON 6"}
    fixtures.extend([
        ("SYNTH-SPARSE-REF-1", 98, anchor-timedelta(days=4), sparse),
        ("SYNTH-SPARSE-REF-2", 102, anchor-timedelta(days=3), sparse),
        ("SYNTH-PRICE-SPARSE", 160, anchor, sparse),
    ])
    ids = {}
    for name, price, created, fields in fixtures:
        existing = session.query(db.QuoteHistory).filter(db.QuoteHistory.quote_no == name).first()
        if existing:
            ids[name] = existing.id
            continue
        normalized = normalized_quote_fields(fields)
        item = db.QuoteHistory(
            quote_no=name, source_channel_id=f"demo:{name}", source_channel="demo",
            layer=fields["layer"], material=fields["material"], qty=fields["qty"],
            length_mm=100, width_mm=100, issue_ratio=1, total=price*fields["qty"],
            unit_price=price, currency="NTD", pricing_version="synthetic-price-v1",
            status="pending", quote_outcome="pending", product_type="pcb",
            notes="Synthetic interview scenario. Prices are illustrative, not customer transactions.",
            spec_json={**fields, "synthetic_demo": True},
            breakdown_json={"synthetic_demo": True}, created_at=created,
            rfq_received_at=created, quote_sent_at=created,
            **{field: normalized[field] for field in (
                "area_in2", "board_thickness_mm", "copper_weight_oz", "surface_finish",
                "gold_thickness_uin", "delivery_days",
            )},
        )
        session.add(item)
        session.flush()
        ids[name] = item.id
    return {name: ids[name] for name in ("SYNTH-PRICE-NORMAL", "SYNTH-PRICE-HIGH", "SYNTH-PRICE-SPARSE")}


def main():
    if os.getenv("RAILWAY_ENVIRONMENT_NAME", "").lower() == "production":
        raise SystemExit("Synthetic price review fixtures are limited to local and staging environments.")
    db.init_db()
    with db.SessionLocal() as session:
        cases = seed_cases(session)
        session.commit()
    print(cases)


if __name__ == "__main__":
    main()
