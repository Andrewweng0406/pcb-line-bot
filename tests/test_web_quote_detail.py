from fastapi.testclient import TestClient

from app.core.auth import hash_password


def _logged_in_client(temp_db):
    from app.main import app
    client = TestClient(app)
    db = temp_db.SessionLocal()
    user = temp_db.User(email="staff@example.com", password_hash=hash_password("hunter2"), role="manager")
    db.add(user)
    db.commit()
    db.close()
    client.post("/login", data={"email": "staff@example.com", "password": "hunter2"})
    return client


def test_quote_detail_shows_spec_and_breakdown(temp_db):
    temp_db.save_quote(
        "line:U1",
        {"layer": 6, "material": "FR4", "qty": 9},
        {"status": "success", "total": 12345.0, "unit_price": 1371.67, "issue_ratio": 1.0, "explanations": ["Setup Fee: 80000"]},
    )
    db = temp_db.SessionLocal()
    quote_id = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first().id
    db.close()

    client = _logged_in_client(temp_db)
    response = client.get(f"/quotes/{quote_id}")

    assert response.status_code == 200
    assert "12,345" in response.text
    assert "Pending Review" in response.text


def test_quote_detail_benchmark_uses_independent_recorded_evidence(temp_db):
    spec = {
        "layer": 6, "material": "FR4", "qty": 10,
        "length_mm": 100, "width_mm": 100, "thickness_mm": 1.6,
        "copper_weight": "1oz", "delivery_days": 7, "enig_thickness_uinch": 5,
        "enig": True, "vip": False, "impedance": False, "back_drill": False, "bvh": False,
    }
    for _ in range(6):
        temp_db.save_quote("web:1", spec, {"status": "success", "total": 1000, "unit_price": 100})
    with temp_db.SessionLocal() as session:
        quotes = session.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id).all()
        for quote in quotes:
            quote.currency = "USD"
            quote.pricing_version = "v1"
            quote.quote_outcome = "won"
            quote.final_price = 900
            quote.actual_cost = 700
        quote_id = quotes[-1].id
        session.commit()
    client = _logged_in_client(temp_db)
    response = client.get(f"/quotes/{quote_id}")
    assert response.status_code == 200
    assert "USD 100.00" in response.text
    assert "USD 90.00" in response.text
    assert "USD 70.00" in response.text
    assert "5 / 5 valid samples" in response.text
    summary = client.get(f"/api/quotes/{quote_id}/historical-summary").json()
    assert all(metric["available"] for metric in summary["evidence"])
    assert client.get(f"/api/quotes/{quote_id}/similar?limit=-1").status_code == 422
    assert client.get(f"/api/quotes/{quote_id}/similar?limit=201").status_code == 422


def test_price_review_scenarios_are_consistent_in_html_and_api(temp_db):
    from scripts.seed_price_review_demo import seed_cases
    with temp_db.SessionLocal() as session:
        ids = seed_cases(session)
        session.commit()
        counts_before = session.query(temp_db.QuoteHistory).count()
        assert seed_cases(session) == ids
        session.commit()
        assert session.query(temp_db.QuoteHistory).count() == counts_before
    client = _logged_in_client(temp_db)
    expected = {
        "SYNTH-PRICE-NORMAL": "within_band",
        "SYNTH-PRICE-HIGH": "above_band",
        "SYNTH-PRICE-SPARSE": "insufficient_evidence",
    }
    for name, status in expected.items():
        response = client.get(f"/quotes/{ids[name]}")
        assert response.status_code == 200
        assert f'data-price-status="{status}"' in response.text
        assessment = client.get(f"/api/quotes/{ids[name]}/historical-summary").json()["price_assessment"]
        assert assessment["status"] == status
        if status == "above_band":
            assert assessment["deviation_pct"] == 60
            assert assessment["reference_count"] == 6
            assert "+60.0%" in response.text
            assert assessment["context_fields"] == ["area_in2", "qty"]
        if status == "within_band":
            summary = client.get(f"/api/quotes/{ids[name]}/historical-summary").json()
            assert summary["evidence"][0]["count"] == assessment["reference_count"] == 5
            assert summary["evidence"][0]["median"] == assessment["median_unit_price"] == 100
            assert "SYNTH-PRICE-HIGH" not in response.text
        assert response.text.index('data-price-status=') < response.text.index('Customer Quote Summary')
        if status == "insufficient_evidence":
            assert assessment["reference_count"] == 2
            assert assessment["upper_bound"] is None
    response = client.get(f"/quotes/{ids['SYNTH-PRICE-HIGH']}?lang=zh")
    assert "高於歷史區間" in response.text
    assert "價格覆核依據" in response.text


