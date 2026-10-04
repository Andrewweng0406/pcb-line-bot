"""Restore a verified snapshot into a new, empty database only.

Set RESTORE_DATABASE_URL to the disposable target and run:
    python scripts/restore_db.py backups/backup_....json --confirm-empty-target
"""
import argparse
import os
import sys
from datetime import datetime

from sqlalchemy import DateTime, create_engine, func, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.core.database as db  # noqa: E402
from backup_db import (  # noqa: E402
    TABLE_MODELS,
    _sha256,
    load_and_verify,
    snapshot_tables,
    snapshot_tables_from_document,
)


class RestoreSafetyError(ValueError):
    """Raised when the requested restore target is not demonstrably disposable."""


def _deserialize_row(model, row: dict) -> dict:
    columns = {column.name: column for column in model.__table__.columns}
    values = dict(row)
    if model.__tablename__ == "users" and "role" not in values:
        values["role"] = "manager"
    for name, value in values.items():
        if value is not None and isinstance(columns[name].type, DateTime):
            values[name] = datetime.fromisoformat(value)
    return values


def restore_backup(snapshot_path: str, target_url: str, source_url: str | None = None) -> dict:
    if not target_url:
        raise RestoreSafetyError("RESTORE_DATABASE_URL is required.")
    if source_url and target_url == source_url:
        raise RestoreSafetyError("Refusing to restore over the configured source database.")

    snapshot, verification = load_and_verify(snapshot_path)
    expected_tables = snapshot_tables_from_document(snapshot)
    engine = create_engine(target_url)
    db.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        existing = {
            name: session.query(func.count(model.id)).scalar() or 0
            for name, model in TABLE_MODELS
        }
        if any(existing.values()):
            raise RestoreSafetyError(f"Restore target is not empty: {existing}")

        for name, model in TABLE_MODELS:
            session.add_all(
                model(**_deserialize_row(model, row)) for row in expected_tables[name]
            )
            session.flush()

        restored_tables = snapshot_tables(session)
        # Older snapshots predate nullable additive columns. Verify every
        # original value and reject unexpected non-null restored data.
        for name, rows in restored_tables.items():
            expected_by_id = {row["id"]: row for row in expected_tables[name]}
            for row in rows:
                expected = expected_by_id.get(row["id"], {})
                for key in set(row) - set(expected):
                    legacy_role = name == "users" and key == "role" and row[key] == "manager"
                    if row[key] is not None and not legacy_role:
                        raise RestoreSafetyError("Unexpected non-null column after restore.")
                    del row[key]
        if _sha256(restored_tables) != verification["content_sha256"]:
            raise RestoreSafetyError("Post-restore checksum does not match the snapshot.")

        if engine.dialect.name == "postgresql":
            for _, model in TABLE_MODELS:
                table = model.__tablename__
                session.execute(text(
                    "SELECT setval(pg_get_serial_sequence(:table_name, 'id'), "
                    "COALESCE((SELECT MAX(id) FROM " + table + "), 1), "
                    "EXISTS (SELECT 1 FROM " + table + "))"
                ), {"table_name": table})
        session.commit()

        return {
            "status": "restored-and-verified",
            "table_counts": verification["table_counts"],
            "content_sha256": verification["content_sha256"],
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot")
    parser.add_argument("--confirm-empty-target", action="store_true")
    args = parser.parse_args()
    if not args.confirm_empty_target:
        raise SystemExit("Pass --confirm-empty-target after verifying the target is disposable.")
    report = restore_backup(
        args.snapshot,
        os.getenv("RESTORE_DATABASE_URL", ""),
        os.getenv("DATABASE_URL"),
    )
    print(report)


if __name__ == "__main__":
    main()
