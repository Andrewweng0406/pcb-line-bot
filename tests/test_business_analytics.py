from datetime import datetime

from app.business_analytics import (
    get_customer_analytics,
    get_outcome_stats,
    get_pricing_trends,
)


def test_outcome_stats_and_win_rate(temp_db):
    temp_db.save_quote("web:1", {"layer": 6, "qty": 1, "area_inch": 10}, {"status": "success", "total": 100, "unit_price": 100})
    temp_db.save_quote("web:1", {"layer": 6, "qty": 1, "area_inch": 10}, {"status": "success", "total": 100, "unit_price": 100})
    db = temp_db.SessionLocal()
    quotes = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.asc()).all()
    quotes[0].quote_outcome = "won"
    quotes[1].quote_outcome = "lost"
    db.commit()

    stats = get_outcome_stats(db, temp_db.QuoteHistory)
    db.close()

    assert stats["counts"]["won"] == 1
    assert stats["counts"]["lost"] == 1
    assert stats["win_rate"] == 0.5


def test_pricing_trends_groups_by_month_and_average_margin(temp_db):
    temp_db.save_quote("web:1", {"layer": 6, "qty": 1, "area_inch": 10}, {"status": "success", "total": 100, "unit_price": 100})
    temp_db.save_quote("web:1", {"layer": 6, "qty": 1, "area_inch": 10}, {"status": "success", "total": 300, "unit_price": 300})
    db = temp_db.SessionLocal()
    quotes = db.query(temp_db.QuoteHistory).all()
    for quote in quotes:
        quote.rfq_received_at = datetime(2026, 7, 1)
    quotes[0].actual_margin_pct = 0.2
    quotes[1].estimated_margin_pct = 0.4
    db.commit()

    trends = get_pricing_trends(db, temp_db.QuoteHistory)
    db.close()

    assert trends[0]["period"] == "2026-07"
    assert trends[0]["rfq_count"] == 2
    assert trends[0]["average_quote_value"] == 200
    assert trends[0]["average_margin_pct"] == 0.3


def test_customer_analytics(temp_db):
    db = temp_db.SessionLocal()
    customer = temp_db.Customer(company_name="ABC Corp")
    db.add(customer)
    db.commit()
    db.refresh(customer)
    customer_id = customer.id
    db.close()

    temp_db.save_quote("web:1", {"layer": 6, "qty": 1, "area_inch": 10}, {"status": "success", "total": 100, "unit_price": 100}, customer_id=customer_id)
    temp_db.save_quote("web:1", {"layer": 6, "qty": 1, "area_inch": 10}, {"status": "success", "total": 200, "unit_price": 200}, customer_id=customer_id)
    db = temp_db.SessionLocal()
    quotes = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.asc()).all()
    quotes[0].quote_outcome = "won"
    quotes[0].final_price = 120
    quotes[1].quote_outcome = "lost"
    db.commit()

    rows = get_customer_analytics(db, temp_db.Customer, temp_db.QuoteHistory)
    db.close()

    row = rows[0]
    assert row["company_name"] == "ABC Corp"
    assert row["total_rfqs"] == 2
    assert row["won"] == 1
    assert row["lost"] == 1
    assert row["win_rate"] == 0.5
    assert row["total_won_value"] == 120