def test_quote_detail_shows_ai_extraction_review(temp_db):
    review = {
        "summary": {"high": 2, "medium": 1, "low": 1, "missing": 0, "needs_review": 1},
        "fields": [
            {
                "field": "layer",
                "label": "Layers",
                "value": 6,
                "source": "explicit",
                "confidence": "high",
                "needs_review": False,
                "reason": "Direct evidence found in the RFQ text.",
            },
            {
                "field": "issue_ratio",
                "label": "Issue Ratio",
                "value": 1.0,
                "source": "default",
                "confidence": "low",
                "needs_review": True,
                "reason": "System default; confirm before sending.",
            },
        ],
    }
    temp_db.save_quote(
        "web:1",
        {"layer": 6, "qty": 9, "area_inch": 10, "_extraction_review": review},
        {"status": "success", "total": 100.0, "unit_price": 11.11},
    )
    db = temp_db.SessionLocal()
    quote_id = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first().id
    db.close()

    client = _logged_in_client(temp_db)
    response = client.get(f"/quotes/{quote_id}")

    assert response.status_code == 200
    assert "AI Extraction Review" in response.text
    assert "Issue Ratio" in response.text
    assert "System default; confirm before sending." in response.text


def test_quote_detail_shows_historical_intelligence(temp_db):
    temp_db.save_quote(
        "web:1",
        {"layer": 6, "material": "FR4", "qty": 10, "length_mm": 100, "width_mm": 100, "enig": True},
        {"status": "success", "total": 1000, "unit_price": 100},
    )
    temp_db.save_quote(
        "web:1",
        {"layer": 6, "material": "FR4", "qty": 10, "length_mm": 102, "width_mm": 100, "enig": True},
        {"status": "success", "total": 1100, "unit_price": 110},
    )
    db = temp_db.SessionLocal()
    quote_id = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first().id
    db.close()

    client = _logged_in_client(temp_db)
    response = client.get(f"/quotes/{quote_id}")

    assert response.status_code == 200
    assert "Specification comparison" in response.text
    assert "-2.0%" in response.text
    assert "%+.1f%%" not in response.text
    assert "Insufficient evidence" in response.text
    assert "Historical Intelligence" in response.text
    assert "Similar Quotes" in response.text
    assert "Similar RFQs" in response.text


def test_quote_detail_missing_returns_404(temp_db):
    client = _logged_in_client(temp_db)
    response = client.get("/quotes/999")
    assert response.status_code == 404


def test_update_quote_status_and_notes(temp_db):
    temp_db.save_quote("line:U1", {"layer": 6, "qty": 1}, {"status": "success", "total": 100.0, "unit_price": 100.0})
    db = temp_db.SessionLocal()
    quote_id = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first().id
    db.close()


