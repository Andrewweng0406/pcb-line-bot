from fastapi.testclient import TestClient

from app.core.auth import hash_password


def test_api_requires_login(temp_db):
    from app.main import app
    client = TestClient(app)

    response = client.get("/api/quotes")
    assert response.status_code == 401


def test_api_works_when_logged_in(temp_db):
    from app.main import app
    client = TestClient(app)

    db = temp_db.SessionLocal()
    user = temp_db.User(email="staff@example.com", password_hash=hash_password("hunter2"), role="manager")
    db.add(user)
    db.commit()
    db.close()

    client.post("/login", data={"email": "staff@example.com", "password": "hunter2"})
    response = client.get("/api/quotes")
    assert response.status_code == 200


def test_api_patch_records_updated_by(temp_db):
    from app.main import app
    client = TestClient(app)

    db = temp_db.SessionLocal()
    user = temp_db.User(email="staff@example.com", password_hash=hash_password("hunter2"), role="manager")
    db.add(user)
    db.commit()
    db.close()

    temp_db.save_quote("line:U1", {"layer": 6, "qty": 1}, {"status": "success", "total": 100.0, "unit_price": 100.0})
    db = temp_db.SessionLocal()
    quote_id = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first().id
    db.close()

    client.post("/login", data={"email": "staff@example.com", "password": "hunter2"})
    response = client.patch(f"/api/quotes/{quote_id}", json={"status": "approved"})
    assert response.status_code == 200

    db = temp_db.SessionLocal()
    quote = db.query(temp_db.QuoteHistory).filter(temp_db.QuoteHistory.id == quote_id).first()
    assert quote.status == "approved"
    assert quote.updated_by.email == "staff@example.com"
    db.close()


def test_api_patch_updates_outcome_and_actual_margin(temp_db):
    from app.main import app
    client = TestClient(app)

    db = temp_db.SessionLocal()
    user = temp_db.User(email="staff@example.com", password_hash=hash_password("hunter2"), role="manager")
    db.add(user)
    db.commit()
    db.close()

    temp_db.save_quote("line:U1", {"layer": 6, "qty": 1, "area_inch": 10}, {"status": "success", "total": 100.0, "unit_price": 100.0})
    db = temp_db.SessionLocal()
    quote_id = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first().id
    db.close()

    client.post("/login", data={"email": "staff@example.com", "password": "hunter2"})
    response = client.patch(
        f"/api/quotes/{quote_id}",
        json={"quote_outcome": "won", "final_price": 100, "actual_cost": 75},
    )
    assert response.status_code == 200

    db = temp_db.SessionLocal()
    quote = db.query(temp_db.QuoteHistory).filter(temp_db.QuoteHistory.id == quote_id).first()
    assert quote.quote_outcome == "won"
    assert quote.actual_margin_pct == 0.25
    db.close()


def test_api_returns_similar_quotes_and_historical_summary(temp_db):
    from app.main import app
    client = TestClient(app)

    db = temp_db.SessionLocal()
    user = temp_db.User(email="staff@example.com", password_hash=hash_password("hunter2"))
    db.add(user)
    db.commit()
    db.close()

    temp_db.save_quote(
        "web:1",
        {
            "layer": 6,
            "material": "FR4",
            "qty": 10,
            "length_mm": 100,
            "width_mm": 100,
            "enig": True,
            "thickness_mm": 1.6,
            "copper_weight": "1oz",
            "delivery_days": 7,
        },
        {"status": "success", "total": 1000, "unit_price": 100},
    )
    temp_db.save_quote(
        "web:1",
        {
            "layer": 6,
            "material": "FR4",
            "qty": 10,
            "length_mm": 102,
            "width_mm": 100,
            "enig": True,
            "thickness_mm": 1.6,
            "copper_weight": "1oz",
            "delivery_days": 7,
        },
        {"status": "success", "total": 1100, "unit_price": 110},
    )
    db = temp_db.SessionLocal()
    quotes = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.asc()).all()
    quotes[0].quote_outcome = "won"
    quote_id = quotes[1].id
    db.commit()
    db.close()

    client.post("/login", data={"email": "staff@example.com", "password": "hunter2"})

    similar = client.get(f"/api/quotes/{quote_id}/similar")
    assert similar.status_code == 200
    assert similar.json()[0]["similarity"] > 80

    summary = client.get(f"/api/quotes/{quote_id}/historical-summary")
    assert summary.status_code == 200
    assert summary.json()["candidate_count"] == 1
    assert summary.json()["comparable_count"] == 0
    assert summary.json()["limited_data"] is True
    assert "average_quoted_unit_price" not in summary.json()
    assert "missing_currency" in similar.json()[0]["exclusions"]
    assert len(similar.json()[0]["differences"]) == 16


def test_api_returns_business_analytics(temp_db):
    from app.main import app
    client = TestClient(app)

    db = temp_db.SessionLocal()
    user = temp_db.User(email="staff@example.com", password_hash=hash_password("hunter2"))
    customer = temp_db.Customer(company_name="ABC Corp")
    db.add_all([user, customer])
    db.commit()
    db.refresh(customer)
    customer_id = customer.id
    db.close()

    temp_db.save_quote(
        "web:1",
        {"layer": 6, "qty": 1, "area_inch": 10},
        {"status": "success", "total": 100, "unit_price": 100},
        customer_id=customer_id,
    )
    db = temp_db.SessionLocal()
    quote = db.query(temp_db.QuoteHistory).first()
    quote.quote_outcome = "won"
    quote.final_price = 100
    db.commit()
    db.close()

    client.post("/login", data={"email": "staff@example.com", "password": "hunter2"})

    outcomes = client.get("/api/stats/outcomes")
    assert outcomes.status_code == 200
    assert outcomes.json()["counts"]["won"] == 1

    trends = client.get("/api/stats/pricing-trends")
    assert trends.status_code == 200
    assert trends.json()[0]["rfq_count"] == 1

    customers = client.get("/api/stats/top-customers")
    assert customers.status_code == 200
    assert customers.json()[0]["company_name"] == "ABC Corp"
