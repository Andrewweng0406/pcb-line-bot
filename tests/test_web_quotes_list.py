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


def test_quotes_list_shows_all_quotes(temp_db):
    temp_db.save_quote("line:U1", {"layer": 6, "material": "FR4", "qty": 1}, {"status": "success", "total": 100.0, "unit_price": 100.0})
    temp_db.save_quote("line:U1", {"layer": 8, "material": "Megtron6", "qty": 1}, {"status": "success", "total": 200.0, "unit_price": 200.0})

    client = _logged_in_client(temp_db)
    response = client.get("/quotes")

    assert response.status_code == 200
    assert "FR4" in response.text
    assert "Megtron6" in response.text
    assert "待審核" in response.text  # status shown as its Chinese label, not "pending"


def test_quotes_list_filters_by_layer(temp_db):
    temp_db.save_quote("line:U1", {"layer": 6, "material": "FR4", "qty": 1}, {"status": "success", "total": 100.0, "unit_price": 100.0})
    temp_db.save_quote("line:U1", {"layer": 8, "material": "Megtron6", "qty": 1}, {"status": "success", "total": 200.0, "unit_price": 200.0})

    client = _logged_in_client(temp_db)
    response = client.get("/quotes?layer=6")

    assert "FR4" in response.text
    assert "Megtron6" not in response.text