def test_update_quote_outcome_won_fields_and_margin(temp_db):
    temp_db.save_quote("web:1", {"layer": 6, "qty": 1, "area_inch": 10}, {"status": "success", "total": 100.0, "unit_price": 100.0})
    db = temp_db.SessionLocal()
    quote_id = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first().id
    db.close()

    client = _logged_in_client(temp_db)
    response = client.post(
        f"/quotes/{quote_id}/update",
        data={
            "status": "pending",
            "notes": "",
            "quote_outcome": "won",
            "final_price": "120",
            "actual_cost": "90",
            "production_lead_time_actual": "8",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    db = temp_db.SessionLocal()
    quote = db.query(temp_db.QuoteHistory).filter(temp_db.QuoteHistory.id == quote_id).first()
    assert quote.status == "pending"
    assert quote.quote_outcome == "won"
    assert quote.final_price == 120
    assert quote.actual_cost == 90
    assert quote.production_lead_time_actual == 8
    assert quote.actual_margin_pct == 0.25
    db.close()


def test_update_quote_outcome_lost_without_reason_and_with_competitor_data(temp_db):
    temp_db.save_quote("web:1", {"layer": 6, "qty": 1, "area_inch": 10}, {"status": "success", "total": 100.0, "unit_price": 100.0})
    db = temp_db.SessionLocal()
    quote_id = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first().id
    db.close()

    client = _logged_in_client(temp_db)
    response = client.post(
        f"/quotes/{quote_id}/update",
        data={
            "status": "approved",
            "notes": "still operationally approved",
            "quote_outcome": "lost",
            "lost_reason": "",
            "lost_reason_note": "customer paused",
            "competitor_name": "Other Fab",
            "competitor_price": "95",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    db = temp_db.SessionLocal()
    quote = db.query(temp_db.QuoteHistory).filter(temp_db.QuoteHistory.id == quote_id).first()
    assert quote.status == "approved"
    assert quote.quote_outcome == "lost"
    assert quote.lost_reason is None
    assert quote.lost_reason_note == "customer paused"
    assert quote.competitor_name == "Other Fab"
    assert quote.competitor_price == 95
    db.close()


def test_status_update_does_not_clear_existing_outcome_data(temp_db):
    temp_db.save_quote("web:1", {"layer": 6, "qty": 1, "area_inch": 10}, {"status": "success", "total": 100.0, "unit_price": 100.0})
    db = temp_db.SessionLocal()
    quote = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first()
    quote.quote_outcome = "won"
    quote.final_price = 120
    quote.actual_cost = 90
    quote.actual_margin_pct = 0.25
    quote_id = quote.id
    db.commit()
    db.close()

    client = _logged_in_client(temp_db)
    response = client.post(
        f"/quotes/{quote_id}/update",
        data={"status": "ordered", "notes": "ordered now"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    db = temp_db.SessionLocal()
    quote = db.query(temp_db.QuoteHistory).filter(temp_db.QuoteHistory.id == quote_id).first()
    assert quote.status == "ordered"
    assert quote.quote_outcome == "won"
    assert quote.final_price == 120
    assert quote.actual_margin_pct == 0.25
    db.close()


def test_quote_missing_spec_json_renders_without_error(temp_db):
    """Pre-migration, LINE-submitted quotes may predate spec_json/breakdown_json.
    Simulate that by inserting a row with those columns left null.
    """
    db = temp_db.SessionLocal()
    quote = temp_db.QuoteHistory(
        source_channel_id="line:U1", layer=6, material="FR4", qty=1, total=100.0, unit_price=100.0
    )
    db.add(quote)
    db.commit()
    db.refresh(quote)
    quote_id = quote.id
    db.close()

    client = _logged_in_client(temp_db)
    response = client.get(f"/quotes/{quote_id}")
    assert response.status_code == 200


def test_export_excel_route_downloads_when_spec_present(temp_db):
    temp_db.save_quote("line:U1", {"layer": 6, "qty": 1}, {"status": "success", "total": 100.0, "unit_price": 100.0})
    db = temp_db.SessionLocal()
    quote_id = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first().id
    db.close()

    client = _logged_in_client(temp_db)
    response = client.get(f"/quotes/{quote_id}/export/excel", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/download/exports/")


def test_export_formal_quote_route_downloads_when_spec_present(temp_db):
    temp_db.save_quote(
        "line:U1",
        {
            "layer": 28,
            "qty": 3,
            "material": "FR4_HTG",
            "length_mm": 560,
            "width_mm": 350,
            "thickness_mm": 5,
            "enig": True,
            "enig_thickness_uinch": 10,
            "impedance": True,
            "copper_outer_oz": 1,
            "copper_inner_oz": 1,
            "special_requirements": "Please provide inspection report.",
        },
        {"status": "success", "total": 228095.46, "unit_price": 76031.82, "area_inch": 303.8},
    )
    db = temp_db.SessionLocal()
    quote_id = db.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first().id
    db.close()

    client = _logged_in_client(temp_db)
    response = client.get(f"/quotes/{quote_id}/export/formal", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/download/exports/formal_quote_")


def test_export_excel_route_404s_without_spec(temp_db):
    db = temp_db.SessionLocal()
    quote = temp_db.QuoteHistory(source_channel_id="line:U1", layer=6, qty=1, total=100.0, unit_price=100.0)
    db.add(quote)
    db.commit()
    db.refresh(quote)
    quote_id = quote.id
    db.close()

    client = _logged_in_client(temp_db)
    response = client.get(f"/quotes/{quote_id}/export/excel", follow_redirects=False)
    assert response.status_code == 404


def test_export_formal_quote_route_404s_without_spec(temp_db):
    db = temp_db.SessionLocal()
    quote = temp_db.QuoteHistory(source_channel_id="line:U1", layer=6, qty=1, total=100.0, unit_price=100.0)
    db.add(quote)
    db.commit()
    db.refresh(quote)
    quote_id = quote.id
    db.close()

    client = _logged_in_client(temp_db)
    response = client.get(f"/quotes/{quote_id}/export/formal", follow_redirects=False)
    assert response.status_code == 404
