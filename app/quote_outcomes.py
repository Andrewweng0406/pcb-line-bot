"""Commercial quote outcome constants and validation helpers."""

ALLOWED_OUTCOMES = {"pending", "won", "lost", "no_response", "cancelled"}
ALLOWED_LOST_REASONS = {
    "price",
    "lead_time",
    "capability",
    "competitor",
    "customer_cancelled",
    "no_budget",
    "no_response",
    "unknown",
    "other",
}

OUTCOME_LABELS = {
    "pending": "Pending",
    "won": "Won",
    "lost": "Lost",
    "no_response": "No Response",
    "cancelled": "Cancelled",
}

LOST_REASON_LABELS = {
    "price": "Price",
    "lead_time": "Lead Time",
    "capability": "Capability",
    "competitor": "Competitor",
    "customer_cancelled": "Customer Cancelled",
    "no_budget": "No Budget",
    "no_response": "No Response",
    "unknown": "Unknown",
    "other": "Other",
}


def normalize_outcome(value):
    if value is None or value == "":
        return None
    normalized = str(value).strip().lower()
    if normalized not in ALLOWED_OUTCOMES:
        return None
    return normalized


def normalize_lost_reason(value):
    if value is None or value == "":
        return None
    normalized = str(value).strip().lower()
    if normalized not in ALLOWED_LOST_REASONS:
        return None
    return normalized
