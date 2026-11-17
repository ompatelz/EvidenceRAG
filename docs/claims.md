# Public claims audit

| Claim | Status | Evidence and wording |
| --- | --- | --- |
| Versioned PDF intake, parsing and PNG previews | Implemented and tested | Local synchronous lifecycle. [Architecture](architecture.md), [failure paths](reliability.md). |
| BM25, dense, hybrid RRF, optional reranking | Implemented, tested, measured on owner-reviewed development and validation | Report method, split, denominator and unit alongside numeric results. [Reviewed runs](../reports/reviewed-answer-benchmark/README.md). |
| A source citation opens the exact PDF page or a reliable region | Implemented and tested | The owned Atlas fixture demonstrates a real region. A page-only anchor shows the page at page precision. [Inspector](inspector.md). |
| Citation validation, table rules and optional prose support | Implemented and tested | Identity checks and support decisions have distinct outputs. [Answer contract](answer_contract.md), [verifier](semantic_support.md). |
| Abstention reduces false answers in a controlled experiment | Measured on provisional development and validation | Same fixed drafts and rankings, 3/4 → 0/4 false answers with coverage 12/13 → 6/13. [Ablation](../reports/ablation_study.md). |
| Query and ingestion timing | Measured on one operational fixture workload | Include hardware, cache and stage boundaries. [Reliability smoke](reliability.md). |
| General answer accuracy and real-user reliability | Future evaluation | The fixed Atlas answer or scripted evaluation drafts cannot establish this. |
| OCR, chart interpretation, and visual retrieval | Planned or deferred | The current system supports image previews and explicit unsupported-modality responses. [ADR-0009](decisions/ADR-0009-visual-evidence-feasibility.md). |
| Production service, public release, tenant isolation | Planned or out of scope | Local candidate and single-user boundaries. [Release](release.md). |

## Resume wording

- Built a local FastAPI prototype that indexes technical PDF text and tables
  with immutable document versions and clickable page and region citations.
- Compared BM25, dense, hybrid and reranked retrieval on owner-reviewed
  synthetic development and validation questions. Built a paired fixed-draft
  evaluation for claim support and abstention.
- Quantified bullet template pending reviewed evidence: “Measured [retrieval or
  abstention metric] on [N human-verified held-out queries] against [baseline],
  with [coverage or cost trade-off].”

The [frozen report](../reports/final_evaluation.md) is measured on the
frozen test under provisional labels. Its two eligible text retrieval
queries and two caller-flagged visual refusals support the narrowly
worded README observation. Keep the resume metric template until the
human-reviewed benchmark gate is met.

## Current benchmark boundary

The refreshed E0–E3 comparison has 24 scored owner-reviewed questions.
These cases are split between development and validation. Live answer
denominators remain empty. The added cases establish coverage of specific
document formats in the corpus. They provide no estimate of deployment
performance.
[Current ablation](../reports/reviewed-answer-benchmark/retrieval-ablation.md)
