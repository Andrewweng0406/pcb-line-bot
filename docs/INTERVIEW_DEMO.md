# Interview Demo Guide

Use this guide for a 3-5 minute walkthrough of the PCB Quote System. The goal
is to show an end-to-end workflow, not every feature.

For a company-specific framing against Vereyo, see
[VEREYO_ALIGNMENT.md](VEREYO_ALIGNMENT.md).

For production AI trust and evaluation talking points, see
[AI_EVALUATION.md](AI_EVALUATION.md).

## Live Demo

- URL: https://web-production-803c7.up.railway.app/login
- Email: `owner@example.com`
- Password: `hunter2`

Use the seeded `DEMO-RFQ-*` records for stable dashboard/history screens, then
create one new quote live to show the interaction.

## Demo Story

This app helps a PCB sales or pricing team turn messy RFQ input into a
structured quote, track commercial outcomes, and reuse historical pricing
context. The same FastAPI backend supports the internal web dashboard and the
LINE bot, so quotes from either channel land in one database.

If interviewing with Vereyo, frame it as the same workflow pattern in a
different domain: Vereyo turns construction plans into estimates, while this
system turns PCB RFQs into structured, auditable quotes.

## Walkthrough

1. Log in
   - Open the Railway demo URL.
   - Mention session-cookie auth and invite-code registration.

2. Dashboard
   - Point out today's quote count, total quote count, average quote amount,
     and `Recent RFQs`.
   - Open `DEMO-RFQ-001` or `DEMO-RFQ-003`.

3. Quote detail
   - Show the customer quote summary, unit price, lead time, and spec summary.
   - Show internal pricing summary and applied pricing factors.
   - Open `Commercial Outcome` to show won/lost tracking.
   - Open `Structured Data and Historical Analysis` to show comparable RFQs.

4. Create a new quote
   - Go to `New Quote`.
   - Paste the sample RFQ below into AI Form Assist.
   - Click `Parse with AI`.
   - Review the AI Extraction Review panel. Explain that explicit fields are
     treated differently from inferred/defaulted/missing fields.
   - Review the generated fields, then click `Calculate and Save Quote`.

5. Exports
   - On the quote detail page, open `AI Extraction Review` to show the audit
     trail for source, confidence, and review-required fields.
   - Show `Generate Formal Quote`.
   - Show `Download Internal Excel` if asked about finance/operations handoff.

6. Architecture close
   - FastAPI + Jinja dashboard.
   - Shared quote engine for web and LINE bot.
   - PostgreSQL on Railway.
   - Persistent Railway volume for exports/uploads/logs.
   - Seed script for repeatable demo data.

## Sample RFQ To Paste

```text
12-layer Megtron 6 PCB, 110 x 75 mm, quantity 8 pcs, issue ratio 2.0.
Board thickness 2.0 mm, ENIG 10u", via-in-pad resin plugging, back drill,
0.4 mm pitch, 3.5 mil line/space, 7 mil minimum hole, double lamination,
10 internal layers, requested lead time 10 working days.
```

Expected story:

- This is a complex HDI-style RFQ.
- The parser extracts layer count, material, size, quantity, surface finish,
  process flags, and lead time.
- The pricing engine applies setup fee, area-based board charge, process fees,
  and multipliers.
- Historical intelligence helps the salesperson compare against similar work.

## Backup Sample RFQ

Use this if the AI parser is unavailable or slow:

```text
8-layer FR-4 PCB, 92 x 64 mm, 12 pcs, 1.6 mm thickness, ENIG 8u",
via-in-pad, 0.45 mm pitch, 4 mil line/space, 8 mil minimum hole,
6 internal layers, delivery in 7 working days.
```

## Talking Points

- I kept the app English-first for interviews, but the UI can switch to
  Chinese and the parsers still accept Chinese RFQ input.
- The quote engine is deterministic and testable; AI is used to structure RFQ
  input, not to invent prices.
- The AI Extraction Review layer marks fields as explicit, inferred, default,
  image-extracted, or missing, so operators know what to trust and what to
  verify.
- Railway uses PostgreSQL plus a mounted persistent volume, so database data
  and generated files survive deploys.
- Demo data is seeded by `scripts/seed_demo_data.py`, which is idempotent.
- AI is treated as an extraction layer. Production readiness comes from
  field-level evals, human review, deterministic pricing, and correction loops.

## If Something Goes Wrong

- If login fails, confirm the demo account:
  `owner@example.com` / `hunter2`
- If the AI parse button fails, manually fill the required fields from the
  backup RFQ and save the quote.
- If exports are slow, keep the story focused on the quote detail page and
  mention that exports are written to the persistent Railway volume.
