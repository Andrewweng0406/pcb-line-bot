"""Portable snapshot validation without application or database dependencies."""

import hashlib
import json
from pathlib import Path

FORMAT_VERSION = 2
TABLE_NAMES = ("users", "customers", "quote_history")


class BackupValidationError(ValueError):
    """Snapshot is malformed or fails an integrity check."""


def _sha256(value):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _validate_rows(tables):
    if set(tables) != set(TABLE_NAMES):
        raise BackupValidationError(f"Snapshot tables must be exactly: {', '.join(sorted(TABLE_NAMES))}.")
    for name, rows in tables.items():
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise BackupValidationError(f"Table {name} must contain a list of rows.")
        ids = [row.get("id") for row in rows]
        if any(type(value) is not int or value <= 0 for value in ids) or len(ids) != len(set(ids)):
            raise BackupValidationError(f"Table {name} contains missing or duplicate IDs.")
    user_ids = {row["id"] for row in tables["users"]}
    customer_ids = {row["id"] for row in tables["customers"]}
    for quote in tables["quote_history"]:
        for field, valid_ids in (("customer_id", customer_ids), ("created_by_user_id", user_ids), ("updated_by_user_id", user_ids)):
            value = quote.get(field)
            if value is not None and (type(value) is not int or value not in valid_ids):
                target = "customer" if field == "customer_id" else "user"
                raise BackupValidationError(f"Quote {quote['id']} references missing {target} {value}.")


def verify_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        raise BackupValidationError("Snapshot root must be an object.")
    if snapshot.get("format_version") == FORMAT_VERSION:
        tables, manifest = snapshot.get("tables"), snapshot.get("manifest")
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
        return {"format_version": FORMAT_VERSION, "integrity": "sha256-verified", "table_counts": counts, "content_sha256": manifest["content_sha256"]}
    if "format_version" in snapshot and (type(snapshot["format_version"]) is not int or snapshot["format_version"] != 1):
        raise BackupValidationError("Unsupported snapshot format version.")
    tables = {name: snapshot.get(name) for name in TABLE_NAMES}
    _validate_rows(tables)
    return {"format_version": 1, "integrity": "structural-only", "table_counts": {name: len(rows) for name, rows in tables.items()}, "content_sha256": _sha256(tables)}


def load_and_verify(path: str | Path):
    try:
        with open(path, encoding="utf-8") as handle:
            snapshot = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupValidationError(f"Unable to read snapshot: {exc}") from exc
    return snapshot, verify_snapshot(snapshot)


def snapshot_tables_from_document(snapshot):
    if snapshot.get("format_version") == FORMAT_VERSION:
        return snapshot["tables"]
    return {name: snapshot[name] for name in TABLE_NAMES}
