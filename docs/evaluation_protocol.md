# Evaluation protocol

## Status

E0 and E1 have provisional retrieval runs on development and validation. Their
candidate labels still require owner review; no validated retrieval or
answer-quality result is claimed. The older rows are schema fixtures, not
benchmark evidence.

## Splits and leakage prevention

- Development items may be inspected while implementing behavior.
- Validation items may tune thresholds, fusion, or model choices.
- Frozen-test items are inspected only for final reporting after configuration is locked.
- A document ID and its versions stay in one split. Related document families should also
  stay together when detectable; random question-level splitting is insufficient.
- Model-generated candidate questions require human verification of answerability, answer,
  evidence, ambiguity, and difficulty.
- The queue chart is the frozen-test document family. Its questions are defined but may not
  be run or inspected for model choice during E0/E1 development.

Example leakage: paraphrasing a table question into development while keeping the original
question in frozen test exposes the same table and answer during tuning. The apparent test
gain would not measure generalization to an unseen document family.

## Label review

`verified` means a human checked the source and label. `needs_review` and `uncertain` labels
must not be treated as final ground truth. Answerable items require answers and evidence;
unanswerable items deliberately contain neither.

For visual-dependent chart questions, a source-page region may exist without a parsed
`EvidenceUnit` ID. The current parser extracts captions, tick labels, and mode names but
does not encode bar heights. Such judgments must be evaluated at page/region level and
reported separately from evidence-unit retrieval metrics. A caption ID cannot stand in
for visual support. Strict seed validation reparses the committed PDFs and checks every
nonvisual evidence ID, page index, and bounding box against canonical units.

## Metrics and later answer-quality measures

- **Hit Rate@K:** answerable queries with at least one relevant item in the top K.
- **Recall@K:** retrieved relevant items divided by all labeled relevant items per query.
- **MRR:** mean reciprocal rank of the first relevant result.
- **nDCG@K:** position-discounted gain using binary evidence-unit relevance.

The four retrieval metrics above are implemented for answerable nonvisual
questions. They are macro-averaged per query and reported by split and category;
the raw rankings and denominators are saved. The measures below remain future
answer/citation evaluation work.

- **Page grounding accuracy:** citations resolving to the correct labeled page.
- **Region grounding accuracy:** citations overlapping the correct labeled region under a
  documented overlap rule; never inferred from page accuracy.
- **Answer correctness:** exact, numeric-tolerance, rubric, or human-reviewed correctness.
- **Citation precision:** cited claim-evidence links that genuinely support the claim.
- **Evidence coverage:** material answer claims with valid support.
- **Abstention coverage:** proportion answered at a threshold, reported with false answers
  on unanswerable items and false abstentions on answerable items.

Metric reports must state corpus revision, split, relevance unit, K, hardware, model and
index versions, configuration, git SHA, and uncertainty. Model judges are diagnostics, not
proof of correctness.

## Current label snapshot and optional live evaluation

Keep the historical seed and frozen run artifacts immutable. Record each
owner response verbatim in the [decision ledger](../datasets/eval/owner_decisions.json).
Record any approved field replacement and its reason in that entry.
Generate the current snapshot with
`python -m evidence_rag.eval.owner_review`. In the existing schema,
`verified` means human verified. Unconfirmed labels remain `needs_review`.
CI rebuilds the snapshot in memory, compares the committed content and validates
source hashes, parser evidence IDs, anchors, page bounds, family isolation
and exact versions. Numeric tolerances remain unset unless the owner approves
one for the question and unit.

The added library family belongs to development and the added garden family
belongs to validation. Future test data needs a family-disjoint split manifest
and dataset hash declared before any model results are inspected. Exclude the
opened historical test from settings selection. Preserve historical runs
alongside any fresh diagnostics and identify the cohort in each table.

Use the [optional live workflow](live_answers.md#reviewed-benchmark-workflow)
only for explicitly authorized source excerpts and reviewed queries. Save
the raw result before source-page judgment. The answer scorer reports correct
emitted answers over emitted answers, supporting citation-to-claim links over
all links, and claims with at least one independently supporting link over
all claims. Record compound claims as separate verifiable propositions when
possible. Review multi-source inferences jointly and report them separately
when no single citation suffices. Page and region accuracy each use the
links with an applicable gold anchor at that precision. Unsupported-answer
rate counts emitted answers with an uncovered claim. False abstention is
abstentions over answerable queries. Coverage is emitted answers over all
queries. Latency uses nearest-rank p50 and p95. A zero denominator leaves a
metric unmeasured. Small, family-clustered subsets are descriptive and carry
no population-level inference.

## Declaring a fresh final test

The original chart family is historical because its outputs have been opened.
Each of the seven current families already has a benchmark assignment. Bring
in permissioned new PDF families before declaring a replacement final test.
Record each family's source, permission, exact PDF hash and split assignment.
Have the owner check the questions, acceptable answers, answerability, visual
dependency and source-page or region anchors. Commit and hash the reviewed
labels before inference. Declare retrieval settings, model revisions, prompt,
context budget, scoring rules, exclusions and failure reporting in that same
freeze record. Keep the families out of development and validation. Run once
against the frozen record and preserve all per-query outputs. Later changes
require a fresh holdout for an untouched final-test claim.
