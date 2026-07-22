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


def test_customers_list_and_create(temp_db):
    client = _logged_in_client(temp_db)

    response = client.post(
        "/customers",
        data={"company_name": "ABC Corp", "contact": "Jane", "phone": "0912345678", "email": "jane@abc.com"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    response = client.get("/customers")
    assert response.status_code == 200
    assert "ABC Corp" in response.text
    assert "Jane" in response.text
