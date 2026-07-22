from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, Text, JSON,
    ForeignKey, func, inspect, text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
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


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), nullable=False, index=True)
    contact = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    common_specs = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class QuoteHistory(Base):
    __tablename__ = "quote_history"

    id = Column(Integer, primary_key=True, index=True)
    # Who/what submitted this quote: a LINE user_id (e.g. "Uabc123...") or a
    # web session token (e.g. "web:<user_id>"). Not a business customer.
    source_channel_id = Column(String(255), index=True)
    # The actual business customer this quote is for, if known/linked.
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    layer = Column(Integer)
    material = Column(String(100))
    length_mm = Column(Float, nullable=True)
    width_mm = Column(Float, nullable=True)
    qty = Column(Integer)
    issue_ratio = Column(Float, default=1.0)
    total = Column(Float)
    unit_price = Column(Float)
    status = Column(String(20), default="pending", index=True)
    notes = Column(Text, nullable=True)
    quote_no = Column(String(50), nullable=True, index=True)
    # Full parsed input / full calculate_quote() output, kept as JSON so new
    # fields added to the parser or quote engine don't require a migration.
    spec_json = Column(JSON, nullable=True)
    breakdown_json = Column(JSON, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    customer = relationship("Customer")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    updated_by = relationship("User", foreign_keys=[updated_by_user_id])


def _run_migrations(engine) -> None:
    """Hand-rolled, idempotent additive migration. No Alembic yet — a single
    evolving table doesn't justify that infra at this stage (see the
    implementation plan's Global Constraints for the full rationale).
    """
    inspector = inspect(engine)
    if "quote_history" not in inspector.get_table_names():
        return  # fresh database, create_all() already built the current schema

    columns = {col["name"] for col in inspector.get_columns("quote_history")}

    with engine.begin() as conn:
        if "source_channel_id" not in columns and "customer_id" in columns:
            conn.execute(text(
                "ALTER TABLE quote_history RENAME COLUMN customer_id TO source_channel_id"
            ))
            columns.discard("customer_id")
            columns.add("source_channel_id")

        additions = {
            "customer_id": "INTEGER",
            "status": "VARCHAR(20) DEFAULT 'pending'",
            "notes": "TEXT",
            "quote_no": "VARCHAR(50)",
            "spec_json": "JSON",
            "breakdown_json": "JSON",
            "created_by_user_id": "INTEGER",
            "updated_by_user_id": "INTEGER",
        }
        for column_name, column_type in additions.items():
            if column_name not in columns:
                conn.execute(text(
                    f"ALTER TABLE quote_history ADD COLUMN {column_name} {column_type}"
                ))


def init_db():
    Base.metadata.create_all(bind=engine)
    _run_migrations(engine)
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


def _generate_quote_no(db: Session) -> str:
    today_str = datetime.utcnow().strftime("%Y%m%d")
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    count_today = db.query(func.count(QuoteHistory.id)).filter(
        QuoteHistory.created_at >= today_start
    ).scalar() or 0
    return f"PCB-{today_str}-{count_today + 1:03d}"


def save_quote(
    source_channel_id: str,
    parsed: dict,
    result: dict,
    customer_id: int = None,
    created_by_user_id: int = None,
) -> bool:
    try:
        db = SessionLocal()
        quote = QuoteHistory(
            source_channel_id=source_channel_id,
            customer_id=customer_id,
            layer=parsed.get("layer"),
            material=parsed.get("material"),
            length_mm=parsed.get("length_mm"),
            width_mm=parsed.get("width_mm"),
            qty=parsed.get("qty"),
            issue_ratio=result.get("issue_ratio", 1.0),
            total=result.get("total"),
            unit_price=result.get("unit_price"),
            status="pending",
            quote_no=_generate_quote_no(db),
            spec_json=parsed,
            breakdown_json=result,
            created_by_user_id=created_by_user_id,
        )
        db.add(quote)
        db.commit()
        db.close()
        logger.info(f"Quote saved for channel {source_channel_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving quote: {e}")
        return False


def get_system_stats() -> dict:
    """Get system statistics."""
    try:
        db = SessionLocal()
        from datetime import datetime, timedelta

        # Today's quote count
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = db.query(func.count(QuoteHistory.id)).filter(
            QuoteHistory.created_at >= today_start
        ).scalar() or 0

        # Total quote count
        total_count = db.query(func.count(QuoteHistory.id)).scalar() or 0

        # Most recent quote time
        last_quote = db.query(QuoteHistory).order_by(
            QuoteHistory.created_at.desc()
        ).first()
        last_quote_time = last_quote.created_at if last_quote else None

        # Average price across all quotes
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


def get_stats_by_layer() -> list:
    db = SessionLocal()
    quotes = db.query(QuoteHistory).all()
    db.close()

    stats = {}
    for q in quotes:
        layer = q.layer
        if layer not in stats:
            stats[layer] = {"count": 0, "total": 0}
        stats[layer]["count"] += 1
        stats[layer]["total"] += q.total or 0

    return [
        {"layer": k, "count": v["count"], "total": round(v["total"], 2)}
        for k, v in sorted(stats.items())
    ]


def get_stats_by_material() -> list:
    db = SessionLocal()
    quotes = db.query(QuoteHistory).all()
    db.close()

    stats = {}
    for q in quotes:
        material = q.material or "Unknown"
        if material not in stats:
            stats[material] = {"count": 0, "total": 0}
        stats[material]["count"] += 1
        stats[material]["total"] += q.total or 0

    return [
        {"material": k, "count": v["count"], "total": round(v["total"], 2)}
        for k, v in sorted(stats.items())
    ]
