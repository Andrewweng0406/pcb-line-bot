from copy import deepcopy
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook

from app.core.config import settings
from app.extraction_review import release_pending
from tests.test_web_extraction_workflow import ReviewTokenParser
from tests.test_web_quote_new import _logged_in_client


RFQ = "6L FR4 qty 9 100x100mm thickness 1.6mm copper 1oz ENIG 5uinch pitch 0.4mm delivery 7 days"
PARSED_RFQ = {
    "layer": 6, "qty": 9, "material": "FR4", "length_mm": 100, "width_mm": 100,
    "thickness": 1.6, "copper_weight": "1oz", "enig": True,
    "gold_thickness_uin": 5, "delivery_days": 7, "pitch_mm": 0.4,
}
FORM = {
    "layer": 8, "qty": 9, "material": "FR4", "length_mm": 100, "width_mm": 100,
    "thickness_mm": 1.6, "copper_weight": "1oz", "enig": "on",
    "enig_thickness_uinch": 5, "delivery_days": 7, "issue_ratio": 1,
    "company_name": "Acceptance Buyer", "pitch_mm": 0.4,
}


def review_token(html):
    parser = ReviewTokenParser()
    parser.feed(html)
    assert parser.token
    return parser.token


def workbook_values(content):
    workbook = load_workbook(BytesIO(content))
    values = {cell.coordinate: cell.value for row in workbook.active for cell in row}
    workbook.close()
    return values


