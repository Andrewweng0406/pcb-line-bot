from fastapi.testclient import TestClient

from app.core.auth import hash_password


def _make_client(temp_db):
    from app.main import app
    return TestClient(app)


def _create_user(temp_db, email="staff@example.com", password="hunter2"):
    db = temp_db.SessionLocal()
    user = temp_db.User(email=email, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


def test_dashboard_redirects_when_logged_out(temp_db):
    client = _make_client(temp_db)
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_login_with_correct_credentials_sets_session_and_redirects(temp_db):
    _create_user(temp_db)
    client = _make_client(temp_db)

    response = client.post(
        "/login",
        data={"email": "staff@example.com", "password": "hunter2"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "session" in response.cookies


def test_login_with_wrong_password_shows_error(temp_db):
    _create_user(temp_db)
    client = _make_client(temp_db)

    response = client.post(
        "/login",
        data={"email": "staff@example.com", "password": "wrong"},
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert "session" not in response.cookies


def test_dashboard_loads_when_logged_in(temp_db):
    _create_user(temp_db)
    client = _make_client(temp_db)
    client.post("/login", data={"email": "staff@example.com", "password": "hunter2"})

    response = client.get("/")
    assert response.status_code == 200


def test_logout_clears_session(temp_db):
    _create_user(temp_db)
    client = _make_client(temp_db)
    client.post("/login", data={"email": "staff@example.com", "password": "hunter2"})

    client.get("/logout")
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
