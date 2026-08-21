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
    "pending": "待定",
    "won": "已成交",
    "lost": "已流失",
    "no_response": "未回覆",
    "cancelled": "已取消",
}

LOST_REASON_LABELS = {
    "price": "價格",
    "lead_time": "交期",
    "capability": "製程能力",
    "competitor": "競爭對手",
    "customer_cancelled": "客戶取消",
    "no_budget": "無預算",
    "no_response": "未回覆",
    "unknown": "未知",
    "other": "其他",
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
