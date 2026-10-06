# Extraction Evaluation

This harness measures the existing extraction pipeline; it never saves quotes or updates the application database. The bundled ten-case dataset (eight text cases and two rendered specification images) is synthetic, not proof of real-world accuracy. Its design follows [OpenAI's evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices): task-specific human-labelled expectations and repeatable comparisons.

## Run

An additional [20-case practice pack](SYNTHETIC_RFQ_PRACTICE.md) is available at
`evals/practice_rfq_20.jsonl`, with individual English RFQ text files and an answer
key. It includes deliberately difficult abstention cases and is separate from
the original ten-case smoke dataset. Its [first live run](SYNTHETIC_RFQ_RESULTS_2026-10-05.md)
passed 17/20 cases. The [local candidate validation](SYNTHETIC_RFQ_FIX_VALIDATION_2026-10-05.md)
records fixes, intermediate failures and a 20/20 repeat plus six variants. These
candidate changes are not deployed and do not establish real RFQ accuracy.

Recorded predictions can be graded without credentials, application configuration or network calls:

```sh
python3 scripts/evaluate_extraction.py evals/private/cases.jsonl \
  --predictions evals/private/predictions.jsonl
```

Live mode sends every dataset input to the configured OpenAI account and incurs API usage. It uses the same parsers and `gpt-4.1-mini` model as the app:

```sh
DEBUG=false python3 scripts/evaluate_extraction.py evals/synthetic_rfq.jsonl \
  --live --output evals/private/synthetic-report.json
```

Exit codes: `0` all labelled fields pass; `1` at least one mismatch or extraction failure; `2` invalid dataset or command. Missing/extra/duplicate prediction IDs are rejected rather than silently reducing the denominator.

## Human Labels

Keep real RFQs, images, labels and reports inside `evals/private/`, which is excluded from Git and Docker uploads. Remove customer names, email addresses, phone numbers, drawing identifiers and proprietary details before live API evaluation. Reports omit raw inputs and API exception messages but contain labelled/extracted field values, so treat them as sensitive. Reports are written atomically with mode `0600`.

Each JSONL line is a case with independently reviewed ground truth:

```json
{"id":"rfq-001","input":{"type":"text","text":"6 layers FR4, quantity 10"},"expected":{"layer":6,"qty":10,"material":"FR4","enig":null},"critical_fields":["layer","qty","enig"]}
```

For images use `"input":{"type":"image","path":"rfq-001.png"}`; paths are relative to the dataset file. Supply only fields with human-established labels. `null` explicitly means unknown/not stated; it is not equivalent to `false`, zero or an empty string. Do not fill labels from model output. Save disagreements for human adjudication and keep a holdout set separate from prompt-tuning examples.

Recorded predictions use `{"id":"rfq-001","parsed":{"layer":6},"review":{"fields":[{"field":"layer","confidence":"high"}]}}`. Omit review if it was not recorded; incorrect unassessed fields are counted separately, not treated as safe.

## Interpretation

- Field accuracy includes parser failures in the denominator. An upstream failure cannot pass a case whose labels happen to be null.
- Critical errors are mismatches in size, quantity, layer, thickness and gold-related fields by default. Cases can specify their own labelled critical fields.
- False high confidence counts wrong values the production review layer marked `high`. Assessed/high-confidence field counts expose missing confidence coverage. Confidence is evidence classification, not calibrated model probability.
- Per-field counts and case-level differences identify regressions. Gold numeric tolerance is 0.05 micro-inches; other continuous values use 0.001 in their field's units. Counts and days require exact numeric equality. Boolean labels require actual booleans.
- The report records dataset SHA-256, Git revision, source-file and live-input hashes, run mode, model and per-case latency. Source hashes identify working-tree changes that are not yet committed. Live results vary; repeat runs before a release and report the sample size alongside accuracy.

The CLI only supports the documented core fields, not every optional manufacturing requirement. An offline recorded run evaluates supplied predictions, not the current live model. A clean synthetic run is a smoke check, not a production release approval.

## Compare Runs

```sh
python3 scripts/compare_extraction_reports.py \
  evals/private/baseline.json evals/private/candidate.json \
  --output evals/private/comparison.json
```

Reports must have matching dataset hashes, case IDs, labelled fields, ground truth, critical-field policy and run mode. Live comparisons also require matching input hashes, including image bytes. Changing models or code is allowed; changing the evaluation population is not. Older reports without input hashes cannot establish a like-for-like live comparison.

The comparison recomputes counts from field results rather than trusting summary totals. It reports regressions even when other improvements leave aggregate accuracy unchanged, and detects wrong values becoming high confidence. Output includes IDs/field names, not raw RFQs or extracted values. A candidate with unchanged failures still exits `1`; "no regression" does not mean release-ready. Invalid/incomparable reports exit `2`. Results remain private with mode `0600`.
