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
    user = temp_db.User(email="staff@example.com", password_hash=hash_password("hunter2"))
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
    user = temp_db.User(email="staff@example.com", password_hash=hash_password("hunter2"))
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
