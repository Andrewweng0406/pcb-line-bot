# Staging Release - 2026-10-05

## Deployment

- URL: `https://web-staging-ee69.up.railway.app/login`.
- Runtime source revision: `b591af5cbbbef3be9662fb4449df18001a71f773`.
- Exact deployment ID: `2408fdc4-52a3-4f72-94e6-1f0af581d330`, SUCCESS.
- Container image: `sha256:205fb8275264fe1d825524cd6efc46df3836f81d3ab77aae66d066bfebb272f5`.
- Health endpoint: HTTP 200 after startup. A transient 502 was observed during
  the replacement/startup window; no zero-downtime claim is made.
- Remote SHA-256 values for the web routes, release evaluator, workbook renderer
  and detail template matched the clean local revision.
- Production deployment remained `3af641f0-8944-4992-bb75-db2b9e00cadc`.
  No production deployment, database write or variable change was performed.

## Try the Three States

Use the existing privately supplied staging Manager credentials, unchanged.
These are synthetic records; do not treat them as customer orders or accuracy labels.

| Record | Link | Expected state |
|---|---|---|
| PCB-20261005-001 | [Quote 18](https://web-staging-ee69.up.railway.app/quotes/18) | Existing AI-assisted rehearsal quote, Approved but missing Surface Finish/Pitch. Estimate allowed; formal export returns 409. |
| PCB-20261005-002 | [Quote 19](https://web-staging-ee69.up.railway.app/quotes/19) | Complete manual synthetic specifications, Pending Review. Estimate allowed; formal export blocked until Manager approval. |
| PCB-20261005-003 | [Quote 20](https://web-staging-ee69.up.railway.app/quotes/20) | Complete manual synthetic specifications and Manager approval. Formal export available. |

Quotes 19/20 belong to the new synthetic customer `Synthetic Release Preview`.
Their notes explicitly identify the manual test data and approval exercise.
No existing quote was revised, relabelled, approved or deleted during this release.

Both estimate and formal workbooks downloaded and opened. Their titles matched
their document types. Desktop/mobile checks at 1440px/390px showed no page-level
horizontal overflow or JavaScript page errors.

A single live synthetic AI request returned HTTP 200: ambiguous `ENIG gold
thickness 5u` stayed blank. This parse was not saved. It is a smoke test, not a
real-document accuracy benchmark or an image-parser evaluation.

## Preservation and Backup

PostgreSQL and the existing `/app/exports` volume were retained. RFQ uploads are
under `/app/exports/data/uploads`. No storage, database or schema replacement
was performed.

| Snapshot | Users | Customers | Quotes | Files |
|---|---|---|---|---|
| Before deployment | 1 | 5 | 18 | 9 |
| After deployment, before browser writes | 1 | 5 | 18 | 9 |
| After synthetic acceptance | 1 | 6 | 20 | 11 |

The before/after-deployment database content checksum was identical:
`b996f1ebfd23ad0910745bf06149d3bf5ae07a0d8ee75701d66ebad897ccc6a7`.
All existing non-log files retained their hashes; logs only appended. An initial
strict all-file equality check correctly flagged the new startup log entries;
archive byte-prefix comparison verified that earlier log content was retained.

After acceptance, full snapshot row comparison verified every original user,
customer and quote row unchanged, and the original file inventory retained.
The only additions were one synthetic customer, two synthetic quotes, one
estimate workbook and one formal workbook, plus appended logs.

All three private database snapshots and corresponding file archives/manifests
are under `backups/staging-b591af5/`, mode 0600 and excluded from Git/Docker.
Health checks verified checksums and archive membership. The final snapshot
also restored into a new isolated local SQLite database with matching checksum:
`f483ed066219dbd84627eef91329c9d314c67d05a0b7687754054b8507692995`.
No online database was used as a restore target.

Private browser reports, downloaded workbooks and screenshots are under
`evals/private/staging-b591af5/`, also excluded from Git/Docker.

## Remaining Limits

This is a staging trial, not production approval. Automatic provider backups
remain unverified/not enabled by this deployment; private manual captures do
not establish encryption, scheduled recovery or permanent retention guarantees.
Real anonymized RFQ evaluation, domain pricing validation and the operational
gates in [Release Acceptance](RELEASE_ACCEPTANCE.md) remain outstanding.
