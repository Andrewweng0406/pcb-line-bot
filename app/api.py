from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime, timedelta
import app.core.database as db
from app.web import get_current_user_optional
from sqlalchemy import desc
from app.business_analytics import (
    get_customer_analytics,
    get_outcome_stats,
    get_pricing_trends,
)
from app.historical_intelligence import find_similar_quotes, historical_pricing_summary
from app.quote_metrics import calculate_margin, to_non_negative_float, to_non_negative_int
from app.quote_outcomes import normalize_lost_reason, normalize_outcome

router = APIRouter(prefix="/api", tags=["api"])


def require_user(user=Depends(get_current_user_optional)):
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# ============================================================================
# Quote-related API
# ============================================================================

@router.get("/quotes")
def get_quotes(
    start_date: str = Query(None),
    end_date: str = Query(None),
    layer: int = Query(None),
    material: str = Query(None),
    search: str = Query(None),
    limit: int = Query(100),
    user=Depends(require_user),
):
    """Get the quote list with filtering and search support."""
    try:
        session = db.SessionLocal()
        query = session.query(db.QuoteHistory)

        # Date filters
        if start_date:
            start = datetime.fromisoformat(start_date)
            query = query.filter(db.QuoteHistory.created_at >= start)
        if end_date:
            end = datetime.fromisoformat(end_date)
            query = query.filter(db.QuoteHistory.created_at <= end)

        # Layer filter
        if layer:
            query = query.filter(db.QuoteHistory.layer == layer)

        # Material filter
        if material:
            query = query.filter(db.QuoteHistory.material.ilike(f"%{material}%"))

        # Search by the submitting channel (LINE user id / "web:<user_id>")
        if search:
            query = query.filter(
                db.QuoteHistory.source_channel_id.ilike(f"%{search}%")
            )

        quotes = query.order_by(desc(db.QuoteHistory.created_at)).limit(limit).all()

        result = [
            {
                "id": q.id,
                "quote_no": q.quote_no,
                "source_channel_id": q.source_channel_id,
                "customer_id": q.customer_id,
                "status": q.status,
                "layer": q.layer,
                "material": q.material,
                "length_mm": q.length_mm,
                "width_mm": q.width_mm,
                "qty": q.qty,
                "total": q.total,
                "unit_price": q.unit_price,
                "created_at": q.created_at.isoformat()
            }
            for q in quotes
        ]

        session.close()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quotes/{quote_id}")
