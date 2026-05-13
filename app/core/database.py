from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class QuoteHistory(Base):
    __tablename__ = "quote_history"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(255), index=True)
    layer = Column(Integer)
    material = Column(String(100))
    length_mm = Column(Float, nullable=True)
    width_mm = Column(Float, nullable=True)
    qty = Column(Integer)
    issue_ratio = Column(Float, default=1.0)
    total = Column(Float)
    unit_price = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


def init_db():
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized")


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_recent_quotes(limit: int = 5) -> list:
    try:
        db = SessionLocal()
        quotes = db.query(QuoteHistory).order_by(
            QuoteHistory.id.desc()
        ).limit(limit).all()
        db.close()
        return [(q.created_at, q.layer, q.material, q.total) for q in quotes]
    except Exception as e:
        logger.error(f"Error getting recent quotes: {e}")
        return []


def search_quotes(keyword: str, limit: int = 10) -> list:
    try:
        db = SessionLocal()
        quotes = db.query(QuoteHistory).filter(
            (QuoteHistory.layer == int(keyword)) if keyword.isdigit() else
            (QuoteHistory.material.ilike(f"%{keyword}%"))
        ).order_by(
            QuoteHistory.id.desc()
        ).limit(limit).all()
        db.close()
        return [(q.created_at, q.layer, q.material, q.total) for q in quotes]
    except Exception as e:
        logger.error(f"Error searching quotes: {e}")
        return []


def get_average_price(keyword: str) -> tuple:
    try:
        db = SessionLocal()
        result = db.query(
            func.avg(QuoteHistory.total),
            func.count(QuoteHistory.id)
        ).filter(
            (QuoteHistory.layer == int(keyword)) if keyword.isdigit() else
            (QuoteHistory.material.ilike(f"%{keyword}%"))
        ).first()
        db.close()

        if result[0] is None:
            return 0, 0
        return float(result[0]), int(result[1])
    except Exception as e:
        logger.error(f"Error getting average price: {e}")
        return 0, 0


def save_quote(customer_id: str, parsed: dict, result: dict) -> bool:
    try:
        db = SessionLocal()
        quote = QuoteHistory(
            customer_id=customer_id,
            layer=parsed.get("layer"),
            material=parsed.get("material"),
            length_mm=parsed.get("length_mm"),
            width_mm=parsed.get("width_mm"),
            qty=parsed.get("qty"),
            issue_ratio=result.get("issue_ratio", 1.0),
            total=result.get("total"),
            unit_price=result.get("unit_price")
        )
        db.add(quote)
        db.commit()
        db.close()
        logger.info(f"Quote saved for customer {customer_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving quote: {e}")
        return False


def get_system_stats() -> dict:
    """獲取系統統計信息"""
    try:
        db = SessionLocal()
        from datetime import datetime, timedelta

        # 今日報價次數
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = db.query(func.count(QuoteHistory.id)).filter(
            QuoteHistory.created_at >= today_start
        ).scalar() or 0

        # 總報價次數
        total_count = db.query(func.count(QuoteHistory.id)).scalar() or 0

        # 最後一筆報價時間
        last_quote = db.query(QuoteHistory).order_by(
            QuoteHistory.created_at.desc()
        ).first()
        last_quote_time = last_quote.created_at if last_quote else None

        # 所有報價的平均價格
        avg_price = db.query(func.avg(QuoteHistory.total)).scalar() or 0

        db.close()

        return {
            "today_count": today_count,
            "total_count": total_count,
            "last_quote_time": last_quote_time,
            "avg_price": round(float(avg_price), 0) if avg_price else 0,
        }
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        return {
            "today_count": 0,
            "total_count": 0,
            "last_quote_time": None,
            "avg_price": 0,
        }
