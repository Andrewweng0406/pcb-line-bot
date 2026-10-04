"""Create and verify portable, integrity-checked database snapshots.

Usage:
    python scripts/backup_db.py [output_dir]
    python scripts/backup_db.py --verify backups/backup_*.json

This complements, but does not replace, provider-native PostgreSQL backups.
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.core.database as db  # noqa: E402


try:
    from .backup_format import (
        FORMAT_VERSION, BackupValidationError, _sha256, load_and_verify,
        verify_snapshot, snapshot_tables_from_document,
    )
except ImportError:
    from backup_format import (
        FORMAT_VERSION, BackupValidationError, _sha256, load_and_verify,
        verify_snapshot, snapshot_tables_from_document,
    )
TABLE_MODELS = (
    ("users", db.User),
    ("customers", db.Customer),
    ("quote_history", db.QuoteHistory),
)


def _row_to_dict(row) -> dict:
    return {
        column.name: getattr(row, column.name).isoformat()
        if hasattr(getattr(row, column.name), "isoformat")
        else getattr(row, column.name)
        for column in row.__table__.columns
    }


def snapshot_tables(session) -> dict:
    return {
        name: [_row_to_dict(row) for row in session.query(model).order_by(model.id).all()]
        for name, model in TABLE_MODELS
    }


def build_snapshot(session) -> dict:
    tables = snapshot_tables(session)
    return {
        "format_version": FORMAT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tables": tables,
        "manifest": {
            "table_counts": {name: len(rows) for name, rows in tables.items()},
            "table_sha256": {name: _sha256(rows) for name, rows in tables.items()},
            "content_sha256": _sha256(tables),
        },
    }


def backup(output_dir: str = "backups") -> str:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    session = db.SessionLocal()
    try:
        snapshot = build_snapshot(session)
    finally:
        session.close()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    final_path = output_path / f"backup_{timestamp}.json"
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=output_path, prefix=".backup_", suffix=".tmp", delete=False
        ) as handle:
            temp_name = handle.name
            os.chmod(temp_name, 0o600)
            json.dump(snapshot, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, final_path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)

    report = verify_snapshot(snapshot)
    print(
        f"Backed up {report['table_counts']} to {final_path} "
        f"(sha256 {report['content_sha256']})"
    )
    return str(final_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", nargs="?", default="backups")
    parser.add_argument("--verify", metavar="SNAPSHOT")
    args = parser.parse_args()
    if args.verify:
        _, report = load_and_verify(args.verify)
        print(json.dumps(report, sort_keys=True))
        return
    backup(args.output_dir)


if __name__ == "__main__":
    main()
