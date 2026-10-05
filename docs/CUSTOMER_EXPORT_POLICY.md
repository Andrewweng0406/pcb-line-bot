# Customer Export Policy

This policy is implemented on the development branch. It has not yet been
deployed to Railway; the 2026-10-05 staging rehearsal describes the older behavior.
Domain-owner validation and the other production release gates still apply.

## Three Different Documents

| Document | Permission | Release conditions |
|---|---|---|
| Internal Excel | Staff, Manager or Admin | Existing internal workflow; may contain pending/unresolved data. Not a customer-release approval. |
| Preliminary estimate | Manager or Admin | Required extraction confirmations complete; valid layer/quantity/area; successful saved calculation, finite nonnegative amounts matching the saved record, and an explicit three-letter currency label. |
| Official quotation | Manager or Admin | All estimate conditions, complete formal specifications, resolved pricing review, and business status Approved or Ordered. |

Viewer cannot generate any export. All customer-export checks run server-side
on every request and use the same readiness evaluator as quote detail.
Blocked requests return HTTP 409 with the document kind and blocker codes;
they do not generate a workbook or modify the quote.

## Formal Specifications and Pricing

Formal release requires layers, quantity, dimensions or area, material,
recognized surface finish, copper weight, board thickness, lead time and Pitch.
Numeric requirements must be positive and finite. Copper can be a single
weight or an explicit positive outer/inner pair. Area-only quotes are supported.
Recognized finishes for this initial conservative policy are ENIG, Hard Gold,
HASL and OSP; ENIG/Hard Gold also require positive explicit gold thickness.
The finish must agree with the ENIG/Hard Gold process flags used by pricing;
typing ENIG without enabling its priced process does not pass formal release.
Do not fill missing customer specifications just to pass the gate.

The saved pricing review must have status `quotable`, an empty
`critical_missing` list and an empty `unpriced_factors` list. Estimate,
Manager Review Required, missing/partial legacy reviews and unresolved
inspection-report charges do not qualify. Manager approval does not override
these conditions. No override mechanism is introduced by this change.

RFQ completeness remains an informational score, not the release decision.
Business status can remain Approved on an incomplete record; it does not mean
the record is approved for formal export. Existing status-edit behavior is
preserved, including pending-extraction guards and saving notes on legacy records.

## Estimate Labelling

`GET /quotes/{id}/export/estimate` downloads an `estimate_*.xlsx` workbook.
Its headline is `PRELIMINARY ESTIMATE - NOT AN OFFICIAL QUOTATION`.
Notes state that it is not approved for ordering/manufacturing, identify formal
release blockers and unpriced factors, and establish no payment or validity terms.
It does not inherit the official quotation's NET 30 or 30-day validity wording.

`GET /quotes/{id}/export/formal` retains the existing official workbook format
but now enforces the additional release conditions. Both documents use saved
calculated amounts, not negotiated `final_price`; no historical price is
recomputed or changed during export. The currency check is syntactic, not FX
conversion or independent validation of a business's currency configuration.

## Existing Records and Limits

There is no schema migration, data rewrite or automatic credential change.
Create Revision preserves the original and produces a fresh calculation/review.
Use it to supply verified missing specifications or regenerate missing legacy
pricing evidence. Revision status starts Pending and needs separate approval.

Previously generated files and valid signed download links are not revoked.
The existing download authorization remains unchanged. The LINE `Formal Quote`
command still directs operators to the authenticated staff dashboard, without
creating an official document or approving a record.

The release checks do not independently verify source-document truth, supplier
capability, commercial terms, company branding or universal manufacturing
completeness. Validate the mandatory-field policy with a PCB domain owner before
customer use. No tenant isolation, external audit sink or automated deployment
approval is implied.

## Verification

The local full suite passed 339 tests, including desktop/mobile browser
acceptance. The final focused export-policy run passed 50 tests. Existing
dependency warnings remain. The isolated loopback preview also verified the
incomplete-approved, complete-pending and complete-approved states at 1440px
and 390px widths. Its AI connection is disabled; no live-model accuracy or
Railway-deployment result is claimed by these checks.
