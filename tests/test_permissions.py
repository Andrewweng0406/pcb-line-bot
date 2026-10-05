import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from app.core.auth import hash_password
from app.core.permissions import can


def role_client(db, role):
    from app.main import app
    with db.SessionLocal() as session:
        user = db.User(email=f"{role}@example.com", password_hash=hash_password("test-password"), role=role)
        session.add(user)
        session.commit()
        user_id = user.id
    client = TestClient(app)
    client.post("/login", data={"email": f"{role}@example.com", "password": "test-password"})
    return client, user_id


def quote_id(db):
    from app.quote_engine import calculate_quote
    spec = {"layer": 6, "qty": 10, "area_inch": 10, "material": "FR4", "surface_finish": "OSP",
            "copper_weight": "1oz", "thickness_mm": 1.6, "pitch_mm": 0.4, "delivery_days": 7}
    db.save_quote("web:1", spec, calculate_quote(spec))
    with db.SessionLocal() as session:
        quote = session.query(db.QuoteHistory).first()
        quote.currency = "NTD"
        session.commit()
        return quote.id


@pytest.mark.parametrize("role", ["viewer", "staff", "manager", "admin"])
def test_role_matrix_and_web_api_parity(temp_db, role):
    qid = quote_id(temp_db)
    client, _ = role_client(temp_db, role)
    assert client.get(f"/api/quotes/{qid}").status_code == 200
    editor = role != "viewer"
    manager = role in {"manager", "admin"}
    assert client.patch(f"/api/quotes/{qid}", json={"notes": "note"}).status_code == (200 if editor else 403)
    assert client.post(f"/quotes/{qid}/update", data={"status": "pending", "notes": "note"}, follow_redirects=False).status_code == (303 if editor else 403)
    assert client.patch(f"/api/quotes/{qid}", json={"final_price": 900}).status_code == (200 if manager else 403)
    assert client.post(f"/quotes/{qid}/update", data={"status": "pending", "actual_cost": 700}, follow_redirects=False).status_code == (303 if manager else 403)
    assert client.patch(f"/api/quotes/{qid}", json={"status": "approved"}).status_code == (200 if manager else 403)
    assert client.post(f"/quotes/{qid}/update", data={"status": "ordered"}, follow_redirects=False).status_code == (303 if manager else 403)
    assert client.get(f"/quotes/{qid}/export/formal", follow_redirects=False).status_code == (303 if manager else 403)
    assert client.get(f"/quotes/{qid}/export/estimate", follow_redirects=False).status_code == (303 if manager else 403)
    assert client.delete(f"/api/quotes/{qid}").status_code == (200 if role == "admin" else 403)
    with temp_db.SessionLocal() as session:
        quote = session.get(temp_db.QuoteHistory, qid)
        if role == "viewer":
            assert quote.notes is None and quote.status == "pending" and quote.final_price is None
        elif role == "staff":
            assert quote.notes == "note" and quote.status == "pending" and quote.final_price is None


def test_viewer_cannot_write_through_other_entry_points(temp_db, monkeypatch):
    import app.web as web
    client, _ = role_client(temp_db, "viewer")
    qid = quote_id(temp_db)
    def forbidden_parser(*args):
        raise AssertionError("Unauthorized requests must not reach AI")
    monkeypatch.setattr(web, "parse_pcb_text", forbidden_parser)
    assert client.get("/quotes/new").status_code == 403
    assert client.post("/quotes/new", data={"layer": 6, "qty": 10}).status_code == 403
    assert client.post("/quotes/new/ai-assist", data={"spec_text": "6L"}).status_code == 403
    assert client.get("/quote_text", params={"text": "6L"}).status_code == 403
    assert client.get(f"/quotes/{qid}/revise").status_code == 403
    assert client.post(f"/quotes/{qid}/review").status_code == 403
    assert client.post("/customers", data={"company_name": "No"}).status_code == 403
    assert client.get("/import/quotes").status_code == 403
    page = client.get(f"/quotes/{qid}").text
    assert 'name="final_price"' not in page and 'name="status"' not in page
    assert f'href="/quotes/{qid}/revise"' not in page
    assert 'href="/quotes/new"' not in page


def test_staff_cannot_confirm_import_or_set_price_override(temp_db):
    client, _ = role_client(temp_db, "staff")
    upload = {"file": ("test.xlsx", b"not-a-workbook", "application/octet-stream")}
    assert client.post("/api/import/quotes/confirm", files=upload).status_code == 403
    assert client.post("/import/quotes", data={"action": "confirm"}, files=upload).status_code == 403
    assert client.post("/quotes/new", data={"layer": 6, "qty": 10, "back_drill_fee": "0"}).status_code == 403
    assert 'name="back_drill_fee"' not in client.get("/quotes/new").text
    assert "Confirm Import" not in client.get("/import/quotes").text
    qid = quote_id(temp_db)
    assert client.patch(f"/api/quotes/{qid}", json={"role": "admin"}).status_code == 400


def test_registration_cannot_choose_privileged_role(temp_db, monkeypatch):
    from app.main import app
    from app.core.config import settings
    monkeypatch.setattr(settings, "INVITE_CODE", "test-invite")
    client = TestClient(app)
    response = client.post("/register", data={"email": "new@example.com", "password": "test-password", "invite_code": "test-invite", "role": "admin"}, follow_redirects=False)
    assert response.status_code == 303
    with temp_db.SessionLocal() as session:
        assert session.query(temp_db.User).filter_by(email="new@example.com").one().role == "staff"
    assert not can(SimpleNamespace(role="unknown"), "read")
    assert not can(SimpleNamespace(), "approve")


def test_demotion_revokes_permissions_in_existing_session_and_is_audited(temp_db):
    sys.path.insert(0, "scripts")
    from set_user_role import set_user_role
    client, user_id = role_client(temp_db, "manager")
    qid = quote_id(temp_db)
    assert client.patch(f"/api/quotes/{qid}", json={"final_price": 900}).status_code == 200
    assert set_user_role("manager@example.com", "staff", "Approval responsibility transferred")
    assert client.patch(f"/api/quotes/{qid}", json={"final_price": 800}).status_code == 403
    with temp_db.SessionLocal() as session:
        user = session.get(temp_db.User, user_id)
        assert user.role_history[-1]["previous_role"] == "manager"
        assert user.role_history[-1]["role"] == "staff"
        assert session.get(temp_db.QuoteHistory, qid).final_price == 900
    assert not set_user_role("manager@example.com", "staff", "Same assignment")
    with pytest.raises(ValueError):
        set_user_role("manager@example.com", "admin", "")


def test_role_migration_keeps_legacy_approval_without_admin_grants(temp_db, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy-users.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(255), password_hash VARCHAR(255), created_at TIMESTAMP)"))
        conn.execute(text("INSERT INTO users (id,email,password_hash) VALUES (1,'legacy@example.com','hash')"))
    temp_db._run_migrations(engine)
    temp_db._run_migrations(engine)
    with engine.begin() as conn:
        assert conn.execute(text("SELECT role FROM users WHERE id=1")).scalar() == "manager"
        conn.execute(text("INSERT INTO users (id,email,password_hash) VALUES (2,'new@example.com','hash')"))
        assert conn.execute(text("SELECT role FROM users WHERE id=2")).scalar() == "staff"
    assert "role_history" in {c["name"] for c in inspect(engine).get_columns("users")}
    engine.dispose()
