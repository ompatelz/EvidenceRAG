# EvidenceRAG evaluation data card

The evaluation pilot uses five deterministic, repository-authored technical
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
All 31 rows remain `needs_review`. The
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
