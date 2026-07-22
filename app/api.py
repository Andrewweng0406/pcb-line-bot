from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime, timedelta
import app.core.database as db
from app.web import get_current_user_optional
from sqlalchemy import desc

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
            quote.total = data["total"]
        if "status" in data:
            quote.status = data["status"]
        if "notes" in data:
            quote.notes = data["notes"]
        quote.updated_by_user_id = user.id

        session.commit()
        session.close()

        return {"status": "success", "message": "報價已更新"}
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
