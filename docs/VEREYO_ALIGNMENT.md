# Vereyo Interview Alignment

Vereyo's product story is AI-powered construction estimating: upload plans,
extract scope, price the work, validate against real contractor data, and send
professional estimates or bid packages.

This project maps to the same product pattern in a different vertical: PCB
manufacturing RFQs instead of construction blueprints.

## One-Sentence Pitch

This is a vertical AI quoting system for PCB manufacturing: messy RFQ inputs
are converted into structured specs, priced through deterministic business
rules, compared against historical quotes, and exported into professional
customer/internal documents.

## Direct Product Parallels

| Vereyo concept | PCB Quote System equivalent |
|---|---|
| Upload construction plans | Paste RFQ text or upload PCB images |
| AI blueprint extraction | AI RFQ/spec extraction |
| Trade-by-trade breakdown | PCB process and pricing-factor breakdown |
| Assembly-based pricing | Rule-based PCB quote engine |
| Real contractor rates | Historical PCB quote intelligence |
| Benchmark validation | Similar RFQ comparison and pricing review |
| Professional reports | Formal quote and internal Excel export |
| Client/project management | Customer, quote, status, and outcome tracking |
| Bid pipeline | RFQ pipeline snapshot and commercial outcomes |

## Demo Framing For Vereyo

Lead with the workflow similarity:

> I noticed Vereyo turns unstructured construction plans into structured
> estimates and bid workflows. My project solves the same class of problem in
> PCB manufacturing: turning unstructured RFQs into structured, auditable,
> repeatable quotes.

Then show the system:

1. Dashboard
   - "This is the estimator/sales team's operating view."
   - Point to Pipeline Snapshot, recent RFQs, win/loss context.

2. AI Form Assist
   - "This is analogous to plan extraction, but for RFQ text/specs."
   - Paste the sample RFQ from `INTERVIEW_DEMO.md`.

3. Quote Detail
   - "The AI structures the input, but pricing is deterministic."
   - Show pricing factors, warnings, and lead-time checks.

4. Historical Intelligence
   - "This mirrors benchmark validation: compare the current estimate against
     similar prior jobs."

5. Exports
   - "The final output is operationally usable: customer quote plus internal
     cost review."

## Strong Interview Talking Points

- I separated AI extraction from pricing logic because estimates need to be
  explainable and auditable.
- The project is vertical workflow software, not a generic chatbot.
- The core value is speed plus trust: AI reduces data-entry time, while rules,
  historical comparisons, and exports make the output usable by operators.
- I would not start by training a foundation model. The practical early-stage
  leverage is structured extraction, field-level evaluation, human review,
  pricing rules, and proprietary correction data.
- The product model is portable across domains: construction plans, PCB RFQs,
  CNC jobs, sheet-metal jobs, and other estimate-heavy workflows share the same
  pattern.

## Questions To Ask Them

- How do you evaluate extraction confidence from uploaded plans?
- Where do estimators most often need to override AI output?
- Is the harder problem plan understanding, cost calibration, or bid workflow?
- How do you version estimates when plans or assumptions change?
- What signals make an estimate trusted enough to send to a customer?

## Short Closing Line

I built this because I am interested in the same problem space Vereyo is
tackling: turning messy real-world technical inputs into structured estimates
that operators can trust, adjust, and send.
