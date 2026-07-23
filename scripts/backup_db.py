"""Dump all rows from every table to a single timestamped JSON file.

Usage: DATABASE_URL=<connection string> python scripts/backup_db.py [output_dir]

Not a substitute for a real pg_dump/Railway-managed backup — this is a
lightweight, dependency-free snapshot suitable for a pilot-scale database.
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.core.database as db  # noqa: E402


def _row_to_dict(row) -> dict:
    return {
        column.name: getattr(row, column.name).isoformat()
        if hasattr(getattr(row, column.name), "isoformat")
        else getattr(row, column.name)
        for column in row.__table__.columns
    }


def backup(output_dir: str = "backups") -> str:
    os.makedirs(output_dir, exist_ok=True)
    session = db.SessionLocal()
    try:
        snapshot = {
            "users": [_row_to_dict(r) for r in session.query(db.User).all()],
            "customers": [_row_to_dict(r) for r in session.query(db.Customer).all()],
            "quote_history": [_row_to_dict(r) for r in session.query(db.QuoteHistory).all()],
        }
    finally:
        session.close()

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f"backup_{timestamp}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    counts = {k: len(v) for k, v in snapshot.items()}
    print(f"Backed up {counts} to {output_path}")
    return output_path


if __name__ == "__main__":
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "backups"
    backup(output_dir)
