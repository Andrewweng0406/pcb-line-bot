"""Check a local backup's integrity, age and file archive; never restore data."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import stat
import tarfile


def private_file(path):
    path = Path(path)
    info = path.lstat()
    return stat.S_ISREG(info.st_mode) and not info.st_mode & 0o077


def verify_archive(archive, manifest):
    hashes = json.loads(Path(manifest).read_text())
    if not isinstance(hashes, dict) or any(
        not isinstance(name, str) or not name or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
        or not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest)
        for name, digest in hashes.items()
    ):
        raise ValueError("Invalid file manifest")
    seen, total = set(), 0
    with tarfile.open(archive, "r:gz") as handle:
        for member in handle:
            if not member.isfile() or member.name in seen or member.name not in hashes:
                raise ValueError("Unexpected archive entry")
            total += member.size
            if total > 1024 * 1024 * 1024:
                raise ValueError("Archive exceeds verification limit")
            digest = hashlib.sha256()
            stream = handle.extractfile(member)
            if stream is None:
                raise ValueError("Unreadable archive entry")
            with stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != hashes[member.name]:
                raise ValueError("File checksum mismatch")
            seen.add(member.name)
    if seen != set(hashes):
        raise ValueError("Archive is missing files")
    return len(seen)


def check_health(snapshot, max_age_hours=24, archive=None, manifest=None, now=None):
    if not math.isfinite(max_age_hours) or max_age_hours <= 0:
        raise ValueError("Maximum backup age must be positive and finite")
    if bool(archive) != bool(manifest):
        raise ValueError("Archive and file manifest must be supplied together")
    now = now or datetime.now(timezone.utc)
    issues = []
    result = {"checked_at": now.isoformat(), "automatic_backups": "not_assessed", "issues": issues}
    paths = {"snapshot": snapshot}
    if archive:
        paths.update(archive=archive, manifest=manifest)
    for name, path in paths.items():
        try:
            if not private_file(path):
                issues.append(f"{name}_permissions_or_type")
        except OSError:
            issues.append(f"{name}_missing")
    try:
        try:
            from .backup_format import load_and_verify
        except ImportError:
            from backup_format import load_and_verify
        document, verified = load_and_verify(snapshot)
        result["snapshot"] = verified
        if verified["integrity"] != "sha256-verified":
            issues.append("snapshot_unverified_legacy")
        created = datetime.fromisoformat(document.get("created_at", ""))
        if created.tzinfo is None:
            raise ValueError("Missing timezone")
        age = (now - created).total_seconds() / 3600
        result["snapshot"]["age_hours"] = round(age, 3)
        if age < -5 / 60:
            issues.append("snapshot_future_timestamp")
        elif age > max_age_hours:
            issues.append("snapshot_stale")
    except (ValueError, OSError, TypeError, KeyError):
        issues.append("snapshot_invalid_or_missing_timestamp")
    if archive:
        try:
            result["files"] = {"status": "sha256-verified", "count": verify_archive(archive, manifest)}
        except (ValueError, OSError, tarfile.TarError, EOFError):
            issues.append("archive_invalid")
    else:
        result["files"] = {"status": "not_assessed"}
    result["status"] = "unhealthy" if issues else "healthy"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot")
    parser.add_argument("--max-age-hours", type=float, default=24)
    parser.add_argument("--archive")
    parser.add_argument("--manifest")
    args = parser.parse_args()
    try:
        report = check_health(args.snapshot, args.max_age_hours, args.archive, args.manifest)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(report, sort_keys=True))
    return int(report["status"] != "healthy")


if __name__ == "__main__":
    raise SystemExit(main())
