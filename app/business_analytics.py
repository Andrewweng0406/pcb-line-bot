"""Company-level RFQ and quote analytics."""

from collections import defaultdict
from datetime import datetime
from math import isfinite
from types import SimpleNamespace

from app.quote_metrics import to_float
from app.quote_outcomes import ALLOWED_OUTCOMES


def monetary_summary(quotes, value_field="total") -> list:
    groups = defaultdict(list)
    for quote in quotes:
        value = to_float(getattr(quote, value_field, None))
        if value is None:
            continue
        if not isfinite(value):
            continue
        currency = (getattr(quote, "currency", None) or "").strip().upper() or "UNKNOWN"
        groups[currency].append(value)
    return [{"currency": currency, "count": len(values),
             "total": round(sum(values), 2) if currency != "UNKNOWN" else None,
             "average": round(sum(values) / len(values), 2) if currency != "UNKNOWN" else None}
            for currency, values in sorted(groups.items())]


def single_currency_value(amounts, field):
    return amounts[0][field] if len(amounts) == 1 and amounts[0]["currency"] != "UNKNOWN" else None


def _month_key(value) -> str:
    if value is None:
        return "Unknown"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return "Unknown"
    return value.strftime("%Y-%m")


def get_outcome_stats(session, QuoteHistory) -> dict:
    quotes = session.query(QuoteHistory).all()
    counts = {outcome: 0 for outcome in sorted(ALLOWED_OUTCOMES)}
    for quote in quotes:
        outcome = quote.quote_outcome or "pending"
        if outcome not in counts:
            counts[outcome] = 0
        counts[outcome] += 1
    won = counts.get("won", 0)
    lost = counts.get("lost", 0)
    resolved = won + lost
    return {
        "counts": counts,
        "win_rate": round(won / resolved, 4) if resolved else None,
        "resolved_count": resolved,
        "total_count": len(quotes),
    }


def get_pricing_trends(session, QuoteHistory) -> list:
    groups = defaultdict(lambda: {"count": 0, "quotes": [], "margin_sum": 0.0, "margin_count": 0})
    for quote in session.query(QuoteHistory).all():
        key = _month_key(quote.rfq_received_at or quote.created_at)
        group = groups[key]
        group["count"] += 1
        group["quotes"].append(quote)
        margin = to_float(quote.actual_margin_pct)
        if margin is None:
            margin = to_float(quote.estimated_margin_pct)
        if margin is not None:
            group["margin_sum"] += margin
            group["margin_count"] += 1

    rows = []
    for period, data in sorted(groups.items()):
        amounts = monetary_summary(data["quotes"])
        rows.append({
            "period": period,
            "rfq_count": data["count"],
            "average_quote_value": single_currency_value(amounts, "average"),
            "amounts_by_currency": amounts,
            "average_margin_pct": round(data["margin_sum"] / data["margin_count"], 4)
            if data["margin_count"]
            else None,
        })
    return rows


def get_customer_analytics(session, Customer, QuoteHistory, limit: int = 10) -> list:
    customers = session.query(Customer).all()
    rows = []
    for customer in customers:
        quotes = (
            session.query(QuoteHistory)
            .filter(QuoteHistory.customer_id == customer.id)
            .all()
        )
        if not quotes:
            rows.append({
                "customer_id": customer.id,
                "company_name": customer.company_name,
                "total_rfqs": 0,
                "won": 0,
                "lost": 0,
                "win_rate": None,
                "total_quoted_value": 0,
                "total_won_value": 0,
                "quoted_by_currency": [],
                "won_by_currency": [],
                "average_quote": None,
                "average_margin_pct": None,
                "last_rfq_date": None,
            })
            continue
        won = [q for q in quotes if (q.quote_outcome or "pending") == "won"]
        lost = [q for q in quotes if (q.quote_outcome or "pending") == "lost"]
        resolved = len(won) + len(lost)
        margins = [
            margin for margin in (
                to_float(q.actual_margin_pct) if to_float(q.actual_margin_pct) is not None else to_float(q.estimated_margin_pct)
                for q in quotes
            )
            if margin is not None
        ]
        quoted_amounts = monetary_summary(quotes)
        won_amounts = monetary_summary([SimpleNamespace(currency=q.currency, total=q.final_price if q.final_price is not None else q.total) for q in won])
        last_rfq = max((q.rfq_received_at or q.created_at for q in quotes if q.rfq_received_at or q.created_at), default=None)
        rows.append({
            "customer_id": customer.id,
            "company_name": customer.company_name,
            "total_rfqs": len(quotes),
            "won": len(won),
            "lost": len(lost),
            "win_rate": round(len(won) / resolved, 4) if resolved else None,
            "total_quoted_value": single_currency_value(quoted_amounts, "total"),
            "total_won_value": single_currency_value(won_amounts, "total"),
            "average_quote": single_currency_value(quoted_amounts, "average"),
            "quoted_by_currency": quoted_amounts,
            "won_by_currency": won_amounts,
            "average_margin_pct": round(sum(margins) / len(margins), 4) if margins else None,
            "last_rfq_date": last_rfq.isoformat() if last_rfq else None,
        })
    return sorted(rows, key=lambda item: item["total_rfqs"], reverse=True)[:limit]
