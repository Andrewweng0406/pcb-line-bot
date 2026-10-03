from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.core.auth import hash_password
from app.import_quotes import confirm_import, preview_import


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
    user = temp_db.User(email="staff@example.com", password_hash=hash_password("hunter2"))
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
