# Staging Rehearsal Results

Recorded on 2026-10-05. This is evidence of a bounded synthetic rehearsal,
not production-release approval or real-customer extraction accuracy.

## Target and Scope

- Environment: staging, `https://web-staging-ee69.up.railway.app`.
- Deployment ID: `1da19458-40f9-4172-8317-0fb4c70be250`.
- CLI deployment status: SUCCESS; recorded parser revision `2e55836`.
- Successful browser run began at `2026-10-05T20:07:21Z`.
- Existing Manager account; English UI; real configured AI parsing, not mocked.
- Exactly one new synthetic quote retained: `PCB-20261005-001`, ID 18.
- No seeding, deletion, revision, import, account change or deployment.
- Production was not accessed or changed during the browser rehearsal.

Railway MCP authentication failed; the authenticated local CLI successfully
read the exact staging deployment. No infrastructure mutation was attempted.

## Observed Results

| Check | Result |
|---|---|
| Ordinary RFQ, live AI | Layers 6, quantity 10, dimensions 100 x 80 mm, thickness 1.6 mm, copper 1 oz and lead time 7 days matched the synthetic input. Explicitly absent optional processes stayed false. |
| Gold/copper separation | Gold thickness remained blank for the non-ENIG ordinary input. |
| Pending review gate | Saved internal calculation; approval and formal export each returned HTTP 409 while required confirmations were pending. |
| Human confirmation | Confirmed only values checked against the synthetic RFQ, plus an explicitly noted synthetic issue-ratio assumption. Review released the formal-export action. |
| Approval persistence | Manager approval saved and remained Approved in a fresh authenticated session. |
| Formal workbook | Download opened successfully; layer, quantity, quote number and calculated total matched the saved quote. |
| Ambiguous unit, live AI | `ENIG gold thickness 5u` remained blank and produced a required clarification item. This case was not saved or guessed. |
| Normal historical fixture | `SYNTH-PRICE-NORMAL` displayed Within historical band; five eligible quoted references, median NTD 100 and band NTD 80-120. |
| Sparse historical fixture | `SYNTH-PRICE-SPARSE` displayed Insufficient evidence, not a price-band verdict. |
| Desktop/mobile | Quote detail fit 1440px and 390px widths without page-level horizontal overflow; screenshots retained privately. |
| JavaScript | No page errors observed during the successful flow. |
| Existing quote preservation | All 17 pre-existing quote-detail API responses matched before/after; final count was 18. |

The API preservation comparison covers the fields exposed by that endpoint.
It is not a full database checksum, file-inventory comparison or recovery drill.
Revision preservation and other roles were not exercised against shared staging
in this run; the local automated suite covers those separate workflows.

The local suite was rerun with `DEBUG=false RUN_BROWSER_ACCEPTANCE=1`:
**287 passed**, 1,096 dependency warnings, in 66.86 seconds. Browser acceptance
in that suite uses controlled parser outputs; it is separate from the live AI
requests above and does not increase the live-model accuracy sample count.

## Important Limitation

The ordinary RFQ still displayed **Estimate** and **88% RFQ data completeness**,
with Surface Finish and Pitch missing. Completing extraction review did not
make the specification complete, and formal export was allowed after review.
Business Approved status is also not an export prerequisite.

Before customer-facing use, specify whether estimates/incomplete specifications
may be formally exported, which domain fields are mandatory, and how those
states must be labelled in the document. Do not claim the existing review gate
enforces those additional business policies. Company branding and commercial
document defaults also need operator approval before real customer delivery.

## Private Evidence

The successful run's report, screenshots and workbook are under
`evals/private/rehearsal-20261005T200721Z/`, excluded from Git and Docker builds.
The workbook SHA-256 is
`811259d28f336e1bbac996ce5cb26ac0fcee79e597e8cc4d74d75cfb26f6d7ce`.
Screenshots include expanded review history at desktop/mobile widths.

Two preliminary ordinary-input parses returned HTTP 200 before the complete
run. Local rehearsal-harness payload-inspection errors interrupted both attempts
before any quote write; they were corrected in the private harness. The successful
run made two live parse requests: ordinary and ambiguous. No paid requests were
retried after an AI-service failure.

## Release Decision

**Rehearsal only.** Real anonymized RFQs, native automatic backups and operational
controls remain outstanding. Follow the [release checklist](RELEASE_ACCEPTANCE.md)
and [interview script](INTERVIEW_DEMO.md); do not infer permission to deploy from
this successful synthetic run.
