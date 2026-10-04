# Backup and Recovery Runbook

This runbook covers the Railway pilot database and persistent export volume.
It is deliberately conservative: restore drills use a disposable database,
never the production or staging database.

## Recovery objectives

- Database recovery point objective: one day after a native daily schedule is enabled.
- Manual release snapshot: before and after every production data migration.
- Recovery time objective for this pilot: four hours.
- Exported files: copy the `/app/exports` volume off Railway after material releases.

These are operational targets, not current guarantees. Railway native schedules
are not enabled until `schedule list` returns active daily and weekly entries.

## Backup layers

1. Railway native Postgres snapshots
   - Preferred for full database recovery.
   - Configure daily and weekly schedules in Railway after the account has backup-write access.
2. PostgreSQL custom-format dump
   - Store an encrypted copy outside Railway.
   - Validate it with `pg_restore --list` immediately after creation.
3. Application snapshot
   - `scripts/backup_db.py` writes a private, atomic JSON snapshot.
   - Its manifest records per-table row counts, per-table SHA-256 values, and a whole-content SHA-256.
   - It validates quote-to-customer and quote-to-user references.
4. Persistent files
   - Archive `/app/exports` separately and store the archive outside Railway.
   - Database snapshots do not contain generated quote files or uploads.

Application snapshots include password hashes and RFQ/customer data. Keep them
out of Git, restrict them to mode `0600`, and use encrypted storage.

## Create and verify an application snapshot

```bash
DATABASE_URL=<read-only-or-production-url> python scripts/backup_db.py backups
python scripts/backup_db.py --verify backups/backup_<timestamp>.json
```

Successful verification reports `sha256-verified`, table counts, and the
content checksum. Legacy version 1 snapshots can be checked structurally but
cannot prove that they have not changed since creation.

## Disposable restore drill

Create a new empty database and keep the production URL in `DATABASE_URL`.
Put only the disposable target in `RESTORE_DATABASE_URL`:

```bash
DATABASE_URL=<source-url> \
RESTORE_DATABASE_URL=<new-empty-database-url> \
python scripts/restore_db.py backups/backup_<timestamp>.json --confirm-empty-target
```

The command refuses to run when the target URL equals the source URL or any
target table already contains data. It verifies the snapshot before writing,
restores in foreign-key order, resets PostgreSQL ID sequences, and compares a
fresh post-restore checksum with the source snapshot.

## Railway native backups

On 2026-10-04, the staging schedule read returned `[]`; attempting daily/weekly configuration returned `OAUTH_INSUFFICIENT_GRANT`. Automatic backups are therefore **not enabled by this release**. The account owner must reauthorize the Railway integration with project write access or configure the schedules in the dashboard, then verify the active schedules and a completed backup. This is a permissions blocker, not a reason to restore or replace the database. No production settings were changed during this check.

Read current status:

```bash
railway postgres pitr status --service Postgres --environment production --json
railway postgres pitr schedule list --service Postgres --environment production --json
railway postgres pitr backup list --service Postgres --environment production --json
```

When the logged-in account has backup-write access, enable the schedule and
read it back before claiming success:

```bash
railway postgres pitr schedule set --daily --weekly --service Postgres --environment production
railway postgres pitr schedule list --service Postgres --environment production --json
```

Do not use `backup restore` for a drill: it overwrites the current database.
Use a separate disposable database or Railway PITR restore to a new service.

## Quarterly drill evidence

Record the following without storing secrets:

- Snapshot creation time and content SHA-256.
- Source and restored table counts.
- Restore target name and confirmation that it was disposable.
- Start/end time and achieved recovery time.
- Application smoke-test result against the restored database.
- Any failed steps and the corrective action.

Delete the disposable restore service only after evidence is recorded. Never
delete or overwrite production as part of a drill.
