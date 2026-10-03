from html.parser import HTMLParser

from app.extraction_review import build_extraction_review, sign_review
from tests.test_web_quote_new import _logged_in_client


class ReviewTokenParser(HTMLParser):
    token = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("name") == "extraction_review_token":
            self.token = attrs["value"]


def test_draft_gate_confirmation_and_formal_export(temp_db, monkeypatch):
    import app.web as web

    client = _logged_in_client(temp_db)
    spec = {"layer": 6, "qty": 9, "length_mm": 100, "width_mm": 100, "material": "FR4", "issue_ratio": 1}
    review = build_extraction_review(spec, "6L FR4 qty 9 100x100mm")
    response = client.post("/quotes/new", data={**spec, "extraction_review_token": sign_review(review, 1)}, follow_redirects=False)
    assert response.status_code == 303
    with temp_db.SessionLocal() as session:
        quote = session.query(temp_db.QuoteHistory).first()
        quote_id = quote.id
        pending = [item["field"] for item in quote.spec_json["_extraction_review"]["fields"] if item["needs_review"]]
    assert client.get(f"/quotes/{quote_id}/export/formal").status_code == 409
    assert client.post(f"/quotes/{quote_id}/update", data={"status": "approved"}).status_code == 409
    assert client.post(f"/quotes/{quote_id}/review", data={"reviewed_fields": pending, "review_note": "Verified against customer RFQ"}, follow_redirects=False).status_code == 303
    with temp_db.SessionLocal() as session:
        saved = session.get(temp_db.QuoteHistory, quote_id).spec_json["_extraction_review"]
        assert saved["summary"]["needs_review"] == 0
        assert all(event["email"] == "staff@example.com" for event in saved["events"])
    assert "Review History" in client.get(f"/quotes/{quote_id}").text
    assert client.post(f"/quotes/{quote_id}/update", data={"status": "approved"}, follow_redirects=False).status_code == 303
    monkeypatch.setattr(web, "export_formal_quote", lambda *args: "/tmp/test-quote.xlsx")
    assert client.get(f"/quotes/{quote_id}/export/formal", follow_redirects=False).status_code == 303


def test_ai_form_signature_and_corrected_value_audit(temp_db, monkeypatch):
    import app.web as web

    client = _logged_in_client(temp_db)
    monkeypatch.setattr(web, "parse_pcb_text", lambda text: {"layer": 6, "qty": 9, "length_mm": 100, "width_mm": 100})
    response = client.post("/quotes/new/ai-assist", data={"spec_text": "6L qty 9 100x100mm"})
    parser = ReviewTokenParser()
    parser.feed(response.text)
    token = parser.token
    data = {"layer": 8, "qty": 9, "length_mm": 100, "width_mm": 100, "extraction_review_token": token, "reviewed_fields": ["layer"]}
    response = client.post("/quotes/new", data=data)
    assert response.status_code == 400
    assert "review note is required" in response.text
    assert token in response.text
    data["review_note"] = "Customer confirmed 8 layers"
    assert client.post("/quotes/new", data=data, follow_redirects=False).status_code == 303
    with temp_db.SessionLocal() as session:
        event = session.query(temp_db.QuoteHistory).first().spec_json["_extraction_review"]["events"][0]
        assert (event["original_value"], event["final_value"]) == (6, 8)
    data["extraction_review_token"] += "tampered"
    assert client.post("/quotes/new", data=data).status_code == 400


def test_unsigned_review_is_rejected(temp_db):
    client = _logged_in_client(temp_db)
    assert client.post("/quotes/new", data={"layer": 6, "qty": 9, "extraction_review_json": "{}"}).status_code == 400


def test_revision_preserves_original_and_invalidates_changed_confirmation(temp_db):
    from app.extraction_review import confirm_review, reconcile_review

    client = _logged_in_client(temp_db)
    spec = {"layer": 6, "qty": 9, "length_mm": 100, "width_mm": 100, "issue_ratio": 1}
    review = reconcile_review(build_extraction_review(spec, "6L qty 9 100x100mm"), spec)
    review = confirm_review(review, ["layer", "issue_ratio"], 1, "staff@example.com", "Confirmed RFQ")
    client.post("/quotes/new", data={**spec, "extraction_review_token": sign_review(review, 1)})
    with temp_db.SessionLocal() as session:
        parent = session.query(temp_db.QuoteHistory).first()
        parent_id = parent.id
    response = client.get(f"/quotes/{parent_id}/revise")
    assert response.status_code == 200
    assert "Revision Of" in response.text
    assert 'hx-post="/quotes/new/ai-assist"' not in response.text
    parser = ReviewTokenParser()
    parser.feed(response.text)
    assert client.post("/quotes/new", data={**spec, "layer": 8, "extraction_review_token": parser.token}, follow_redirects=False).status_code == 303
    with temp_db.SessionLocal() as session:
        original = session.get(temp_db.QuoteHistory, parent_id)
        child = session.query(temp_db.QuoteHistory).order_by(temp_db.QuoteHistory.id.desc()).first()
        assert original.layer == 6
        assert child.layer == 8
        review = child.spec_json["_extraction_review"]
        assert review["revision_of"] == parent_id
        layer = next(item for item in review["fields"] if item["field"] == "layer")
        assert not layer.get("confirmation")
        assert layer["final_value"] == 8
        assert review["events"][0]["final_value"] == 6
        assert client.get(f"/quotes/{child.id}/export/formal").status_code == 409
