import pytest

from app.extraction_review import (
    build_extraction_review, clarification_draft, confirm_review, pending_fields,
    read_review, reconcile_review, sign_review,
)


def _field(review, name):
    return next(item for item in review["fields"] if item["field"] == name)


def test_conflict_is_not_high_confidence_and_preserves_original_evidence():
    review = build_extraction_review({"layer": 6, "qty": 9}, "Email: 6L, drawing: 8 layers; qty 9")
    item = _field(review, "layer")
    assert item["source"] == "conflict"
    assert item["needs_review"]
    assert item["evidence"] == ["6L", "8 layers"]
    assert "conflicting specifications (6L; 8 layers)" in clarification_draft(review)


def test_wrong_extracted_value_requires_review_even_with_a_keyword():
    review = build_extraction_review({"layer": 8, "qty": 9}, "6L qty 9")
    assert _field(review, "layer")["confidence"] == "low"
    assert _field(review, "qty")["confidence"] == "high"


def test_partial_dimensions_require_size_review():
    review = build_extraction_review({"layer": 6, "qty": 9, "length_mm": 100}, "6L qty 9")
    assert _field(review, "size")["needs_review"]


def test_negative_boolean_is_not_automatically_high_confidence():
    review = build_extraction_review({"vip": True}, "No VIP required")
    assert _field(review, "vip")["needs_review"]


def test_gold_evidence_does_not_confuse_micrometers_with_microinches():
    review = build_extraction_review({"enig_thickness_uinch": 10}, "Gold thickness 10um")
    assert _field(review, "enig_thickness_uinch")["needs_review"]
    assert _field(review, "enig_thickness_uinch")["evidence"] == []


def test_signed_review_rejects_tampering_and_wrong_owner():
    token = sign_review(build_extraction_review({"layer": 6}), 1)
    assert read_review(token, 1)["fields"]
    with pytest.raises(ValueError):
        read_review(token + "tampered", 1)
    with pytest.raises(ValueError):
        read_review(token, 2)


def test_correction_requires_reason_and_records_authenticated_actor():
    review = build_extraction_review({"layer": 6, "qty": 9}, "6L qty 9")
    corrected = reconcile_review(review, {"layer": 8, "qty": 9, "length_mm": 100, "width_mm": 100, "issue_ratio": 1})
    assert _field(corrected, "layer")["needs_review"]
    with pytest.raises(ValueError, match="review note"):
        confirm_review(corrected, ["layer"], 7, "reviewer@example.com", "")
    confirmed = confirm_review(corrected, ["layer"], 7, "reviewer@example.com", "Customer confirmed revision B")
    event = confirmed["events"][0]
    assert event["original_value"] == 6
    assert event["final_value"] == 8
    assert event["user_id"] == 7
    assert event["action"] == "corrected"
    assert _field(review, "layer")["value"] == 6
    changed_again = reconcile_review(confirmed, {"layer": 10, "qty": 9})
    assert not _field(changed_again, "layer").get("confirmation")
    assert changed_again["events"] == confirmed["events"]


def test_missing_values_cannot_be_confirmed_and_repeated_confirmation_is_idempotent():
    review = build_extraction_review({"layer": 6, "qty": 9}, "6L qty 9")
    with pytest.raises(ValueError, match="supply a value"):
        confirm_review(review, ["size"], 1, "staff@example.com", "")
    confirmed = confirm_review(review, ["issue_ratio"], 1, "staff@example.com", "Standard yield confirmed")
    repeated = confirm_review(confirmed, ["issue_ratio"], 1, "staff@example.com", "")
    assert len(repeated["events"]) == 1
    assert "issue_ratio" not in [item["field"] for item in pending_fields(repeated)]
