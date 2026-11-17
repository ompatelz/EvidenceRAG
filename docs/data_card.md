# EvidenceRAG evaluation data card

The historical evaluation pilot used five deterministic, repository-authored technical
PDF families. The [fixture manifest](../datasets/manifests/fixtures.json)
records each source, creation date, SHA-256 and redistribution terms. The PDFs
contain synthetic technical content and are dedicated under
[CC0-1.0](../datasets/LICENSE-FIXTURES.txt).

| Split | PDF families | Candidate questions |
| --- | --- | ---: |
| Development | Atlas narrative and diagram, checksum/retry note | 13 |
| Validation | Retrieval table, cache-admission note | 13 |
| Frozen test | Queue scheduling chart | 5 |

The [candidate labels](../datasets/eval/phase2_seed.jsonl) include five
unanswerable questions and two questions that require interpreting bar heights.
Each row records its exact document version, answerability, acceptable answers,
and evidence anchors where applicable. The visual labels use page regions.
The original snapshot records all 31 rows as `needs_review`. The
[review packet](../datasets/eval/REVIEW_PACKET.md) links source pages and asks
the reviewer to check answerability, supporting evidence and region precision.

CI regenerates fixture bytes and validates hashes, split membership, and
parser-produced evidence references. The separate fixture schema cases and
the fixed-draft support, policy and semantic audits serve the scopes defined in
the [evaluation protocol](evaluation_protocol.md). The single frozen run and
its input hashes are in the [frozen report](../reports/final_evaluation.md).
Keep the chart family out of implementation, model selection and threshold tuning.

The corpus omits external documents, scans, representative production layouts
and multi-page tables. The five frozen questions belong to one chart PDF.
The reported retrieval and abstention results describe this pilot's workloads
and provisional annotations.

## Current benchmark snapshot

| Split | Families | Questions | Owner verified | Pending |
| --- | ---: | ---: | ---: | ---: |
| Development | 3 | 16 | 16 | 0 |
| Validation | 3 | 15 | 15 | 0 |
| Historical frozen test | 1 | 5 | 5 | 0 |
| Total | 7 | 36 | 36 | 0 |

The current corpus has 29 answerable questions, seven unanswerable questions,
and three visual-dependent questions. The added Harbor Library schedule
provides a grid table, a two-page renewal calculation, and an absent fee.
The Juniper Garden site map provides a spatial question and an absent
closing time. Both PDFs are original synthetic fixtures and available under
CC0-1.0. Their provenance and exact versions are recorded in the
[current manifest](../datasets/manifests/answer-benchmark.json).
The benchmark now covers more layouts and subject matter. Scans, naturally
authored documents, diverse held-out families and production workloads remain
gaps. The owner verified all five expansion labels. The [reserved test candidate](../datasets/eval/RESERVED_FINAL_TEST.md) adds
two separate CC0 families and six pending labels. Its inputs are isolated from
this reviewed snapshot. No predictions have been generated for them.
