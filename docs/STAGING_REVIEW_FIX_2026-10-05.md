# Staging Review Fix Release - 2026-10-05

Date uses the client's America/Los_Angeles calendar. Railway records the final
deployment's UTC creation timestamp as `2026-10-06T01:19:02.617Z`.

## Deployment

- Staging: `https://web-staging-ee69.up.railway.app/login`.
- Uploaded application revision: `796c671bd3943527780e9e3f1e7dc9a3fe91bbeb`.
- Exact deployment: `9fc798c6-45f3-4e3e-bda9-b65b7b7cb495`, verified SUCCESS.
- Image: `sha256:bcc2cba13d1c5a754944d482531ffb113c1944a270f27aedea3d6b0d746a5130`.
- Health endpoint returned HTTP 200; remote parser, review and web-route hashes
  matched local files. Existing PostgreSQL and `/app/exports` volume retained.
- The initial `268d74c` deployment `2e55498a-ad89-4dc9-bb6e-ee62350db5b8` succeeded,
  then was superseded before synthetic write acceptance by the web-form fix.
- Production remains deployment `b8c9108e-d060-4816-bad5-8aecee8f6859`.
  No production mutation, deployment, migration or environment-variable change.

## What Changed

The [local evaluation record](SYNTHETIC_RFQ_FIX_VALIDATION_2026-10-05.md) documents
gold/negation rules, unresolved quantity abstention and review reminders. Parser
revision `268d74c` includes the 20-case practice pack, six wording variants,
baseline failures and final passing live runs. Those were local synthetic API
evaluations, not twenty newly saved staging/production quotes.

An additional web integration issue was found during release preparation:
Hard Gold normalization forced `enig=true` even when extraction said No ENIG.
Revision `796c671` removes that overwrite without guessing a false value when
ENIG is unspecified. A regression verifies explicit No ENIG remains unchecked,
Hard Gold remains checked and gold thickness survives. Hard Gold pricing already
uses an exclusive branch, so this issue did not imply duplicate ENIG fees.

Final local full suite, including desktop/mobile browser acceptance:
**357 passed**, 1,156 dependency warnings, 72.94 seconds.
Parser/review source hashes match those from the final 36-case synthetic live
evaluation; the later change was the web-form normalization and its tests.

## Live Browser Acceptance

One existing Manager login, three live synthetic text parses, one new quote and
two workbook downloads. The private report records **55 passing checks**:

- Hard Gold true, ENIG false and explicit gold 20 uinch preserved through the
  actual AI-assisted form; confirmed total is 10 individual boards in 2 sets.
- Quantity basis receives low-confidence conflict review. Approval, estimate
  and formal endpoints return 409 while extraction review remains incomplete.
- Confirming the quantity conflict without a review note returns 400.
- Human confirmation with a synthetic source-verification note unlocks an
  estimate, but formal export remains blocked until separate Manager approval.
- Estimate/formal workbooks have distinct titles, correct quantity and the
  saved total. This is workflow verification, not independent price validation.
- Database review events retain the authenticated actor and quantity-basis note;
  the review-history note renders in the detail page.
- An unresolved `32 sets` case leaves quantity blank with missing review; a
  separate No Hard Gold case preserves explicit false and HASL finish.
  Neither of those two parse-only cases was saved.
- Desktop 1440px/mobile 390px layouts have no page-level overflow or JavaScript
  errors; screenshots were inspected.

Saved rehearsal case: quote **#21**, `PCB-20261006-001`, linked to the existing
`Synthetic Release Preview` customer. Its quote number uses the application's
runtime date; it is not a client-local date claim. Only this synthetic record was
reviewed/approved; its notes explicitly disclaim customer approval/reference use.

## Preservation

Before and immediately after deployment: **1 user, 6 customers, 20 quotes,
15 files**. Database content checksum unchanged:
`f483ed066219dbd84627eef91329c9d314c67d05a0b7687754054b8507692995`.
Existing non-log file hashes and all paths retained.

After acceptance: **1 user, 6 customers, 21 quotes, 17 files**. Full-row
comparisons retained every existing user, customer and quote; only #21 and its
two workbook files were added. Prior non-log hashes and file paths retained.
Logs are excluded from hash-equality claims because runtime writes can update them.
The post-acceptance checksum changes for the deliberately added/approved quote.

Snapshots, archives and manifests passed the existing integrity checker. Private
evidence is in `backups/staging-review-fix-20261005/` and
`evals/private/staging-review-fix-20261005/`, excluded from Git/Docker with
restrictive permissions. No online restore or new restore drill was performed
for this staging update. It does not enable native scheduled backups.

## Limits

Synthetic passing results do not establish real RFQ accuracy, pricing correctness
or general prompt-injection protection. Text set reminders cover supported
numeric English wording, not exhaustive cross-document/image unit ambiguity.
Stored legacy reviews are not automatically regenerated. Rehearse here before
requesting production promotion; production's outstanding backup, credential,
privacy and operational controls remain applicable.
