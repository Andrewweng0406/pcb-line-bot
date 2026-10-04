from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.core.auth import hash_password
from app.import_quotes import confirm_import, preview_import
import pytest


def _workbook_bytes(rows):
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    output = BytesIO()
    wb.save(output)
    return output.getvalue()


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


def test_preview_import_validates_rows_without_committing(temp_db):
    file_bytes = _workbook_bytes([
        ["Customer Name", "Layers", "Material", "Qty", "Size", "Quote", "Date", "Result"],
        ["ABC Corp", "6L", "FR4", 10, "100x50", 1234, "2026-07-01", "won"],
        ["Bad Corp", "", "FR4", 0, "bad", "", "2026-07-01", "lost"],
    ])

    result = preview_import(file_bytes)
    assert result["rows_detected"] == 2
    assert result["valid"] == 1
    assert result["invalid"] == 1

    db = temp_db.SessionLocal()
    assert db.query(temp_db.QuoteHistory).count() == 0
    db.close()


def test_confirm_import_rejects_invalid_rows_without_commit(temp_db):
    file_bytes = _workbook_bytes([
        ["Customer Name", "Layers", "Material", "Qty", "Size", "Quote", "Date", "Result"],
        ["Bad Corp", "", "FR4", 0, "bad", "", "2026-07-01", "lost"],
    ])
    db = temp_db.SessionLocal()
    result = confirm_import(db, temp_db, file_bytes)
    assert result["status"] == "error"
    assert result["committed"] == 0
    assert db.query(temp_db.QuoteHistory).count() == 0
    db.close()


def test_confirm_import_commits_valid_rows_and_customer(temp_db):
    file_bytes = _workbook_bytes([
        ["Customer Name", "Layers", "Material", "Qty", "Size", "Quote", "Date", "Result"],
        ["ABC Corp", "6L", "FR4", 10, "100x50", 1234, "2026-07-01", "won"],
    ])
    db = temp_db.SessionLocal()
    result = confirm_import(db, temp_db, file_bytes)
    assert result["status"] == "success"
    assert result["committed"] == 1

    quote = db.query(temp_db.QuoteHistory).first()
    assert quote.source_channel == "excel_import"
    assert quote.quote_no.startswith("PCB-")
    assert quote.layer == 6
    assert quote.qty == 10
    assert quote.total == 1234
    assert quote.unit_price == 123.4
    assert quote.quote_outcome == "won"
    assert quote.customer.company_name == "ABC Corp"
    db.close()


