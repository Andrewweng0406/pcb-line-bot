from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import subprocess
import sys

import pytest

from scripts.check_backup_health import check_health, verify_archive
from scripts.backup_format import _sha256, verify_snapshot, BackupValidationError


NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def snapshot(tmp_path, age=1):
    tables = {"users": [], "customers": [], "quote_history": []}
    document = {"format_version": 2, "created_at": (NOW - timedelta(hours=age)).isoformat(), "tables": tables, "manifest": {
        "table_counts": {k: 0 for k in tables}, "table_sha256": {k: _sha256(v) for k, v in tables.items()}, "content_sha256": _sha256(tables),
    }}
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(document)); path.chmod(0o600)
    return path


def archive(tmp_path, entries=None, hashes=None):
    entries = entries if entries is not None else [("quote.xlsx", b"file-content")]
    path = tmp_path / "files.tar.gz"
    with tarfile.open(path, "w:gz") as handle:
        for name, content in entries:
            info = tarfile.TarInfo(name); info.size = len(content)
            handle.addfile(info, io.BytesIO(content))
    manifest = tmp_path / "files.json"
    manifest.write_text(json.dumps(hashes if hashes is not None else {name: hashlib.sha256(content).hexdigest() for name, content in entries}))
    path.chmod(0o600); manifest.chmod(0o600)
    return path, manifest


def test_healthy_snapshot_and_files_do_not_claim_automatic_backups(tmp_path):
    snap = snapshot(tmp_path)
    files, manifest = archive(tmp_path)
    report = check_health(snap, archive=files, manifest=manifest, now=NOW)
    assert report["status"] == "healthy"
    assert report["automatic_backups"] == "not_assessed"
    assert report["snapshot"]["age_hours"] == 1
    assert report["files"] == {"status": "sha256-verified", "count": 1}
    assert "tables" not in report["snapshot"]


@pytest.mark.parametrize("age,issue", [(25, "snapshot_stale"), (-1, "snapshot_future_timestamp")])
def test_stale_and_future_backups_are_unhealthy(tmp_path, age, issue):
    report = check_health(snapshot(tmp_path, age), now=NOW)
    assert report["status"] == "unhealthy" and issue in report["issues"]


def test_public_permissions_and_symlinks_are_unhealthy(tmp_path):
    snap = snapshot(tmp_path); snap.chmod(0o644)
    assert "snapshot_permissions_or_type" in check_health(snap, now=NOW)["issues"]
    link = tmp_path / "link.json"; link.symlink_to(snap)
    assert "snapshot_permissions_or_type" in check_health(link, now=NOW)["issues"]


def test_tampering_missing_files_and_legacy_snapshots_are_unhealthy(tmp_path):
    snap = snapshot(tmp_path)
    document = json.loads(snap.read_text())
    document["manifest"]["content_sha256"] = "0" * 64
    snap.write_text(json.dumps(document))
    assert check_health(snap, now=NOW)["status"] == "unhealthy"
    assert check_health(tmp_path / "missing.json", now=NOW)["status"] == "unhealthy"
    snap.write_text(json.dumps(document["tables"]))
    assert "snapshot_unverified_legacy" in check_health(snap, now=NOW)["issues"]


@pytest.mark.parametrize("entries,hashes", [
    ([("quote.xlsx", b"wrong")], {"quote.xlsx": hashlib.sha256(b"right").hexdigest()}),
    ([], {"missing.xlsx": "0" * 64}),
    ([("extra.xlsx", b"extra")], {}),
    ([("duplicate.xlsx", b"a"), ("duplicate.xlsx", b"a")], None),
    ([("../secret", b"a")], None),
])
def test_corrupt_or_unsafe_archives_are_rejected(tmp_path, entries, hashes):
    files, manifest = archive(tmp_path, entries, hashes)
    with pytest.raises(ValueError):
        verify_archive(files, manifest)
    assert check_health(snapshot(tmp_path), archive=files, manifest=manifest, now=NOW)["status"] == "unhealthy"


def test_archive_symlink_is_rejected_without_extraction(tmp_path):
    files, manifest = archive(tmp_path, [], {})
    with tarfile.open(files, "w:gz") as handle:
        info = tarfile.TarInfo("link"); info.type = tarfile.SYMTYPE; info.linkname = "/etc/passwd"
        handle.addfile(info)
    with pytest.raises(ValueError):
        verify_archive(files, manifest)
    assert not (tmp_path / "link").exists()


def test_invalid_health_options_are_rejected(tmp_path):
    snap = snapshot(tmp_path)
    for age in (0, -1, float("inf"), float("nan")):
        with pytest.raises(ValueError):
            check_health(snap, max_age_hours=age)
    with pytest.raises(ValueError):
        check_health(snap, archive="unpaired.tar.gz")


@pytest.mark.parametrize("invalid_id", [True, 0, -1, "1", None, [], {}])
def test_invalid_backup_ids_fail_as_validation_errors(tmp_path, invalid_id):
    document = json.loads(snapshot(tmp_path).read_text())
    document["tables"]["users"] = [{"id": invalid_id}]
    with pytest.raises(BackupValidationError, match="IDs"):
        verify_snapshot(document)


def test_unknown_snapshot_version_is_not_treated_as_legacy():
    with pytest.raises(BackupValidationError, match="version"):
        verify_snapshot({"format_version": 99, "users": [], "customers": [], "quote_history": []})


def test_health_cli_works_offline_without_application_settings(tmp_path):
    snap = snapshot(tmp_path)
    env = dict(os.environ); env.pop("OPENAI_API_KEY", None); env["DEBUG"] = "invalid-on-purpose"
    runner = Path("scripts/check_backup_health.py").resolve()
    process = subprocess.run([sys.executable, str(runner), str(snap), "--max-age-hours", "10000"], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    report = json.loads(process.stdout)
    assert report["status"] == "healthy" and report["automatic_backups"] == "not_assessed"
