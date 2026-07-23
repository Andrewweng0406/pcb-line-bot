from fastapi.testclient import TestClient


def _client():
    from app.main import app
    return TestClient(app)


def test_register_page_loads(temp_db):
    client = _client()
    response = client.get("/register")
    assert response.status_code == 200
    assert "邀請碼" in response.text


def test_register_with_correct_invite_code_creates_account_and_logs_in(temp_db, monkeypatch):
    import app.core.config as config_module
    config_module.settings.INVITE_CODE = "the-real-code"

    client = _client()
    response = client.post(
        "/register",
        data={
            "email": "newstaff@example.com",
            "password": "hunter2",
            "invite_code": "the-real-code",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "session" in response.cookies

    db = temp_db.SessionLocal()
    user = db.query(temp_db.User).filter(temp_db.User.email == "newstaff@example.com").first()
    assert user is not None
    assert user.password_hash != "hunter2"
    db.close()


def test_register_with_wrong_invite_code_is_rejected(temp_db):
    import app.core.config as config_module
    config_module.settings.INVITE_CODE = "the-real-code"

    client = _client()
    response = client.post(
        "/register",
        data={
            "email": "newstaff@example.com",
            "password": "hunter2",
            "invite_code": "wrong-code",
        },
    )
    assert response.status_code == 400
    assert 'value="newstaff@example.com"' in response.text  # email preserved so the user doesn't retype it

    db = temp_db.SessionLocal()
    user = db.query(temp_db.User).filter(temp_db.User.email == "newstaff@example.com").first()
    assert user is None
    db.close()


def test_register_with_existing_email_is_rejected(temp_db):
    import app.core.config as config_module
    config_module.settings.INVITE_CODE = "the-real-code"

    from app.core.auth import hash_password
    db = temp_db.SessionLocal()
    db.add(temp_db.User(email="existing@example.com", password_hash=hash_password("x")))
    db.commit()
    db.close()

    client = _client()
    response = client.post(
        "/register",
        data={
            "email": "existing@example.com",
            "password": "hunter2",
            "invite_code": "the-real-code",
        },
    )
    assert response.status_code == 400
