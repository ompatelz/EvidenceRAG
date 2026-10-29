# Evaluation protocol

## Status

This document defines future measurements. No retrieval or answer-quality result has been
measured. The committed rows are contract fixtures, not benchmark evidence.

## Splits and leakage prevention

- Development items may be inspected while implementing behavior.
- Validation items may tune thresholds, fusion, or model choices.
- Frozen-test items are inspected only for final reporting after configuration is locked.
- A document ID and its versions stay in one split. Related document families should also
  stay together when detectable; random question-level splitting is insufficient.
- Model-generated candidate questions require human verification of answerability, answer,
  evidence, ambiguity, and difficulty.

Example leakage: paraphrasing a table question into development while keeping the original
question in frozen test exposes the same table and answer during tuning. The apparent test
gain would not measure generalization to an unseen document family.

## Label review

`verified` means a human checked the source and label. `needs_review` and `uncertain` labels
must not be treated as final ground truth. Answerable items require answers and evidence;
unanswerable items deliberately contain neither.

## Metrics to implement later

- **Hit Rate@K:** answerable queries with at least one relevant item in the top K.
- **Recall@K:** retrieved relevant items divided by all labeled relevant items per query.
- **MRR:** mean reciprocal rank of the first relevant result.
- **nDCG@K:** position-discounted gain using explicit binary or graded relevance.
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