def test_rfq_to_revision_preserves_evidence_and_real_exports(temp_db, monkeypatch, tmp_path):
    import app.web as web

    monkeypatch.setattr(settings, "EXPORT_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "DEFAULT_CURRENCY", "NTD")
    monkeypatch.setattr(settings, "PRICING_VERSION", "acceptance-v1")
    monkeypatch.setattr(web, "parse_pcb_text", lambda text: deepcopy(PARSED_RFQ))
    client = _logged_in_client(temp_db)
    parsed = client.post("/quotes/new/ai-assist", data={"spec_text": RFQ})
    assert parsed.status_code == 200
    token = review_token(parsed.text)
    draft = client.post("/quotes/new", data={**FORM, "extraction_review_token": token}, follow_redirects=False)
    assert draft.status_code == 303
    with temp_db.SessionLocal() as session:
        parent = session.query(temp_db.QuoteHistory).one()
        parent_id = parent.id
        assert parent.layer == 8
        assert parent.status == "pending"
        review = parent.spec_json["_extraction_review"]
        assert review["raw_input"] == RFQ
        layer = next(item for item in review["fields"] if item["field"] == "layer")
        assert (layer["value"], layer["final_value"]) == (6, 8)
        assert layer["evidence"]
        pending = [item["field"] for item in release_pending(parent.spec_json)]
    assert client.post(f"/quotes/{parent_id}/update", data={"status": "approved"}).status_code == 409
    assert client.post(f"/quotes/{parent_id}/update", data={"status": "ordered"}).status_code == 409
    assert client.get(f"/quotes/{parent_id}/export/formal").status_code == 409
    assert list(tmp_path.iterdir()) == []
    # Corrected values require a note, and a failed review must not persist events.
    assert client.post(f"/quotes/{parent_id}/review", data={"reviewed_fields": pending}).status_code == 400
    with temp_db.SessionLocal() as session:
        assert session.get(temp_db.QuoteHistory, parent_id).spec_json["_extraction_review"].get("events", []) == []
    confirmed = client.post(f"/quotes/{parent_id}/review", data={
        "reviewed_fields": pending, "review_note": "Customer confirmed 8 layers against drawing Rev B",
    }, follow_redirects=False)
    assert confirmed.status_code == 303
    assert client.get(f"/api/quotes/{parent_id}/historical-summary").json()["price_assessment"]["status"] == "insufficient_evidence"
    assert client.post(f"/quotes/{parent_id}/update", data={"status": "approved", "notes": "Approved after RFQ review"}, follow_redirects=False).status_code == 303
    with temp_db.SessionLocal() as session:
        parent = session.get(temp_db.QuoteHistory, parent_id)
        snapshot = deepcopy(parent.spec_json)
        original_total = parent.total
        assert not release_pending(snapshot)
        correction = next(event for event in snapshot["_extraction_review"]["events"] if event["field"] == "layer")
        assert (correction["original_value"], correction["final_value"]) == (6, 8)
        assert correction["email"] == "staff@example.com"
        assert correction["at"] and correction["note"]
    export = client.get(f"/quotes/{parent_id}/export/formal", follow_redirects=False)
    assert export.status_code == 303
    original_url = export.headers["location"]
    original_bytes = client.get(original_url).content
    cells = workbook_values(original_bytes)
    assert cells["C11"] == "9 pcs/batch"
    assert "Layer: 8" in cells["B11"]
    assert cells["E11"] == f"NTD {original_total:,.2f}"
    internal = client.get(f"/quotes/{parent_id}/export/excel", follow_redirects=False)
    assert internal.status_code == 303
    internal_bytes = client.get(internal.headers["location"]).content
    assert workbook_values(internal_bytes)["B6"] == "NTD"
    assert workbook_values(internal_bytes)["B7"] == 8
    revision = client.get(f"/quotes/{parent_id}/revise")
    child = client.post("/quotes/new", data={**FORM, "layer": 10,
        "extraction_review_token": review_token(revision.text)}, follow_redirects=False)
    assert child.status_code == 303
    with temp_db.SessionLocal() as session:
        child = session.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first()
        child_id = child.id
        assert child_id != parent_id and child.status == "pending" and child.layer == 10
        child_review = child.spec_json["_extraction_review"]
        assert child_review["revision_of"] == parent_id
        assert child_review["raw_input"] == RFQ
        assert child_review["events"] == snapshot["_extraction_review"]["events"]
        layer = next(item for item in child_review["fields"] if item["field"] == "layer")
        assert not layer.get("confirmation")
        pending = [item["field"] for item in release_pending(child.spec_json)]
        assert "layer" in pending
    assert client.get(f"/quotes/{child_id}/export/formal").status_code == 409
    assert client.post(f"/quotes/{child_id}/update", data={"status": "approved"}).status_code == 409
    assert client.post(f"/quotes/{child_id}/review", data={"reviewed_fields": pending,
        "review_note": "Customer changed stackup to 10 layers, drawing Rev C"}, follow_redirects=False).status_code == 303
    assert client.post(f"/quotes/{child_id}/update", data={"status": "approved"}, follow_redirects=False).status_code == 303
    assert client.get(f"/api/quotes/{child_id}/historical-summary").json()["price_assessment"]["status"] == "insufficient_evidence"
    matches = client.get(f"/api/quotes/{child_id}/similar").json()
    assert all("review_pending" not in item["exclusions"] for item in matches)
    revised_export = client.get(f"/quotes/{child_id}/export/formal", follow_redirects=False)
    assert revised_export.status_code == 303
    assert "Layer: 10" in workbook_values(client.get(revised_export.headers["location"]).content)["B11"]
    assert client.get(original_url).content == original_bytes
    assert client.get(internal.headers["location"]).content == internal_bytes
    with temp_db.SessionLocal() as session:
        parent = session.get(temp_db.QuoteHistory, parent_id)
        assert parent.spec_json == snapshot
        assert parent.layer == 8 and parent.total == original_total and parent.status == "approved"
        assert session.query(temp_db.QuoteHistory).count() == 2
        assert session.query(temp_db.Customer).count() == 1
    # A fresh authenticated session still sees both saved versions and their audit.
    client.cookies.clear()
    assert client.post("/login", data={"email": "staff@example.com", "password": "hunter2"}).status_code == 200
    assert "drawing Rev B" in client.get(f"/quotes/{parent_id}").text
    assert "drawing Rev C" in client.get(f"/quotes/{child_id}").text


def test_repeated_exports_never_overwrite_existing_files(monkeypatch, tmp_path):
    from datetime import datetime
    from types import SimpleNamespace
    import app.formal_quote_export as formal
    import app.export_excel as internal

    monkeypatch.setattr(settings, "EXPORT_DIR", str(tmp_path))
    clock = SimpleNamespace(now=lambda: datetime(2026, 10, 3, 12))
    monkeypatch.setattr(formal, "datetime", clock)
    monkeypatch.setattr(internal, "datetime", clock)
    first_result = {"total": 1000, "unit_price": 100}
    second_result = {"total": 2000, "unit_price": 200}
    first_path = formal.export_formal_quote(FORM, first_result, {"currency": "NTD"})
    first_bytes = Path(first_path).read_bytes()
    second_path = formal.export_formal_quote(FORM, second_result, {"currency": "NTD"})
    assert first_path != second_path
    assert Path(first_path).read_bytes() == first_bytes
    monkeypatch.setattr(internal, "quote_counter", 1)
    first_filename = internal.export_quote_excel(FORM, first_result, currency="NTD")
    first_bytes = (tmp_path / first_filename).read_bytes()
    # A process restart resets the in-memory counter.
    monkeypatch.setattr(internal, "quote_counter", 1)
    second_filename = internal.export_quote_excel(FORM, second_result, currency="NTD")
    assert first_filename != second_filename
    assert (tmp_path / first_filename).read_bytes() == first_bytes
