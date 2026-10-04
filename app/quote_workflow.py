from app.extraction_review import release_pending


def validate_status_transition(quote, status):
    if status not in {"pending", "approved", "ordered"}:
        raise ValueError("Invalid quote status")
    if status != quote.status and status in {"approved", "ordered"} and release_pending(quote.spec_json):
        raise PermissionError("Confirm the pending extraction fields before approving this quote.")
