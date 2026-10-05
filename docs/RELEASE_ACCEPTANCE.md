# Release Acceptance Checklist

Prepared 2026-10-05. This is a procedure and evidence template, not a claim that
the checks below have been performed today. Production remains frozen.
The development branch now implements the [customer-export policy](CUSTOMER_EXPORT_POLICY.md).
The older staging deployment has not been updated; verify the exact revision
before testing the new conditions.

## Evidence Rules

Record the UTC verification time, environment, exact deployed revision/ID,
operator and sanitized evidence path for every run. Use Pass, Fail, Blocked or
Not Tested. A previous passing result is historical evidence, not a current pass.
Keep logs, screenshots, backups, RFQs and reports containing customer data out
of Git. Do not paste keys, passwords, database URLs or cookies into this file.

Use synthetic staging records for write tests. Use disposable databases for
restore drills. No production changes, merge, cleanup or credential rotation
are authorized by this checklist alone.

## Rehearsal Checks

| ID | Check | Expected result | Evidence |
|---|---|---|---|
| D1 | Log in with an existing Manager; select English. | Dashboard and quote pages render; appropriate actions are available. | Timestamp, environment and private screenshot. |
| D2 | Parse Interview Demo Case A. | Core dimensions/quantity/layers match; copper does not populate gold; missing optional data is distinguishable. | Human labels and saved evaluation result. |
| D3 | Save an AI-assisted quote with confirmations pending. | Internal calculation can be retained; approval and formal export are blocked by extraction review. | Quote number and rejected endpoint result. |
| D4 | Inspect and confirm known pending values; add a correction note when needed. | Reviewer/time/original/final values appear; unresolved values cannot simply be confirmed. | Sanitized review-history screenshot. |
| D5 | After completing required review, set business status to Approved as Manager. | Approval persists as a separate business status; changing status does not replace field confirmations. | Reloaded detail and API response. |
| D6 | Try an approved incomplete quote, then a complete reviewed/approved quote. | Incomplete formal export returns 409; its estimate is clearly labelled. Complete resolved pricing permits formal download with matching quote number, currency and calculated amounts. | Private workbook checksums, titles and value comparison. |
| D7 | Parse Case B with ambiguous gold unit. | Gold thickness remains blank and needs human clarification; do not substitute a guessed unit. | Form/review screenshot and labelled result. |
| D8 | Inspect SYNTH-PRICE-SPARSE and NORMAL. | Sparse evidence gives no verdict; normal evidence exposes eligible earlier references and formula. | Screenshots including sample counts/exclusion reasons. |
| D9 | Create a revision of a synthetic quote. | New quote links to unchanged original; changed confirmations are invalidated. | Before/after quote IDs and original-content comparison. |
| D10 | Rehearse at desktop and mobile widths. | Text and controls do not overlap; horizontal scrolling is confined to wide tables. | 1440px and 390px screenshots. |

On the new development revision, formal export requires role, completed review,
complete specifications, resolved pricing and Approved/Ordered business status.
An estimate does not require business approval but retains review/calculation
guards. These additional conditions are not active on the older staging deployment.
Manually created quotes without extraction metadata use a different workflow;
do not use them to claim the AI review guard has been tested.

## Backend and Security Checks

| ID | Check | Expected result |
|---|---|---|
| S1 | Replay Viewer/Staff/Manager/Admin action tests. | Server-side denials match the documented role matrix, not merely hidden UI controls. |
| S2 | PATCH calculated total; try approval with pending review. | Calculated total is immutable; pending approval/export stays blocked even for privileged users. |
| S3 | Demote a synthetic account in an isolated test. | Existing session loses old permissions on the next request; role-change audit records the reason. |
| S4 | Check HTTPS session and cross-site writes. | HttpOnly/SameSite/Secure cookie; configured same-origin accepted, unrelated origin rejected. |
| S5 | Test invalid/oversize image and workbook input. | Bounded, explicit rejection; no partial quote/import write. PDF remains unsupported. |
| S6 | Repeat an exact workbook import in isolation. | Duplicate rows skipped; changed mappings do not silently overwrite existing imports. |
| S7 | Trigger AI failure on a manually edited form in isolation. | Error is visible, current values remain, and busy state clears. |
| S8 | Inspect source-image/download access. | Anonymous originals denied; legitimate image access works; filename-bound signed export tokens expire. |

