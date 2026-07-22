from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
from app.core.database import (
    QuoteHistory,
    SessionLocal,
    get_recent_quotes,
    search_quotes,
    get_system_stats
)
from sqlalchemy import desc, and_

router = APIRouter(prefix="/api", tags=["api"])

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
    limit: int = Query(100)
):
    """Get the quote list with filtering and search support."""
    try:
        db = SessionLocal()
        query = db.query(QuoteHistory)

        # Date filters
        if start_date:
            start = datetime.fromisoformat(start_date)
            query = query.filter(QuoteHistory.created_at >= start)
        if end_date:
            end = datetime.fromisoformat(end_date)
            query = query.filter(QuoteHistory.created_at <= end)

        # Layer filter
        if layer:
            query = query.filter(QuoteHistory.layer == layer)

        # Material filter
        if material:
            query = query.filter(QuoteHistory.material.ilike(f"%{material}%"))

        # Search by quote number or customer ID
        if search:
            query = query.filter(
                QuoteHistory.customer_id.ilike(f"%{search}%")
            )

        quotes = query.order_by(desc(QuoteHistory.created_at)).limit(limit).all()

        result = [
            {
                "id": q.id,
                "customer_id": q.customer_id,
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

        db.close()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quotes/{quote_id}")
def get_quote(quote_id: int):
    """Get details for a single quote."""
    try:
        db = SessionLocal()
        quote = db.query(QuoteHistory).filter(QuoteHistory.id == quote_id).first()
        db.close()

        if not quote:
            raise HTTPException(status_code=404, detail="報價不存在")

        return {
            "id": quote.id,
            "customer_id": quote.customer_id,
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
def update_quote(quote_id: int, data: dict):
    """Update a quote, such as price, status, or notes."""
    try:
        db = SessionLocal()
        quote = db.query(QuoteHistory).filter(QuoteHistory.id == quote_id).first()

        if not quote:
            raise HTTPException(status_code=404, detail="報價不存在")

        # Update allowed fields
        if "total" in data:
            quote.total = data["total"]

        db.commit()
        db.close()

        return {"status": "success", "message": "報價已更新"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/quotes/{quote_id}")
def delete_quote(quote_id: int):
    """Delete a quote."""
    try:
        db = SessionLocal()
        quote = db.query(QuoteHistory).filter(QuoteHistory.id == quote_id).first()

        if not quote:
            raise HTTPException(status_code=404, detail="報價不存在")

        db.delete(quote)
        db.commit()
        db.close()

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
    end_date: str = Query(None)
):
    """Get the statistics summary."""
    try:
        db = SessionLocal()

        # Basic statistics
        query = db.query(QuoteHistory)

        if start_date:
            start = datetime.fromisoformat(start_date)
            query = query.filter(QuoteHistory.created_at >= start)
        if end_date:
            end = datetime.fromisoformat(end_date)
            query = query.filter(QuoteHistory.created_at <= end)

        quotes = query.all()

        total_count = len(quotes)
        total_amount = sum(q.total for q in quotes) if quotes else 0
        avg_price = total_amount / total_count if total_count > 0 else 0

        db.close()

        return {
            "total_count": total_count,
            "total_amount": round(total_amount, 2),
            "avg_price": round(avg_price, 2)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/by-layer")
def get_stats_by_layer():
    """Group statistics by layer."""
    try:
        db = SessionLocal()
        quotes = db.query(QuoteHistory).all()

        stats = {}
        for q in quotes:
            layer = q.layer
            if layer not in stats:
                stats[layer] = {"count": 0, "total": 0}
            stats[layer]["count"] += 1
            stats[layer]["total"] += q.total

        result = [
            {"layer": k, "count": v["count"], "total": round(v["total"], 2)}
            for k, v in sorted(stats.items())
        ]

        db.close()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/by-material")
def get_stats_by_material():
    """Group statistics by material."""
    try:
        db = SessionLocal()
        quotes = db.query(QuoteHistory).all()

        stats = {}
        for q in quotes:
            material = q.material or "Unknown"
            if material not in stats:
                stats[material] = {"count": 0, "total": 0}
            stats[material]["count"] += 1
            stats[material]["total"] += q.total

        result = [
            {"material": k, "count": v["count"], "total": round(v["total"], 2)}
            for k, v in sorted(stats.items())
        ]

        db.close()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
