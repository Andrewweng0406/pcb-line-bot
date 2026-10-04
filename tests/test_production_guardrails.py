import io
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.auth import hash_password, sign_export
from app.extraction_review import attach_extraction_review, build_extraction_review


def login(temp_db):
    from app.main import app
    with temp_db.SessionLocal() as session:
        session.add(temp_db.User(email="guard@example.com", password_hash=hash_password("test-password"), role="manager"))
        session.commit()
    client = TestClient(app)
    client.post("/login", data={"email": "guard@example.com", "password": "test-password"})
    return client


def test_api_cannot_bypass_review_or_corrupt_calculated_price(temp_db):
    spec = {"layer": 6, "qty": 10, "area_inch": 10}
    spec = attach_extraction_review(spec, build_extraction_review(spec, raw_input="6L qty 10"))
    temp_db.save_quote("web:1", spec, {"status": "success", "total": 1000, "unit_price": 100})
    with temp_db.SessionLocal() as session:
        quote_id = session.query(temp_db.QuoteHistory).first().id
    client = login(temp_db)
    for status in ("approved", "ordered"):
        assert client.patch(f"/api/quotes/{quote_id}", json={"status": status}).status_code == 409
        assert client.post(f"/quotes/{quote_id}/update", data={"status": status}).status_code == 409
    for status in ("invented", [], None):
        assert client.patch(f"/api/quotes/{quote_id}", json={"status": status}).status_code == 400
    assert client.patch(f"/api/quotes/{quote_id}", json={"total": 2500}).status_code == 400
    assert client.patch(f"/api/quotes/{quote_id}", json={"final_price": 2500}).status_code == 200
    with temp_db.SessionLocal() as session:
        quote = session.get(temp_db.QuoteHistory, quote_id)
        assert quote.status == "pending"
        assert quote.total == quote.breakdown_json["total"] == 1000
        assert quote.unit_price == 100 and quote.final_price == 2500


def test_public_ai_and_download_routes_are_protected(temp_db, monkeypatch, tmp_path):
    from app.main import app
    from app.core.config import settings
    monkeypatch.setattr(settings, "EXPORT_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "DEBUG", False)
    (tmp_path / "test.xlsx").write_bytes(b"test-export")
    client = TestClient(app)
    assert client.get("/download/exports/test.xlsx").status_code == 401
    assert client.get("/quote_text", params={"text": "6L"}).status_code == 401
    assert client.get("/image_test").status_code == 404
    token = sign_export("test.xlsx")
    assert client.get("/download/exports/test.xlsx", params={"token": token}).content == b"test-export"
    assert client.get("/download/exports/other.xlsx", params={"token": token}).status_code == 401
    assert client.get("/download/exports/test.xlsx", params={"token": token + "x"}).status_code == 401


def test_cross_site_mutations_are_rejected(temp_db):
    client = login(temp_db)
    response = client.post("/quotes/1/review", headers={"Origin": "https://attacker.example"})
    assert response.status_code == 403


def test_https_login_cookie_is_secure(temp_db):
    client = login(temp_db)
    response = client.post("https://testserver/login", data={"email": "guard@example.com", "password": "test-password"}, follow_redirects=False)
    cookie = response.headers["set-cookie"]
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie


def test_image_upload_validates_bytes_and_preserves_evidence(temp_db, monkeypatch, tmp_path):
    import app.web as web
    monkeypatch.setattr(web.settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(web, "parse_pcb_image", lambda path: {"layer": 6, "qty": 10})
    client = login(temp_db)
    assert client.post("/quotes/new/ai-assist", files={"photo": ("fake.jpg", b"not-an-image", "image/jpeg")}).status_code == 400
    monkeypatch.setattr(web.settings, "MAX_UPLOAD_SIZE", 5)
    assert client.post("/quotes/new/ai-assist", files={"photo": ("big.jpg", b"123456", "image/jpeg")}).status_code == 413
    monkeypatch.setattr(web.settings, "MAX_UPLOAD_SIZE", 100000)
    stream = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(stream, format="PNG")
    original = stream.getvalue()
    response = client.post("/quotes/new/ai-assist", files={"photo": ("spec.png", original, "image/png")})
    assert response.status_code == 200
    files = list(tmp_path.glob("web_*.png"))
    assert len(files) == 1 and files[0].read_bytes() == original
    url = f"/rfq-images/{files[0].name}"
    assert url in response.text
    assert client.get(url).content == original
    from app.main import app
    assert TestClient(app).get(url).status_code == 401
    with temp_db.SessionLocal() as session:
        session.add(temp_db.User(email="other@example.com", password_hash=hash_password("test-password")))
        session.commit()
    other = TestClient(app)
    other.post("/login", data={"email": "other@example.com", "password": "test-password"})
    assert other.get(url).status_code == 404


@pytest.mark.parametrize("text", ["Copper thickness 35um, no ENIG", "Board thickness 1.6mm, hole diameter 100um", "No ENIG; minimum pitch 20um"])
def test_parser_does_not_turn_unrelated_units_into_gold(text, monkeypatch):
    import app.ai_parser as parser
    monkeypatch.setenv("OPENAI_API_KEY", "stub")
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"enig":false,"enig_thickness_uinch":null}'))])
    monkeypatch.setattr(parser.client.chat.completions, "create", lambda **kwargs: response)
    assert parser.parse_pcb_text(text) == {"enig": False, "enig_thickness_uinch": None}
