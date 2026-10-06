# Synthetic RFQ Live Evaluation - 2026-10-05

This is the preserved pre-fix baseline. See the [subsequent local fix validation](SYNTHETIC_RFQ_FIX_VALIDATION_2026-10-05.md)
for candidate changes, retained intermediate failures and final repeat results.

One live run of `evals/practice_rfq_20.jsonl` through the existing text parser
and extraction review, using configured `gpt-4.1-mini`. No application quotes,
customers, approvals or exports were created; no production deployment occurred.

## Recorded Evidence

- Code revision: `20f79c3c2c1b4365cb8f6f4376b7ed8f43367720`; the new dataset and
  practice documentation were still uncommitted during evaluation.
- Dataset SHA-256: `1a51a379c38afd8c70f2c665240b93e2d750004b251fa2439263952fd5ad8b1e`.
- All 20 parser requests succeeded; 17/20 cases passed every labelled field.
- Correct labelled fields: 246/249 (98.80%). Two critical-field errors.
- Wrong values assessed as high confidence: zero in this run.
- Review coverage: 221/249 labelled fields assessed; 148 high-confidence fields.
  Two of the three wrong fields had no recorded review assessment. Zero false
  high-confidence errors therefore does not mean complete error interception.
- CLI exit code: 1, correctly signalling remaining mismatches, not an API outage.
- Full report: `evals/private/practice-20-report.json`, Git-ignored, mode `0600`.
  It includes source and live-input hashes; no raw source RFQs or credentials.

## Failures

| Case | Field | Expected | Actual | Review assessment |
|---|---|---|---|---|
| practice-01 | hard_gold | false | null | Not recorded |
| practice-06 | enig_thickness_uinch | 20 | null | Not recorded |
| practice-20 | qty | null | 20 | medium |

1. Explicit negative Hard Gold must remain false, not unknown.
2. Explicit Hard Gold thickness must survive an unrelated ENIG negation. The
   prompt contains competing negation/gold rules; this is a possible cause,
   not a verified root cause or a completed fix.
3. An unresolved count in sets must not be silently treated as individual
   boards. Medium confidence still requires human clarification of the basis.

## Scope and Next Work

These are synthetic, author-labelled text cases, not independent real RFQs,
image/OCR accuracy, security certification, price validation or production
release acceptance. Only labelled core fields are graded. Passing the adversarial
footer case does not establish general prompt-injection resistance or prove
approval/export enforcement in the browser.

The dataset contains explicit clarification instructions, so results should not
be generalized to less explicit supplier documents. This is one stochastic model
run. Preserve these baseline labels; repeat like-for-like evaluation after a
targeted fix, include the original ten-case suite, and add unseen variants rather
than tuning only these exact examples. Do not claim these three errors were fixed
or that the review workflow blocked them end to end based on this report.
