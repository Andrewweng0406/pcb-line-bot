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


def test_dashboard_shows_stats(temp_db):
    temp_db.save_quote(
        "line:U1",
        {"layer": 6, "qty": 1},
        {"status": "success", "total": 100.0, "unit_price": 100.0},
    )
    db = temp_db.SessionLocal()
    quote = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first()
    db.close()
    client = _logged_in_client(temp_db)

    response = client.get("/")
    assert response.status_code == 200
    assert "Quote" in response.text
    assert "Pipeline Snapshot" in response.text
    assert "Active Quotes" in response.text
    assert "Recent RFQs" in response.text
    assert f"/quotes/{quote.id}" in response.text


def test_dashboard_shows_pipeline_outcomes(temp_db):
    temp_db.save_quote(
        "line:U1",
        {"layer": 6, "qty": 1},
        {"status": "success", "total": 100.0, "unit_price": 100.0},
    )
    temp_db.save_quote(
        "line:U2",
        {"layer": 8, "qty": 1},
        {"status": "success", "total": 200.0, "unit_price": 200.0},
    )
    db = temp_db.SessionLocal()
    quotes = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.asc()).all()
    quotes[0].quote_outcome = "won"
    quotes[1].quote_outcome = "lost"
    db.commit()
    db.close()
    client = _logged_in_client(temp_db)

    response = client.get("/")

    assert response.status_code == 200
    assert "Won Quotes / Lost Quotes" in response.text
    assert "50%" in response.text
