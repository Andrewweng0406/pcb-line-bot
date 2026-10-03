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
    assert "AI Extraction Review" in response.text
    assert "Review Required" in response.text
    assert "High" in response.text


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
    assert "AI parsing failed" in response.text


def test_ai_assist_marks_defaults_and_inferred_fields_for_review(temp_db, monkeypatch):
    import app.web as web_module

    monkeypatch.setattr(
        web_module,
        "parse_pcb_text",
        lambda text: {"layer": 6, "material": "FR4", "qty": 9, "surface_finish": "ENIG"},
    )

    client = _logged_in_client(temp_db)
    response = client.post("/quotes/new/ai-assist", data={"spec_text": "6L FR4 qty 9"})

    assert response.status_code == 200
    assert "System default; confirm before sending." in response.text
    assert "Value was extracted, but direct evidence was not obvious." in response.text
    assert 'name="extraction_review_token"' in response.text


def test_ai_assist_fills_form_from_uploaded_photo(temp_db, monkeypatch):
    """The photo-upload path (as opposed to pasted text) had no test
    coverage at all until a real browser test surfaced the gap — the route
    itself always worked, but nothing exercised it.
    """
    import io

    import app.web as web_module

    monkeypatch.setattr(
        web_module,
        "parse_pcb_image",
        lambda path: {"layer": 46, "material": "MEGTRON 6", "qty": 2, "company_name": "ZENVOCE CORPORATION"},
    )

    client = _logged_in_client(temp_db)
    fake_image = io.BytesIO(b"fake-jpeg-bytes")
    response = client.post(
        "/quotes/new/ai-assist",
        data={"spec_text": ""},
        files={"photo": ("spec.jpg", fake_image, "image/jpeg")},
    )

    assert response.status_code == 200
    assert 'value="46"' in response.text
    assert 'value="MEGTRON 6"' in response.text
    assert 'value="ZENVOCE CORPORATION"' in response.text


def test_ai_assist_fills_extended_pcb_image_fields(temp_db, monkeypatch):
    import io

    import app.web as web_module

    monkeypatch.setattr(
        web_module,
        "parse_pcb_image",
        lambda path: {
            "layer": 22,
            "qty": 3,
            "material": "M6 FR4-HTG",
            "company_name": "HTSI",
            "length_mm": 490,
            "width_mm": 565,
            "thickness": 5,
            "pitch_mm": 0.5,
            "surface_finish": "ENIG",
            "enig": True,
            "enig_thickness_uinch": 10,
            "vip": True,
            "impedance": True,
            "back_drill": True,
            "copper_outer_oz": 1,
            "copper_inner_oz": 1,
            "min_hole_mil": 8,
            "warpage_mil_per_inch": 4,
            "legend_color": "White",
            "solder_mask_color": "Green",
            "countersunk": True,
            "counterbored": True,
            "inspection_report_required": True,
            "special_requirements": "Please provide inspection report.",
        },
    )

    client = _logged_in_client(temp_db)
    fake_image = io.BytesIO(b"fake-jpeg-bytes")
    response = client.post(
        "/quotes/new/ai-assist",
        data={"spec_text": ""},
        files={"photo": ("fab-info.jpg", fake_image, "image/jpeg")},
    )

    assert response.status_code == 200
    assert 'name="material" value="M6 FR4-HTG"' in response.text
    assert 'name="pitch_mm" value="0.5"' in response.text
    assert 'name="copper_outer_oz" value="1"' in response.text
    assert 'name="copper_inner_oz" value="1"' in response.text
    assert 'name="copper_weight" value="1oz"' in response.text
    assert 'name="min_hole_mil" value="8"' in response.text
    assert 'name="warpage_mil_per_inch" value="4"' in response.text
    assert 'name="legend_color" value="White"' in response.text
    assert 'name="solder_mask_color" value="Green"' in response.text
    assert 'name="back_drill" checked' in response.text
    assert 'name="countersunk" checked' in response.text
    assert 'name="counterbored" checked' in response.text
    assert 'name="inspection_report_required" checked' in response.text
    assert "Please provide inspection report." in response.text


def test_ai_assist_marks_hard_gold_from_photo(temp_db, monkeypatch):
    import io

    import app.web as web_module

    monkeypatch.setattr(
        web_module,
        "parse_pcb_image",
        lambda path: {
            "layer": 36,
            "qty": 2,
            "material": "FR4",
            "surface_finish": "hard gold",
            "enig_thickness_uinch": 20,
        },
    )

    client = _logged_in_client(temp_db)
    fake_image = io.BytesIO(b"fake-jpeg-bytes")
    response = client.post(
        "/quotes/new/ai-assist",
        data={"spec_text": ""},
        files={"photo": ("probeleader.jpg", fake_image, "image/jpeg")},
    )

    assert response.status_code == 200
    assert 'name="surface_finish" value="Hard Gold"' in response.text
    assert 'name="enig" checked' in response.text
    assert 'name="hard_gold" checked' in response.text


def test_ai_assist_prefers_photo_over_text_when_both_given(temp_db, monkeypatch):
    import io

    import app.web as web_module

    monkeypatch.setattr(web_module, "parse_pcb_image", lambda path: {"layer": 46, "qty": 2})
    monkeypatch.setattr(
        web_module,
        "parse_pcb_text",
        lambda text: (_ for _ in ()).throw(AssertionError("should not call the text parser when a photo was sent")),
    )

    client = _logged_in_client(temp_db)
    fake_image = io.BytesIO(b"fake-jpeg-bytes")
    response = client.post(
        "/quotes/new/ai-assist",
        data={"spec_text": "6層 FR4"},
        files={"photo": ("spec.jpg", fake_image, "image/jpeg")},
    )

    assert response.status_code == 200
    assert 'value="46"' in response.text
