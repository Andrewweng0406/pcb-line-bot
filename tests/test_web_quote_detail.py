from fastapi.testclient import TestClient

from app.core.auth import hash_password


def _logged_in_client(temp_db):
    from app.main import app
    client = TestClient(app)
    db = temp_db.SessionLocal()
    user = temp_db.User(email="staff@example.com", password_hash=hash_password("hunter2"))
    db.add(user)
    db.commit()
    db.close()
    client.post("/login", data={"email": "staff@example.com", "password": "hunter2"})
    return client


def test_quote_detail_shows_spec_and_breakdown(temp_db):
    temp_db.save_quote(
        "line:U1",
        {"layer": 6, "material": "FR4", "qty": 9},
        {"status": "success", "total": 12345.0, "unit_price": 1371.67, "issue_ratio": 1.0, "explanations": ["工程費: 80000"]},
    )
    db = temp_db.SessionLocal()
    quote_id = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first().id
    db.close()

    client = _logged_in_client(temp_db)
    response = client.get(f"/quotes/{quote_id}")

    assert response.status_code == 200
    assert "12,345" in response.text
    assert "待審核" in response.text


def test_quote_detail_shows_historical_intelligence(temp_db):
    temp_db.save_quote(
        "web:1",
        {"layer": 6, "material": "FR4", "qty": 10, "length_mm": 100, "width_mm": 100, "enig": True},
        {"status": "success", "total": 1000, "unit_price": 100},
    )
    temp_db.save_quote(
        "web:1",
        {"layer": 6, "material": "FR4", "qty": 10, "length_mm": 102, "width_mm": 100, "enig": True},
        {"status": "success", "total": 1100, "unit_price": 110},
    )
    db = temp_db.SessionLocal()
    quote_id = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.asc()).first().id
    db.close()

    client = _logged_in_client(temp_db)
    response = client.get(f"/quotes/{quote_id}")

    assert response.status_code == 200
    assert "Historical Intelligence" in response.text
    assert "Similar Quotes" in response.text
    assert "Similar RFQs" in response.text


def test_quote_detail_missing_returns_404(temp_db):
    client = _logged_in_client(temp_db)
    response = client.get("/quotes/999")
    assert response.status_code == 404


def test_update_quote_status_and_notes(temp_db):
    temp_db.save_quote("line:U1", {"layer": 6, "qty": 1}, {"status": "success", "total": 100.0, "unit_price": 100.0})
    db = temp_db.SessionLocal()
    quote_id = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first().id
    db.close()


def test_update_quote_outcome_won_fields_and_margin(temp_db):
    temp_db.save_quote("web:1", {"layer": 6, "qty": 1, "area_inch": 10}, {"status": "success", "total": 100.0, "unit_price": 100.0})
    db = temp_db.SessionLocal()
    quote_id = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first().id
    db.close()

    client = _logged_in_client(temp_db)
    response = client.post(
        f"/quotes/{quote_id}/update",
        data={
            "status": "pending",
            "notes": "",
            "quote_outcome": "won",
            "final_price": "120",
            "actual_cost": "90",
            "production_lead_time_actual": "8",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    db = temp_db.SessionLocal()
    quote = db.query(temp_db.QuoteHistory).filter(temp_db.QuoteHistory.id == quote_id).first()
    assert quote.status == "pending"
    assert quote.quote_outcome == "won"
    assert quote.final_price == 120
    assert quote.actual_cost == 90
    assert quote.production_lead_time_actual == 8
    assert quote.actual_margin_pct == 0.25
    db.close()


def test_update_quote_outcome_lost_without_reason_and_with_competitor_data(temp_db):
    temp_db.save_quote("web:1", {"layer": 6, "qty": 1, "area_inch": 10}, {"status": "success", "total": 100.0, "unit_price": 100.0})
    db = temp_db.SessionLocal()
    quote_id = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first().id
    db.close()

    client = _logged_in_client(temp_db)
    response = client.post(
        f"/quotes/{quote_id}/update",
        data={
            "status": "approved",
            "notes": "still operationally approved",
            "quote_outcome": "lost",
            "lost_reason": "",
            "lost_reason_note": "customer paused",
            "competitor_name": "Other Fab",
            "competitor_price": "95",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    db = temp_db.SessionLocal()
    quote = db.query(temp_db.QuoteHistory).filter(temp_db.QuoteHistory.id == quote_id).first()
    assert quote.status == "approved"
    assert quote.quote_outcome == "lost"
    assert quote.lost_reason is None
    assert quote.lost_reason_note == "customer paused"
    assert quote.competitor_name == "Other Fab"
    assert quote.competitor_price == 95
    db.close()


def test_status_update_does_not_clear_existing_outcome_data(temp_db):
    temp_db.save_quote("web:1", {"layer": 6, "qty": 1, "area_inch": 10}, {"status": "success", "total": 100.0, "unit_price": 100.0})
    db = temp_db.SessionLocal()
    quote = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first()
    quote.quote_outcome = "won"
    quote.final_price = 120
    quote.actual_cost = 90
    quote.actual_margin_pct = 0.25
    quote_id = quote.id
    db.commit()
    db.close()

    client = _logged_in_client(temp_db)
    response = client.post(
        f"/quotes/{quote_id}/update",
        data={"status": "ordered", "notes": "ordered now"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    db = temp_db.SessionLocal()
    quote = db.query(temp_db.QuoteHistory).filter(temp_db.QuoteHistory.id == quote_id).first()
    assert quote.status == "ordered"
    assert quote.quote_outcome == "won"
    assert quote.final_price == 120
    assert quote.actual_margin_pct == 0.25
    db.close()


def test_quote_missing_spec_json_renders_without_error(temp_db):
    """Pre-migration, LINE-submitted quotes may predate spec_json/breakdown_json.
    Simulate that by inserting a row with those columns left null.
    """
    db = temp_db.SessionLocal()
    quote = temp_db.QuoteHistory(
        source_channel_id="line:U1", layer=6, material="FR4", qty=1, total=100.0, unit_price=100.0
    )
    db.add(quote)
    db.commit()
    db.refresh(quote)
    quote_id = quote.id
    db.close()

    client = _logged_in_client(temp_db)
    response = client.get(f"/quotes/{quote_id}")
    assert response.status_code == 200


def test_export_excel_route_downloads_when_spec_present(temp_db):
    temp_db.save_quote("line:U1", {"layer": 6, "qty": 1}, {"status": "success", "total": 100.0, "unit_price": 100.0})
    db = temp_db.SessionLocal()
    quote_id = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first().id
    db.close()

    client = _logged_in_client(temp_db)
    response = client.get(f"/quotes/{quote_id}/export/excel", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/download/exports/")


def test_export_excel_route_404s_without_spec(temp_db):
    db = temp_db.SessionLocal()
    quote = temp_db.QuoteHistory(source_channel_id="line:U1", layer=6, qty=1, total=100.0, unit_price=100.0)
    db.add(quote)
    db.commit()
    db.refresh(quote)
    quote_id = quote.id
    db.close()

    client = _logged_in_client(temp_db)
    response = client.get(f"/quotes/{quote_id}/export/excel", follow_redirects=False)
    assert response.status_code == 404