def test_import_api_preview_and_confirm(temp_db):
    client = _logged_in_client(temp_db)
    file_bytes = _workbook_bytes([
        ["Customer Name", "Layers", "Material", "Qty", "Size", "Quote", "Date", "Result"],
        ["ABC Corp", "6L", "FR4", 10, "100x50", 1234, "2026-07-01", "won"],
    ])

    preview = client.post(
        "/api/import/quotes/preview",
        files={"file": ("quotes.xlsx", file_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert preview.status_code == 200
    assert preview.json()["valid"] == 1

    db = temp_db.SessionLocal()
    assert db.query(temp_db.QuoteHistory).count() == 0
    db.close()

    confirm = client.post(
        "/api/import/quotes/confirm",
        files={"file": ("quotes.xlsx", file_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert confirm.status_code == 200
    assert confirm.json()["committed"] == 1


def test_import_web_page_and_preview(temp_db):
    client = _logged_in_client(temp_db)
    response = client.get("/import/quotes")
    assert response.status_code == 200
    assert "Import Historical Quotes" in response.text

    file_bytes = _workbook_bytes([
        ["Customer Name", "Layers", "Material", "Qty", "Size", "Quote", "Date", "Result"],
        ["ABC Corp", "6L", "FR4", 10, "100x50", 1234, "2026-07-01", "won"],
    ])
    response = client.post(
        "/import/quotes",
        data={"action": "preview"},
        files={"file": ("quotes.xlsx", file_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 200
    assert "Import Preview" in response.text
    assert "Valid: 1" in response.text


def test_import_repeated_confirmation_is_idempotent(temp_db):
    data = _workbook_bytes([
        ["Customer Name", "Layers", "Material", "Qty", "Size", "Quote"],
        ["ABC", 6, "FR4", 10, "100x50", 1000],
        ["ABC", 6, "FR4", 20, "100x50", 2000],
    ])
    with temp_db.SessionLocal() as session:
        assert confirm_import(session, temp_db, data)["committed"] == 2
        result = confirm_import(session, temp_db, data)
        assert result["committed"] == 0 and result["duplicates"] == 2
        quotes = session.query(temp_db.QuoteHistory).all()
        assert len(quotes) == 2 and len({q.quote_no for q in quotes}) == 2
        assert session.query(temp_db.Customer).count() == 1
        assert all(q.import_key and q.spec_json["file_sha256"] for q in quotes)
        with pytest.raises(ValueError, match="different mapping"):
            confirm_import(session, temp_db, data, {"layer": "Layers", "qty": "Qty", "total": "Quote"})
        assert session.query(temp_db.QuoteHistory).count() == 2


def test_import_records_reference_fields_without_guessing(temp_db):
    data = _workbook_bytes([
        ["Layers", "Material", "Qty", "Size", "Quote", "Currency", "Pricing Version", "Thickness (mm)", "Copper (oz)", "Surface Finish", "Lead Time (days)", "ENIG", "VIP", "Impedance", "Back Drill", "BVH", "Accepted Price", "Actual Cost"],
        [6, "FR4", 10, "100x50", 1000, "usd", "v1", 1.6, 1, "OSP", 7, "no", "no", "no", "no", "no", 900, 700],
    ])
    preview = preview_import(data)
    assert not any("Reference data missing" in warning for warning in preview["rows"][0]["warnings"])
    with temp_db.SessionLocal() as session:
        confirm_import(session, temp_db, data)
        quote = session.query(temp_db.QuoteHistory).first()
        assert quote.currency == "USD" and quote.pricing_version == "v1"
        assert quote.board_thickness_mm == 1.6 and quote.copper_weight_oz == 1
        assert quote.spec_json["vip"] is False and quote.delivery_days == 7
        assert quote.final_price == 900 and quote.actual_cost == 700
        assert quote.actual_margin_pct == pytest.approx(.2222)
    sparse = _workbook_bytes([["Layers", "Qty", "Quote"], [6, 10, 1000]])
    assert preview_import(sparse)["rows"][0]["mapped"]["currency"] is None
    assert "Reference data missing" in ";".join(preview_import(sparse)["rows"][0]["warnings"])


def test_import_rejects_unsafe_or_invalid_mapping_and_metadata():
    from app.import_quotes import parse_mapping_json
    for raw in ("[]", "broken"):
        with pytest.raises(ValueError):
            parse_mapping_json(raw)
    duplicate_headers = _workbook_bytes([["Layers", "Layers"], [6, 8]])
    with pytest.raises(ValueError, match="Duplicate"):
        preview_import(duplicate_headers)
    invalid = _workbook_bytes([["Layers", "Qty", "Quote", "Currency", "VIP"], [6, 10, 1000, "dollars", "maybe"]])
    assert preview_import(invalid)["invalid"] == 1


def test_concurrent_identical_imports_cannot_duplicate_rows(temp_db):
    from concurrent.futures import ThreadPoolExecutor
    data = _workbook_bytes([["Layers", "Qty", "Quote"], [6, 10, 1000]])
    def run_import():
        with temp_db.SessionLocal() as session:
            try:
                return confirm_import(session, temp_db, data)["committed"]
            except ValueError:
                return 0
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(lambda _: run_import(), range(2))) == 1
    with temp_db.SessionLocal() as session:
        assert session.query(temp_db.QuoteHistory).count() == 1


def test_import_key_migration_preserves_existing_records(temp_db, tmp_path):
    from sqlalchemy import Column, MetaData, Table, create_engine, inspect, select
    engine = create_engine(f"sqlite:///{tmp_path / 'pre-import-key.db'}")
    old_metadata = MetaData()
    old_table = Table("quote_history", old_metadata, *[
        Column(c.name, c.type, primary_key=c.primary_key, nullable=c.nullable)
        for c in temp_db.QuoteHistory.__table__.columns if c.name != "import_key"
    ])
    old_metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(old_table.insert().values(id=1, layer=6, qty=10, total=1000))
    temp_db._run_migrations(engine)
    temp_db._run_migrations(engine)
    inspector = inspect(engine)
    assert "import_key" in {c["name"] for c in inspector.get_columns("quote_history")}
    assert any(i["name"] == "ix_quote_history_import_key" and i["unique"] for i in inspector.get_indexes("quote_history"))
    with engine.connect() as connection:
        row = connection.execute(select(old_table)).first()
        assert row.total == 1000 and row.qty == 10
    engine.dispose()
