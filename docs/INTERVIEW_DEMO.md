# Interview Demo Guide

A five-minute English rehearsal for the PCB Quote System. Demonstrate an
inspectable estimating workflow, not a claim of production maturity.

## Environment and Safety

- Rehearse on [staging](https://web-staging-ee69.up.railway.app/login).
- Do not create, revise, approve, import, seed or delete
  production records during rehearsal.
- Use privately supplied credentials for an existing Manager account. Do not
  show passwords, API keys, environment variables or customer data on screen.
- Use synthetic inputs only. New rehearsal quotes stay in staging; retain their
  quote numbers in your private rehearsal notes instead of deleting records.
- Confirm English is selected. Open Quote List, a normal price-review fixture
  and a sparse fixture in separate tabs before starting.
- Fixture names are more stable than numeric IDs. Find `SYNTH-PRICE-NORMAL`,
  `SYNTH-PRICE-HIGH` and `SYNTH-PRICE-SPARSE` in Quote List.
- If fixtures are absent, prepare them only in an explicitly selected local or
  staging environment using `scripts/seed_price_review_demo.py`. This writes
  synthetic records; it is preparation, not part of a read-only demo. Do not
  rerun the general seed script against shared data without reviewing its upsert
  behavior.

The older staging parser revision `2e55836` was rehearsed on 2026-10-05.
Revision `b591af5` was subsequently deployed and its new estimate/formal gates
verified on staging the same day. See the [deployment record](STAGING_RELEASE_2026-10-05.md)
for three ready-to-inspect synthetic cases. Recheck availability before an
interview; this document is not a live deployment-health check.
The same application has since been promoted to production by explicit user
request. Keep rehearsals on staging; production was verified without saved test
quotes or generated exports. See the [production record](PRODUCTION_RELEASE_2026-10-05.md).
Staging has since advanced to the [review-fix release](STAGING_REVIEW_FIX_2026-10-05.md).
Synthetic quote #21 exercises real text parsing, quantity-basis review, separate
approval and both customer document downloads. Production does not have these
new extraction/form fixes or this synthetic quote.

## Five-Minute Script

| Time | On-screen action | Say |
|---|---|---|
| 0:00-0:30 | Open Quote List. | "I built a PCB estimating workflow that turns messy RFQs into structured specifications. AI handles extraction; a deterministic rules engine handles pricing. The important part is how the system makes uncertainty reviewable." |
| 0:30-1:20 | Open New Quote, paste Case A, click Parse with AI. | "Each extracted field carries evidence and a review state. These are evidence classifications, not calibrated model probabilities. Missing information is not silently treated as a confirmed fact." |
| 1:20-2:20 | Inspect fields, then Calculate and Save Quote without confirming everything. Open AI Extraction Review. | "An initial calculation can be saved for internal work while review is pending. Formal export and approval are blocked until required extraction confirmations are complete. The backend enforces that too." |
| 2:20-3:00 | Review the actual values, confirm verified pending fields and add a note. Show Download Estimate while business approval is pending. Choose Approved, then Generate Formal Quote after every release check passes. | "An estimate is explicitly labelled and makes no formal payment or validity commitment. Official release additionally needs complete specifications, resolved pricing and Manager approval. Approval alone cannot override missing specifications." |
| 3:00-3:45 | Switch to the prepared SYNTH-PRICE-NORMAL and SYNTH-PRICE-SPARSE tabs. Expand Price Review Evidence. | "Historical review uses earlier independent references. With enough compatible evidence, I show a transparent price band; with too little evidence, I say insufficient evidence. Similarity is not permission to pool incompatible jobs." |
| 3:45-4:30 | In another New Quote tab, parse Case B. Point to blank Gold Thickness and the review-required item. Do not save or confirm a guessed value. | "This ambiguous unit was a real failure in synthetic evaluation. Prompt changes alone were variable, so I added a text guard that leaves the thickness unknown and asks for clarification." |
| 4:30-5:00 | Return to the quote detail and close verbally. | "I added field-level evaluations, regression comparison and checksummed backup verification. The latest recorded synthetic run passed 59 fields across ten cases. Real anonymized RFQs, automated backups and stronger operational controls are still release gates." |

The formal-export endpoint on staging revision `b591af5` requires Manager/Admin permission, completed
extraction review, complete formal specifications, resolved pricing review and
Approved/Ordered business status. The previously rehearsed staging revision
only enforced permission and extraction review. Distinguish these revisions.

## Case A - Ordinary RFQ

```text
6-layer FR4 PCB, quantity 10 pcs, board size 100 x 80 mm.
Board thickness 1.6 mm, copper thickness 1 oz, lead time 7 days.
Surface finish OSP, minimum pitch 0.4 mm.
No ENIG, no VIP, no back drill, no BVH, no impedance control.
```

Expected checkpoints:

- Layer 6, quantity 10, dimensions 100 x 80 mm and thickness 1.6 mm.
- ENIG false; gold thickness unknown/blank. Copper must not become gold thickness.
- Surface Finish OSP and Pitch 0.4 mm.
- Absent optional requirements remain unknown at extraction time. The form may
  expose standard options; inspect them before saving.
- The default issue ratio needs operator confirmation; do not present it as a
  customer-specified value.
- Inspect every field you confirm. Do not check all boxes simply to unlock export.
  A rehearsal note can explain the synthetic RFQ and the independently verified
  internal issue-ratio policy. Unresolved fields stay unresolved.

No exact quote amount is promised here: pricing configuration/version and
operator edits determine the calculated result.

For an optional incomplete-estimate demonstration, omit the Surface Finish/Pitch
line. The earlier staging rehearsal displayed that input as an Estimate with
88% RFQ completeness but still allowed formal export. The new development policy
blocks formal export even after approval; only a labelled estimate is available
after review. Do not invent the missing specifications to unlock the document.

## Case B - Ambiguous Unit

```text
6 layers FR4, quantity 10, size 100 x 80 mm.
ENIG gold thickness 5u; the thickness unit is not specified.
```

Gold Thickness must remain blank and require human clarification. A value of
5 micro-inches is not established by the source. Do not claim the text guard
detects every ambiguity or reads image content.

For the optional correction demonstration, obtain a synthetic clarification
that explicitly says "5 uinch", enter that value in the form, select its
confirmation checkbox and record the clarification in the review note. This is
a human correction, not evidence that the original AI guess was correct.

## Case C - Insufficient History

Open `SYNTH-PRICE-SPARSE`. The synthetic fixture deliberately has only two
earlier compatible references, below the five-sample policy. Expect
Insufficient evidence and no asserted price-band verdict.

Do not alter reference eligibility or add fake won/cost outcomes to make the
screen look more complete. Quoted, accepted and actual-cost evidence have
separate eligibility and sample counts. Explain exclusion reasons.

If time permits, `SYNTH-PRICE-HIGH` illustrates a price-review flag. The band is
a transparent policy, not a validated market prediction, and specification
differences are not automatically priced by that historical comparison.

## Revision Demonstration - Optional

On a synthetic rehearsal quote, choose Create Revision. Change one previously
confirmed specification and supply its confirmation and a correction note.
Save the new record and show its link to the original. Check that the original
was not overwritten and changed values require fresh confirmation.

## Failure Fallbacks

| Failure | Response |
|---|---|
| AI unavailable, timeout or rate limit | Do not retry repeatedly. Keep the current form, acknowledge the failure, then show an existing synthetic reviewed quote. Manual entry is a separate path and does not prove AI review guards worked. |
| Missing fixtures | Use a prepared local/staging fixture or skip the historical-band screen. Do not seed production or invent evidence. |
| No Manager access | Show the available Staff workflow. Explain the permission boundary; do not promote an account during the demo. |
| Export fails | Keep the quote detail and review history visible. Describe the intended handoff as unverified in this rehearsal, not as a successful download. |
| Missing gold unit | Leave it unresolved or demonstrate a documented synthetic clarification. Never confirm a blank value. |

## Short Answers

**Why not train an LLM?**

"My immediate problems are domain labels, measurable extraction failures and
operator workflow. I use an existing model and improve the surrounding
validation and evaluation before considering training."

**What makes this more than an AI wrapper?**

"The system has deterministic pricing, server-side permissions, review gates,
correction history, conservative historical evidence and repeatable evaluation.
An API returning JSON alone would not give an operator those controls."

**Is it production-ready?**

"It is a staged single-company pilot. Native automatic backups are still
blocked by integration permissions; real-document evaluation is pending.
Redis is not enabled on staging, so distributed rate limiting is not verified.
There is no tenant isolation, soft-delete recovery or external tamper-proof
audit sink. I distinguish tested behavior from release requirements."

**How does this relate to another estimating domain?**

"The transferable pattern is extraction, validation, human correction,
deterministic estimation and historical feedback. The field vocabulary and cost
rules are domain-specific; I would validate those with domain experts."

## Evidence and Acceptance

- [Release acceptance checklist](RELEASE_ACCEPTANCE.md)
- [Customer-export policy](CUSTOMER_EXPORT_POLICY.md)
- [Recorded staging rehearsal](REHEARSAL_2026-10-05.md)
- [Runnable extraction evaluation](EXTRACTION_EVALUATION.md)
- [Backup and recovery runbook](BACKUP_RECOVERY.md)
- [Access-control boundaries](ACCESS_CONTROL.md)
- [Company-specific framing](VEREYO_ALIGNMENT.md)

Do not display private backup/evaluation payloads during the interview.
Automated browser acceptance uses controlled parser outputs; its passing result
is workflow evidence, not independent live-model accuracy.
