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


def test_ai_assist_fills_form_from_text(temp_db, monkeypatch):
    import app.web as web_module

    monkeypatch.setattr(
        web_module,
        "parse_pcb_text",
        lambda text: {"layer": 6, "material": "FR4", "qty": 9},
    )

    client = _logged_in_client(temp_db)
    response = client.post("/quotes/new/ai-assist", data={"spec_text": "6層 FR4 數量9"})

    assert response.status_code == 200
    assert 'value="6"' in response.text
    assert 'value="FR4"' in response.text


def test_ai_assist_normalizes_thickness_field_name(temp_db, monkeypatch):
    import app.web as web_module

    monkeypatch.setattr(
        web_module,
        "parse_pcb_text",
        lambda text: {"layer": 6, "qty": 1, "thickness": "1.6"},
    )

    client = _logged_in_client(temp_db)
    response = client.post("/quotes/new/ai-assist", data={"spec_text": "板厚1.6mm"})

    assert response.status_code == 200
    assert 'name="thickness_mm" value="1.6"' in response.text


def test_ai_assist_handles_parser_failure_gracefully(temp_db, monkeypatch):
    import app.web as web_module

    def _boom(text):
        raise RuntimeError("OpenAI timeout")

    monkeypatch.setattr(web_module, "parse_pcb_text", _boom)

    client = _logged_in_client(temp_db)
    response = client.post("/quotes/new/ai-assist", data={"spec_text": "6層 FR4"})

    assert response.status_code == 200
    assert "AI 解析失敗" in response.text
