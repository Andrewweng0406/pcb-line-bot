# Production Pilot Update - 2026-10-05

The user requested production promotion after trying the verified staging
release. Remaining pilot limitations were disclosed before deployment. This
record documents technical deployment and preservation, not commercial readiness
or independent acceptance of every gate in [Release Acceptance](RELEASE_ACCEPTANCE.md).

## Exact Deployment

- URL: `https://web-production-803c7.up.railway.app/login`.
- Uploaded clean source revision: `59bee79a0e16e54e5f4113b7faade7978783677b`.
- Application code is identical to staging's tested `b591af5` application;
  the intervening commit changed documentation only.
- Exact deployment: `b8c9108e-d060-4816-bad5-8aecee8f6859`, SUCCESS.
- Image: `sha256:c62ead6b6e13309e09848d6532821e21e4b605a488184ba8f77e5a8156e83cae`.
- Previous deployment: `3af641f0-8944-4992-bb75-db2b9e00cadc`, application `dfbb4c2`.
- Remote web-route, release-evaluator, workbook-renderer and template hashes
  matched the verified staging/local application files.
- Staging remained at deployment `2408fdc4-52a3-4f72-94e6-1f0af581d330`.

No service/database/volume replacement, environment-variable change, seed,
import, deletion, quote creation, revision or business-status update was performed.
The existing PostgreSQL database and `/app/exports` volume were retained, with
uploads at `/app/exports/data/uploads`. Credentials were not rotated.

## Validation

- Pre-release local suite: 339 passed, 1,151 dependency warnings, 70.74 seconds.
- Production health: HTTP 200. Anonymous quote API denied with HTTP 401.
- Existing Manager login succeeded; all 11 original quote IDs/details rendered.
- Each existing quote's formal-export control and endpoint matched the new
  release policy; estimate visibility also matched the evaluator.
- Desktop/mobile checks at 1440px/390px passed without page-level overflow or
  JavaScript errors; new-quote form rendered without submitting it.
- One live synthetic text parse returned HTTP 200; ambiguous gold `5u` remained
  unknown. The parse was not saved, uploaded as an image or graded as real RFQ accuracy.
- No production workbook was generated. Positive estimate/formal downloads
  were verified on staging and local tests using the same application code.

All 11 existing production quotes currently fail formal-release requirements.
Six also have unknown currency and cannot generate a customer estimate; five
can generate labelled estimates. Approved/Ordered status alone does not override
missing specifications, unresolved pricing or legacy evidence.
Use verified revisions and inspect the configured currency rather than editing
history or inventing missing values to unlock formal export.

## Preservation and Recovery

Before and after counts: **2 users, 8 customers, 11 quotes, 18 files**.
Every original row ID and pre-existing field value was compared and retained,
including credentials, customer records, quote amounts, specifications and notes.
No staging synthetic customer or quote was copied into production.

The older production application did not expose the new role/import metadata
in its model snapshot. Startup applied the tested additive migrations:

- Existing users retain their prior approval capability through Manager roles;
  no account was granted Admin deletion rights. `role_history` is null.
- Existing quotes receive a null `import_key`; the new uniqueness index does
  not alter prior quote content.

The initial strict whole-snapshot equality check flagged those expected new
columns. Subsequent ID/field projection comparison verified every original field
unchanged and rejected additions other than the expected role/import metadata.
Consequently full snapshot checksums differ rather than falsely claiming byte
identity across schema changes:

- Before: `7c0ff91398d20d036ba3d43356ae1dcba1f943517d319873772f1559441f73ad`.
- After: `59a254dec98189e149588aa140cc06872a4e7008c63b2a9a55fa45c56d3d7981`.

All 18 file paths remained. Non-log files retained their hashes; logs only
appended, verified by comparing archived byte prefixes.
Both private snapshots and file archives/manifests passed integrity checks.
Each snapshot restored into a separate empty local SQLite database with its
own matching checksum. No online database was restored or overwritten.

Private evidence is under `backups/production-b591af5/` and
`evals/private/production-b591af5/`, excluded from Git/Docker; snapshots,
archives and restored databases have restrictive permissions.

The prior deployment ID is recorded for application rollback. Additive columns
can remain for the old model, but rollback would also restore the older, weaker
export/permission behavior. Review that trade-off and never restore a snapshot
over the live database merely to roll back application code.

## Outstanding Controls

The production provider schedule read on 2026-10-05 returned `[]`: automatic
backups are not configured. This release did not enable schedules, encryption,
offsite replication or permanent retention. Redis remains disabled; distributed
limiting, external alerts and storage-retention/quotas are not established.

Real anonymized RFQ evaluation and domain pricing/commercial validation remain
pending. Public demo credentials must be replaced before sensitive customer use;
the application remains single-company, without tenant isolation or an external
tamper-proof audit sink. Technical deployment success does not remove these limits.
