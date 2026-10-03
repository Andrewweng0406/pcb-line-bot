import json

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
    assert "New Quote" in response.text


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
    assert quote.source_channel == "web"
    assert quote.product_type == "pcb"
    assert quote.pricing_version == "v1"
    db.close()


def test_submitting_quote_preserves_extraction_review_metadata(temp_db):
    client = _logged_in_client(temp_db)
    review = {
        "summary": {"high": 2, "medium": 0, "low": 1, "missing": 0, "needs_review": 1},
        "fields": [
            {
                "field": "issue_ratio",
                "label": "Issue Ratio",
                "value": 1.0,
                "source": "default",
                "confidence": "low",
                "needs_review": True,
                "reason": "System default; confirm before sending.",
            }
        ],
    }

    response = client.post(
        "/quotes/new",
        data={
            "layer": 6,
            "qty": 9,
            "material": "FR4",
            "length_mm": 100,
            "width_mm": 100,
            "issue_ratio": 1.0,
            "extraction_review_json": json.dumps(review),
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    db = temp_db.SessionLocal()
    quote = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first()
    assert quote.spec_json["_extraction_review"]["summary"]["needs_review"] == 1
    assert quote.spec_json["_extraction_review"]["fields"][0]["source"] == "default"
    db.close()


def test_submitting_invalid_quote_shows_error(temp_db):
    client = _logged_in_client(temp_db)

    response = client.post(
        "/quotes/new",
        data={"layer": 999, "qty": 1},
    )
    assert response.status_code == 400
    assert "is not supported" in response.text


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


def test_submitting_quote_preserves_extended_spec_fields(temp_db):
    client = _logged_in_client(temp_db)

    response = client.post(
        "/quotes/new",
        data={
            "layer": 22,
            "qty": 3,
            "material": "M6 FR4-HTG",
            "length_mm": 490,
            "width_mm": 565,
            "issue_ratio": 1.0,
            "enig": "on",
            "enig_thickness_uinch": 10,
            "vip": "on",
            "impedance": "on",
            "back_drill": "on",
            "countersunk": "on",
            "counterbored": "on",
            "inspection_report_required": "on",
            "thickness_mm": 5,
            "pitch_mm": 0.5,
            "surface_finish": "ENIG",
            "copper_outer_oz": 1,
            "copper_inner_oz": 1,
            "min_hole_mil": 8,
            "warpage_mil_per_inch": 4,
            "legend_color": "White",
            "solder_mask_color": "Green",
            "special_requirements": "Please provide inspection report.",
            "company_name": "HTSI",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    db = temp_db.SessionLocal()
    quote = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first()
    assert quote.spec_json["material"] == "M6 FR4-HTG"
    assert quote.spec_json["pitch_mm"] == 0.5
    assert quote.spec_json["copper_outer_oz"] == 1
    assert quote.spec_json["copper_inner_oz"] == 1
    assert quote.spec_json["copper_weight"] == "1oz"
    assert quote.spec_json["min_hole_mil"] == 8
    assert quote.spec_json["warpage_mil_per_inch"] == 4
    assert quote.spec_json["legend_color"] == "White"
    assert quote.spec_json["solder_mask_color"] == "Green"
    assert quote.spec_json["back_drill"] is True
    assert quote.spec_json["countersunk"] is True
    assert quote.spec_json["counterbored"] is True
    assert quote.spec_json["inspection_report_required"] is True
    assert quote.spec_json["special_requirements"] == "Please provide inspection report."
    assert quote.surface_finish == "ENIG"
    assert quote.gold_thickness_uin == 10
    assert quote.copper_weight_oz == 1
    db.close()