Never run deletion or role-change experiments on shared production accounts.
Permission tests do not establish tenant isolation or confidential-cost filtering.

## Evaluation and Recovery Commands

Run the existing automated suite locally with isolated test databases:

```sh
DEBUG=false RUN_BROWSER_ACCEPTANCE=1 python3 -m pytest -q --disable-warnings
```

Live evaluation explicitly sends the synthetic inputs to the configured AI
account and incurs usage. Real inputs require anonymization and approved handling:

```sh
DEBUG=false python3 scripts/evaluate_extraction.py evals/synthetic_rfq.jsonl \
  --live --output evals/private/candidate.json
python3 scripts/compare_extraction_reports.py \
  evals/private/baseline.json evals/private/candidate.json
python3 scripts/check_backup_health.py backups/snapshot.json \
  --archive backups/files.tar.gz --manifest backups/files.json
```

Comparison requires matching datasets, ground truth, input hashes and run mode.
Passing a synthetic run does not establish real RFQ accuracy. A healthy supplied
backup does not establish current database completeness, an enabled scheduler,
encryption or a successful restore. Follow [Backup Recovery](BACKUP_RECOVERY.md)
for a disposable restore drill; never restore over staging/production for testing.

## Production Release Gates

These are human sign-off requirements, not an implemented automatic release gate.
Every required gate must pass or have an explicitly documented owner-approved
scope limitation before a separately authorized production deployment.

| Gate | Required evidence | Last recorded state, 2026-10-04 |
|---|---|---|
| Exact deployment and rollback | Verified target revision, SUCCESS for its exact deployment ID, preserved prior artifact; assess additive-schema compatibility before rollback. | Staging parser revision 2e55836 verified; no production release authorized. |
| Real RFQ quality | Independently labelled anonymized documents, field-level failures and critical-error review; business owner defines acceptable risk. | Pending; only ten synthetic cases/59 fields were evaluated. |
| Recovery | Verified recent DB snapshot and file archive, active daily/weekly provider schedule, completed native backup and disposable restore evidence. | Manual snapshots/restores verified; automatic schedule blocked by OAuth grant. |
| Access and secrets | Review legacy Manager membership; replace public demo credentials before real data; confirm secret handling and intended single-company access. | Real-data access review pending; no tenant isolation. |
| Operational limits | Specify replica count, verify intended limiter mode/proxy handling, storage quotas/retention and error alert routing. | Redis disabled; distributed limiting, retention/quota policy and alerts not verified. |
| Domain decisions | Validate pricing rules/version/currency and required-field policy with a domain owner; verify the new approval/completeness/unpriced-factor export gates on the target revision. | New export policy implemented on development branch after rehearsal; no deployment or domain-owner sign-off yet. |

Do not enable infrastructure, create services or restore data merely to make a
checklist entry green. Resolve permission/cost/scope decisions separately.

## Run Record

Copy this template into a private evidence folder for each rehearsal or release:

```text
Run ID:
UTC verification time:
Environment and exact deployment/revision:
Operator and role:
Dataset/input hashes (if applicable):
Check IDs and Pass/Fail/Blocked/Not Tested results:
Private evidence paths:
Observed failures and unresolved fields:
Database/file preservation comparison:
Required gate owner/sign-off:
Decision: rehearsal only / release rejected / separately authorized release
```

Stop on unexpected data changes, missing originals, false high confidence,
unexplained permission escalation or failed recovery checks. Preserve evidence;
do not delete records or overwrite results to conceal a failure.
