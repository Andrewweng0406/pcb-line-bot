# AI Evaluation and Trust Plan

This project uses AI for extraction, not for final pricing decisions. The
pricing path stays deterministic: RFQ text or images are converted into
structured fields, then the quote engine applies business rules, warnings,
historical comparisons, and exports.

## Why This Matters

In estimating workflows, the risk is not only hallucination. The bigger risks
are missing scope, misreading a technical value, or producing an output that an
operator cannot inspect. A useful AI estimating product needs a reviewable loop:

```text
messy input -> structured extraction -> validation -> human review
-> deterministic pricing -> historical benchmark -> corrected data
```

## What To Evaluate

Measure extraction quality by field, not only by "looks right".

| Area | Example fields | Metric |
|---|---|---|
| Required RFQ fields | layer, quantity, size | exact match rate |
| Technical specs | material, thickness, surface finish | normalized match rate |
| Process flags | ENIG, VIP, back drill, hard gold | precision / recall |
| Numeric tolerances | pitch, line/space, min hole | numeric error band |
| Commercial fields | lead time, customer, notes | match or missing rate |
| Completeness | required and recommended fields | missing-field rate |

For Vereyo-style construction estimating, the same pattern maps to trades,
scope items, dimensions, quantities, assemblies, exclusions, and assumptions.

## Eval Set Design

Start with a small but realistic set:

- 20 clean RFQs with obvious fields.
- 20 messy RFQs with abbreviations and missing details.
- 20 real historical RFQs after customer approval and anonymization.
- 10 image/PDF inputs if vision parsing is enabled.
- Edge cases for each pricing multiplier and process flag.

Each sample should have:

- raw input text or image reference
- expected structured JSON
- notes about ambiguity
- expected follow-up questions
- whether the quote should be marked quotable, estimate, or review-required

## Production Feedback Loop

The best data comes from operator corrections.

Track:

- original raw input
- AI extracted fields
- human-edited fields
- quote engine warnings
- final sent quote
- won/lost/no-response outcome
- actual cost and margin when known

This turns the product into a learning loop. The model or prompts can improve,
but the business also learns which fields are most often missing or corrected.

## Guardrails

- Never let AI directly set final price without deterministic validation.
- Mark incomplete or risky RFQs as `Estimate` or `Manager Review Required`.
- Keep follow-up questions when critical fields are missing.
- Store both raw input and structured output for auditability.
- Show applied pricing factors so users can inspect why a quote changed.
- Treat low-confidence extraction as a review workflow, not an error page.

## Metrics To Show Internally

- Field-level extraction accuracy.
- Required-field missing rate.
- Human correction rate by field.
- Quote creation time before vs after AI assist.
- Percentage of quotes needing manual cost review.
- Win rate and margin by quote type after human review.
- Error categories: missing scope, wrong numeric value, wrong material/process,
  ambiguous input, unsupported requirement.

## How This Project Already Supports The Loop

- AI Form Assist and image parsing produce structured form fields.
- AI Extraction Review classifies extracted fields by source and confidence:
  explicit, inferred, default, image-extracted, or missing.
- New Quote highlights low-confidence/default/missing fields before save.
- Quote Detail stores and displays the extraction audit trail for later review.
- RFQ completeness checks identify missing information.
- Pricing is deterministic through `app/quote_engine.py`.
- Pricing review labels quote risk as quotable, estimate, or review-needed.
- Quote detail exposes applied factors, warnings, and internal notes.
- Historical intelligence compares similar RFQs.
- Commercial outcome tracking records won/lost/no-response, actual cost, and
  margin.
- Demo seed data creates stable examples for review and regression thinking.

## Future Implementation Ideas

- Add confidence scores to extracted fields.
- Store every AI extraction attempt before user edits.
- Add an "AI vs final" diff view on quote detail.
- Create a pytest-backed eval fixture with golden RFQ examples.
- Add a dashboard card for human correction rate.
- Add exportable eval reports for model/prompt comparisons.

## Interview Talking Point

I would not start by training a foundation model. For this kind of product, the
practical leverage is in the workflow and data loop: structured extraction,
field-level evaluation, human review, deterministic pricing, historical
benchmarking, and feedback from real outcomes.
