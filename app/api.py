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
# 報價相關 API
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
    """獲取報價列表，支援篩選和搜尋"""
    try:
        db = SessionLocal()
        query = db.query(QuoteHistory)

        # 日期篩選
        if start_date:
            start = datetime.fromisoformat(start_date)
            query = query.filter(QuoteHistory.created_at >= start)
        if end_date:
            end = datetime.fromisoformat(end_date)
            query = query.filter(QuoteHistory.created_at <= end)

        # 層數篩選
        if layer:
            query = query.filter(QuoteHistory.layer == layer)

        # 材料篩選
        if material:
            query = query.filter(QuoteHistory.material.ilike(f"%{material}%"))

        # 搜尋（報價編號或客戶ID）
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
    """獲取單一報價詳情"""
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
    """更新報價（價格、狀態、備註等）"""
    try:
        db = SessionLocal()
        quote = db.query(QuoteHistory).filter(QuoteHistory.id == quote_id).first()

        if not quote:
            raise HTTPException(status_code=404, detail="報價不存在")

        # 更新允許的欄位
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
    """刪除報價"""
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
# 統計相關 API
# ============================================================================

@router.get("/stats/summary")
def get_stats_summary(
    start_date: str = Query(None),
    end_date: str = Query(None)
):
    """獲取統計摘要"""
    try:
        db = SessionLocal()

        # 基本統計
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
    """按層數統計"""
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
    """按材料統計"""
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