def get_quote(quote_id: int, user=Depends(require_user)):
    """Get details for a single quote."""
    try:
        session = db.SessionLocal()
        quote = session.query(db.QuoteHistory).filter(db.QuoteHistory.id == quote_id).first()
        session.close()

        if not quote:
            raise HTTPException(status_code=404, detail="報價不存在")

        return {
            "id": quote.id,
            "quote_no": quote.quote_no,
            "source_channel_id": quote.source_channel_id,
            "customer_id": quote.customer_id,
            "status": quote.status,
            "notes": quote.notes,
            "layer": quote.layer,
            "material": quote.material,
            "length_mm": quote.length_mm,
            "width_mm": quote.width_mm,
            "qty": quote.qty,
            "issue_ratio": quote.issue_ratio,
            "total": quote.total,
            "unit_price": quote.unit_price,
            "quote_outcome": quote.quote_outcome,
            "final_price": quote.final_price,
            "actual_cost": quote.actual_cost,
            "actual_margin_pct": quote.actual_margin_pct,
            "created_at": quote.created_at.isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/quotes/{quote_id}")
def update_quote(quote_id: int, data: dict, user=Depends(require_user)):
    """Update a quote, such as price, status, or notes."""
    try:
        session = db.SessionLocal()
        quote = session.query(db.QuoteHistory).filter(db.QuoteHistory.id == quote_id).first()

        if not quote:
            raise HTTPException(status_code=404, detail="報價不存在")

        # Update allowed fields
        if "total" in data:
            total = to_non_negative_float(data["total"])
            if total is None:
                raise HTTPException(status_code=400, detail="Invalid total")
            quote.total = total
        if "status" in data:
            quote.status = data["status"]
        if "notes" in data:
            quote.notes = data["notes"]
        if "quote_outcome" in data:
            outcome = normalize_outcome(data["quote_outcome"])
            if outcome is None:
                raise HTTPException(status_code=400, detail="Invalid quote_outcome")
            quote.quote_outcome = outcome
        if "final_price" in data:
            final_price = to_non_negative_float(data["final_price"])
            if data["final_price"] not in (None, "") and final_price is None:
                raise HTTPException(status_code=400, detail="Invalid final_price")
            quote.final_price = final_price
        if "actual_cost" in data:
            actual_cost = to_non_negative_float(data["actual_cost"])
            if data["actual_cost"] not in (None, "") and actual_cost is None:
                raise HTTPException(status_code=400, detail="Invalid actual_cost")
            quote.actual_cost = actual_cost
        if "production_lead_time_actual" in data:
            days = to_non_negative_int(data["production_lead_time_actual"])
            if data["production_lead_time_actual"] not in (None, "") and days is None:
                raise HTTPException(status_code=400, detail="Invalid production_lead_time_actual")
            quote.production_lead_time_actual = days
        if "lost_reason" in data:
            lost_reason = normalize_lost_reason(data["lost_reason"])
            if data["lost_reason"] not in (None, "") and lost_reason is None:
                raise HTTPException(status_code=400, detail="Invalid lost_reason")
            quote.lost_reason = lost_reason
        if "lost_reason_note" in data:
            quote.lost_reason_note = data["lost_reason_note"] or None
        if "competitor_name" in data:
            quote.competitor_name = data["competitor_name"] or None
        if "competitor_price" in data:
            competitor_price = to_non_negative_float(data["competitor_price"])
            if data["competitor_price"] not in (None, "") and competitor_price is None:
                raise HTTPException(status_code=400, detail="Invalid competitor_price")
            quote.competitor_price = competitor_price
        quote.actual_margin_pct = calculate_margin(quote.final_price, quote.actual_cost)
        quote.updated_by_user_id = user.id

        session.commit()
        session.close()

        return {"status": "success", "message": "報價已更新"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quotes/{quote_id}/similar")
def get_similar_quotes(quote_id: int, limit: int = Query(10), user=Depends(require_user)):
    """Return explainable structured-similarity matches for one quote."""
    try:
        session = db.SessionLocal()
        quote = session.query(db.QuoteHistory).filter(db.QuoteHistory.id == quote_id).first()
        if not quote:
            session.close()
            raise HTTPException(status_code=404, detail="報價不存在")
        matches = find_similar_quotes(session, db.QuoteHistory, quote, limit=limit)
        session.close()
        return matches
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quotes/{quote_id}/historical-summary")
def get_historical_summary(quote_id: int, user=Depends(require_user)):
    """Return pricing reference stats from the closest historical quotes."""
    try:
        session = db.SessionLocal()
        quote = session.query(db.QuoteHistory).filter(db.QuoteHistory.id == quote_id).first()
        if not quote:
            session.close()
            raise HTTPException(status_code=404, detail="報價不存在")
        similar = find_similar_quotes(session, db.QuoteHistory, quote, limit=50)
        session.close()
        return historical_pricing_summary(similar)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/quotes/{quote_id}")
def delete_quote(quote_id: int, user=Depends(require_user)):
    """Delete a quote."""
    try:
        session = db.SessionLocal()
        quote = session.query(db.QuoteHistory).filter(db.QuoteHistory.id == quote_id).first()

        if not quote:
            raise HTTPException(status_code=404, detail="報價不存在")

        session.delete(quote)
        session.commit()
        session.close()

        return {"status": "success", "message": "報價已刪除"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Statistics-related API
# ============================================================================

@router.get("/stats/summary")
def get_stats_summary(
    start_date: str = Query(None),
    end_date: str = Query(None),
    user=Depends(require_user),
):
    """Get the statistics summary."""
    try:
        session = db.SessionLocal()

        # Basic statistics
        query = session.query(db.QuoteHistory)

        if start_date:
            start = datetime.fromisoformat(start_date)
            query = query.filter(db.QuoteHistory.created_at >= start)
        if end_date:
            end = datetime.fromisoformat(end_date)
            query = query.filter(db.QuoteHistory.created_at <= end)

        quotes = query.all()

        total_count = len(quotes)
        total_amount = sum(q.total for q in quotes) if quotes else 0
        avg_price = total_amount / total_count if total_count > 0 else 0

        session.close()

        return {
            "total_count": total_count,
            "total_amount": round(total_amount, 2),
            "avg_price": round(avg_price, 2)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/by-layer")
def get_stats_by_layer(user=Depends(require_user)):
    """Group statistics by layer."""
    try:
        return db.get_stats_by_layer()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/by-material")
def get_stats_by_material(user=Depends(require_user)):
    """Group statistics by material."""
    try:
        return db.get_stats_by_material()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/outcomes")
def get_stats_outcomes(user=Depends(require_user)):
    try:
        session = db.SessionLocal()
        result = get_outcome_stats(session, db.QuoteHistory)
        session.close()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/pricing-trends")
def get_stats_pricing_trends(user=Depends(require_user)):
    try:
        session = db.SessionLocal()
        result = get_pricing_trends(session, db.QuoteHistory)
        session.close()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/top-customers")
def get_stats_top_customers(user=Depends(require_user)):
    try:
        session = db.SessionLocal()
        result = get_customer_analytics(session, db.Customer, db.QuoteHistory)
        session.close()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
