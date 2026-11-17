# EvidenceRAG

EvidenceRAG is a local, single-user prototype for finding evidence in technical
PDFs and inspecting its original page or region. It extracts text and page-local
tables, retains versioned provenance, and tests when a cited answer should be
withheld. The optional Atlas demo emits one fixed answer for an owned fixture.
The API accepts an injected answer generator for controlled experiments.

## Run the demo

From a clean clone with Python 3.12, uv 0.12.7, and Node.js:

```sh
uv sync --locked --all-extras --dev
uv run --locked python scripts/quality_gate.py
EVIDENCERAG_DEMO_ANSWERS=true uv run --locked uvicorn evidence_rag.api:create_app --factory --no-access-log
```

In PowerShell, use `$env:EVIDENCERAG_DEMO_ANSWERS = 'true'` before the Uvicorn
command. Open [the local inspector](http://127.0.0.1:8000/inspector), ingest
`datasets/fixtures/atlas-narrative.pdf`, and select the Atlas example question.
Click the citation to see the highlighted source line. The [demo guide](docs/demo.md)
includes a controlled retriever comparison and an unsupported question.
[Build, container and rollback instructions](docs/release.md) cover the local candidate.
See [live cited answers](docs/live_answers.md) to use a signed-in Codex CLI,
OpenRouter, or the OpenAI API with per-query consent.

## How the application works

1. A bounded multipart upload becomes an immutable SHA-256 document version.
   PyMuPDF extracts evidence and renders page previews. The lifecycle publishes
   a ready record after both outputs are complete.
2. Queries select one ready version. BM25 works in the base runtime. Optional
   dense, hybrid RRF, and reranked modes load pinned local models and build a
   temporary Qdrant index. Scores retain their method-specific meaning.
3. A configured generator receives a bounded evidence pack. Every material
   claim must cite a supplied evidence ID from the exact version and resolve
   to a source preview. Table rules and an optional local semantic verifier
   give additional signals to the opt-in abstention policy.
4. The inspector fetches the version-scoped anchor and page PNG. It highlights
   an available region and labels page-only citations at page precision.

See the [architecture diagram](docs/architecture.md), [answer contract](docs/answer_contract.md),
[abstention policy](docs/abstention.md), and [reliability and privacy boundaries](docs/reliability.md).

## Measured results

The current retrieval comparison uses owner-reviewed synthetic labels.
The older fixed-draft and retrieval results below are historical diagnostics. The
[evaluation protocol](docs/evaluation_protocol.md) defines split isolation,
ranking denominators, and the human-review gate.

| Observation | Scope | Evidence |
| --- | --- | --- |
| BM25 / dense / hybrid / reranked validation nDCG@5: 0.797 / 0.842 / 0.808 / 0.842 | Same 11 scored owner-reviewed validation queries and canonical evidence-unit relevance | [Run record and raw outputs](reports/reviewed-answer-benchmark/README.md) |
| False answers on unanswerable cases: 3/4 → 0/4. Coverage: 12/13 → 6/13. Correct answers: 7/13 → 6/13. | Same BM25 rankings and fixed drafts, support policy off/on | [Paired raw run](reports/runs/grounding-comparison-v1.json), [analysis](reports/ablation_study.md) |
| Ingest 173.21 ms/page and cited query 12.24 ms wall time | One owned page, one cited BM25 query, Windows i7-13700H, sequential in-process ASGI | [Operational smoke](reports/runs/local-release-smoke.json), [conditions](docs/reliability.md) |

The [baseline report](reports/baselines.md) and [error analysis](reports/error_analysis.md)
cover misses, false abstentions, and citation errors. Resume claims and their
evidence are tracked in the [claims audit](docs/claims.md).

## Scope and known limits

Use loopback with one user and one application process. The app keeps PDFs and
derived assets in local storage, performs optional model lookup from the local
cache at query time, and uses no hosted generator by default. The caller is
responsible for the documents it uploads. Access control for shared hosts,
durable distributed ingestion, OCR, multi-page table linking, and pixel-level
chart or diagram interpretation are outside this scope. A region preview shows
where evidence came from. The system can still retrieve irrelevant context or
withhold a supported answer. The application is licensed under
[GNU AGPLv3](LICENSE). Keep the [copyright and license notices](NOTICE) when
redistributing and follow the [distribution guide](docs/release.md#distribution).

The [project status](docs/PROJECT_STATUS.md) records verification and remaining
gates. The [study guide](docs/interview.md) covers the code and experiments in
reading order.

## Held-out diagnostic

On one held-out owned PDF, BM25 ranked the labeled evidence first on
two of two eligible text queries. Both flagged pixel-dependent queries
returned an unsupported-modality outcome. The run used the original provisional label snapshot and a disabled generator.
Those labels were subsequently reviewed. The opened family stays closed to
new final-test claims. See [the frozen report](reports/final_evaluation.md)
and [raw run](reports/runs/release-frozen-bm25.json).

## Reviewed answer benchmark progress

The owner reviewed all 36 benchmark questions across seven synthetic PDF
families. The four-method retrieval report scores 24 answerable nonvisual
development and validation questions. Live answers, claim metrics and
larger-population validation remain pending. A [separate held-out run](reports/reserved-final-evaluation.md)
records Codex results on two new owner-approved synthetic families.
[Source review](datasets/eval/SOURCE_REVIEW_GUIDE.md) ·
[Current baseline](reports/reviewed-answer-benchmark/baselines.md) ·
[Retrieval ablation](reports/reviewed-answer-benchmark/retrieval-ablation.md)
