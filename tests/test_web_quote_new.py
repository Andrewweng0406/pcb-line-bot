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


def test_new_quote_form_loads(temp_db):
    client = _logged_in_client(temp_db)
    response = client.get("/quotes/new")
    assert response.status_code == 200
    assert "新增報價" in response.text


def test_submitting_quote_creates_row_and_links_customer(temp_db):
    client = _logged_in_client(temp_db)

    response = client.post(
        "/quotes/new",
        data={
            "layer": 6,
            "qty": 9,
            "material": "FR4",
            "length_mm": 100,
            "width_mm": 100,
            "issue_ratio": 1.0,
            "company_name": "ABC Corp",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/quotes"

    db = temp_db.SessionLocal()
    quote = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first()
    assert quote.layer == 6
    assert quote.customer.company_name == "ABC Corp"
    assert quote.created_by.email == "staff@example.com"
    assert quote.spec_json["material"] == "FR4"
    db.close()


def test_submitting_invalid_quote_shows_error(temp_db):
    client = _logged_in_client(temp_db)

    response = client.post(
        "/quotes/new",
        data={"layer": 999, "qty": 1},
    )
    assert response.status_code == 400
    assert "暫不支持" in response.text


def test_submitting_quote_with_blank_optional_fields_succeeds(temp_db):
    """A real browser submits empty text inputs as "" rather than omitting
    them, which used to 422 the request (Optional[float] Form fields can't
    parse ""). This reproduces exactly that shape.
    """
    client = _logged_in_client(temp_db)

    response = client.post(
        "/quotes/new",
        data={
            "layer": 6,
            "qty": 9,
            "material": "FR4",
            "length_mm": 100,
            "width_mm": 100,
            "issue_ratio": 1.0,
            "enig_thickness_uinch": "",
            "thickness_mm": "",
            "pitch_mm": "",
            "delivery_days": "",
            "company_name": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
