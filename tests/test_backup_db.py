import json
import os
import stat
import sys

import pytest

sys.path.insert(0, "scripts")

from backup_db import BackupValidationError, backup, load_and_verify  # noqa: E402
from restore_db import RestoreSafetyError, restore_backup  # noqa: E402


def _seed(temp_db):
    from app.core.auth import hash_password

    with temp_db.SessionLocal() as session:
        user = temp_db.User(email="staff@example.com", password_hash=hash_password("pw"))
        customer = temp_db.Customer(company_name="ABC Corp")
        session.add_all([user, customer])
        session.commit()
        user_id, customer_id = user.id, customer.id

    temp_db.save_quote(
        "line:U1",
        {"layer": 6, "qty": 1},
        {"status": "success", "total": 100.0, "unit_price": 100.0},
        customer_id=customer_id,
        created_by_user_id=user_id,
    )


def test_backup_is_atomic_private_and_integrity_checked(temp_db, tmp_path):
    _seed(temp_db)
    output_path = backup(str(tmp_path))
    snapshot, report = load_and_verify(output_path)

    assert snapshot["format_version"] == 2
    assert report["integrity"] == "sha256-verified"
    assert report["table_counts"] == {"users": 1, "customers": 1, "quote_history": 1}
    assert snapshot["tables"]["quote_history"][0]["total"] == 100.0
    assert stat.S_IMODE(os.stat(output_path).st_mode) == 0o600
    assert not list(tmp_path.glob(".backup_*.tmp"))


def test_backup_detects_content_tampering(temp_db, tmp_path):
    _seed(temp_db)
    output_path = backup(str(tmp_path))
    with open(output_path, encoding="utf-8") as handle:
        snapshot = json.load(handle)
    snapshot["tables"]["quote_history"][0]["total"] = 999999
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle)

    with pytest.raises(BackupValidationError, match="checksum"):
        load_and_verify(output_path)


def test_backup_detects_broken_relationship(temp_db, tmp_path):
    _seed(temp_db)
    output_path = backup(str(tmp_path))
    with open(output_path, encoding="utf-8") as handle:
        snapshot = json.load(handle)
    snapshot["tables"]["quote_history"][0]["customer_id"] = 999
    # Rewriting the manifest cannot hide referential corruption.
    from backup_db import _sha256

    tables = snapshot["tables"]
    snapshot["manifest"] = {
        "table_counts": {name: len(rows) for name, rows in tables.items()},
        "table_sha256": {name: _sha256(rows) for name, rows in tables.items()},
        "content_sha256": _sha256(tables),
    }
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle)

    with pytest.raises(BackupValidationError, match="missing customer"):
        load_and_verify(output_path)


def test_restore_drill_recreates_exact_snapshot_in_empty_database(temp_db, tmp_path):
    _seed(temp_db)
    output_path = backup(str(tmp_path))
    target_url = f"sqlite:///{tmp_path / 'restore-drill.db'}"

    report = restore_backup(output_path, target_url, source_url="sqlite:///source.db")

    assert report["status"] == "restored-and-verified"
    assert report["table_counts"] == {"users": 1, "customers": 1, "quote_history": 1}
    with pytest.raises(RestoreSafetyError, match="not empty"):
        restore_backup(output_path, target_url, source_url="sqlite:///source.db")


def test_restore_refuses_source_database(temp_db, tmp_path):
    _seed(temp_db)
    output_path = backup(str(tmp_path))
    source_url = "sqlite:///same.db"
    with pytest.raises(RestoreSafetyError, match="configured source"):
        restore_backup(output_path, source_url, source_url=source_url)


def test_legacy_snapshot_remains_structurally_verifiable(temp_db, tmp_path):
    _seed(temp_db)
    output_path = backup(str(tmp_path))
    with open(output_path, encoding="utf-8") as handle:
        current = json.load(handle)
    legacy_path = tmp_path / "legacy.json"
    with open(legacy_path, "w", encoding="utf-8") as handle:
        json.dump(current["tables"], handle)

    _, report = load_and_verify(legacy_path)
    assert report["format_version"] == 1
    assert report["integrity"] == "structural-only"
