# Synthetic RFQ Fix Validation - 2026-10-05

This records the local candidate evaluation. The changes were subsequently
[deployed and verified on staging](STAGING_REVIEW_FIX_2026-10-05.md), with an
additional web-form correction and 357-test run. No production deployment,
credential change, production quote write or production export. See the
[unchanged production deployment record](PRODUCTION_RELEASE_2026-10-05.md).

## Changes

- Text instructions distinguish explicit rejection from unknown/undecided
  process selection. ENIG negation no longer instructs the model to erase a
  separately selected Hard Gold finish/thickness or another selected finish.
- Quantity extraction requests individual-board counts and abstention for
  unresolved sets. Prompt instructions are in a system message; source text is
  a separate user message. This is not proof of prompt-injection immunity.
- The review layer flags a missing Hard Gold value when mentioned in text and
  missing gold thickness when a supported explicit numeric gold unit is present.
  These are focused English text checks, not exhaustive omission detection.
- Text matching numeric `set`/`sets` quantities requires low-confidence conflict
  review with a note confirming the board count/pricing basis. This is deliberately
  conservative even when a correct board total exists. It does not parse every
  unit synonym, spelled-out number, language, panel conversion or image.

The quantity safeguard does not deterministically overwrite the model's count;
abstention is prompt-based, while matched set counts get a mandatory review item.
Images still receive their existing human-review policy. No image parser prompt
was changed, and existing saved review metadata is not retroactively regenerated.

## Results

The original answer keys were retained; the baseline and candidate were compared
with matching dataset and input hashes. All requests used `gpt-4.1-mini`.

| Final live dataset | Cases passing | Labelled fields correct | Assessed review fields |
|---|---|---|---|
| Original practice pack | 20/20 | 249/249 | 224/249 |
| Six wording variants | 6/6 | 30/30 | 27/30 |
| Existing smoke set, including two images | 10/10 | 59/59 | 44/59 |

The practice baseline was 17/20 cases and 246/249 labelled fields. The final
comparison records three improvements, zero regressions and zero new false
high-confidence errors. Final live runs have zero labelled errors/parser failures,
but review coverage remains incomplete; unlabelled values were not graded.

The first candidate passed the practice pack and original smoke set but only
5/6 variants (28/30 fields): an undecided finish was incorrectly extracted as
explicit false for ENIG and Hard Gold. Both had medium confidence. After clarifying
rejection versus undecided status, all six variants passed. These variants are now
development regression examples, not an untouched holdout set.

Final local automated suite, including desktop/mobile browser acceptance:
**356 passed**, 1,151 dependency warnings, 71.33 seconds. The earlier candidate
suite was 355 passed; the final suite adds validation of the six-case dataset.
Mocked parser tests verify the API message contract and absence of destructive
postprocessing; live comparisons, not the mocks, validate model behavior.

## Reproducibility and Limits

Evaluation HEAD was `20f79c3c2c1b4365cb8f6f4376b7ed8f43367720`, with local
uncommitted candidate changes. Final source hashes:

- `app/ai_parser.py`: `5397d6a2dd6bbb4eac110e29af2944dae501ad0d43e7142ddbe87aa2dbd2d5f7`.
- `app/extraction_review.py`: `7aba5d349bc1ef521345e3e51eaa4d38e950e20a543641e4b2ef2d8addfe7ee1`.

Private reports preserve full source/input hashes and are excluded from Git:

- Baseline: `evals/private/practice-20-report.json`.
- First candidate: `practice-20-candidate-report.json`, `review-variants-report.json`,
  `review-original-10-report.json`, all under `evals/private/`.
- Final: `practice-20-final-report.json`, `review-variants-final-report.json`,
  `review-original-10-final-report.json`, `practice-20-final-comparison.json`,
  all under `evals/private/`.

These are small synthetic author-labelled datasets, often with explicit
clarification instructions. They do not establish real RFQ accuracy, general
security, price correctness or full end-to-end interception of model errors.
Repeat evaluation and collect independently labelled unseen/real anonymized
RFQs before broader claims. Production backup/recovery and other outstanding
operational controls remain separate requirements.
