"""Create and verify portable, integrity-checked database snapshots.

Usage:
    python scripts/backup_db.py [output_dir]
    python scripts/backup_db.py --verify backups/backup_*.json

This complements, but does not replace, provider-native PostgreSQL backups.
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.core.database as db  # noqa: E402


FORMAT_VERSION = 2
TABLE_MODELS = (
    ("users", db.User),
    ("customers", db.Customer),
    ("quote_history", db.QuoteHistory),
)


class BackupValidationError(ValueError):
    """Raised when a snapshot is malformed or fails an integrity check."""


def _row_to_dict(row) -> dict:
    return {
        column.name: getattr(row, column.name).isoformat()
        if hasattr(getattr(row, column.name), "isoformat")
        else getattr(row, column.name)
        for column in row.__table__.columns
    }


def _canonical_bytes(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(value) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


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


def _validate_rows(tables: dict) -> None:
    expected = {name for name, _ in TABLE_MODELS}
    if set(tables) != expected:
        raise BackupValidationError(
            f"Snapshot tables must be exactly: {', '.join(sorted(expected))}."
        )
    for name, rows in tables.items():
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise BackupValidationError(f"Table {name} must contain a list of rows.")
        ids = [row.get("id") for row in rows]
        if any(value is None for value in ids) or len(ids) != len(set(ids)):
            raise BackupValidationError(f"Table {name} contains missing or duplicate IDs.")

    user_ids = {row["id"] for row in tables["users"]}
    customer_ids = {row["id"] for row in tables["customers"]}
    for quote in tables["quote_history"]:
        if quote.get("customer_id") is not None and quote["customer_id"] not in customer_ids:
            raise BackupValidationError(
                f"Quote {quote['id']} references missing customer {quote['customer_id']}."
            )
        for field in ("created_by_user_id", "updated_by_user_id"):
            if quote.get(field) is not None and quote[field] not in user_ids:
                raise BackupValidationError(
                    f"Quote {quote['id']} references missing user {quote[field]}."
                )


def verify_snapshot(snapshot: dict) -> dict:
    if not isinstance(snapshot, dict):
        raise BackupValidationError("Snapshot root must be an object.")

    if snapshot.get("format_version") == FORMAT_VERSION:
        tables = snapshot.get("tables")
        manifest = snapshot.get("manifest")
        if not isinstance(tables, dict) or not isinstance(manifest, dict):
            raise BackupValidationError("Snapshot tables or manifest is missing.")
        _validate_rows(tables)
        counts = {name: len(rows) for name, rows in tables.items()}
        hashes = {name: _sha256(rows) for name, rows in tables.items()}
        if manifest.get("table_counts") != counts:
            raise BackupValidationError("Snapshot row counts do not match the manifest.")
        if manifest.get("table_sha256") != hashes:
            raise BackupValidationError("Snapshot table checksum does not match the manifest.")
        if manifest.get("content_sha256") != _sha256(tables):
            raise BackupValidationError("Snapshot content checksum does not match the manifest.")
        return {
            "format_version": FORMAT_VERSION,
            "integrity": "sha256-verified",
            "table_counts": counts,
            "content_sha256": manifest["content_sha256"],
        }

    # Version 1 snapshots were plain top-level table lists. They remain readable,
    # but cannot prove that their contents have not changed since creation.
    tables = {name: snapshot.get(name) for name, _ in TABLE_MODELS}
    _validate_rows(tables)
    return {
        "format_version": 1,
        "integrity": "structural-only",
        "table_counts": {name: len(rows) for name, rows in tables.items()},
        "content_sha256": _sha256(tables),
    }


def load_and_verify(path: str | Path) -> tuple[dict, dict]:
    try:
        with open(path, encoding="utf-8") as handle:
            snapshot = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupValidationError(f"Unable to read snapshot: {exc}") from exc
    return snapshot, verify_snapshot(snapshot)


def snapshot_tables_from_document(snapshot: dict) -> dict:
    if snapshot.get("format_version") == FORMAT_VERSION:
        return snapshot["tables"]
    return {name: snapshot[name] for name, _ in TABLE_MODELS}


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
