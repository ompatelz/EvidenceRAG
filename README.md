# EvidenceRAG

EvidenceRAG is a planned evidence-first retrieval system for technical PDFs. Its goal is
to retrieve text, tables, figures, and equations with honest page or region provenance,
then produce answers whose material claims can be inspected against their sources.

This repository has completed the **Phase 1 acceptance gate**. It includes the verified Phase 0
foundation and a bounded synchronous workflow from safe PDF intake through an atomic
`ready` state, with provenance-preserving evidence and inspectable page anchors. It does
**not** retrieve evidence, generate answers, or report benchmark results.

## Why this project exists

Many document-question-answering demos return fluent text and page-like citations
without proving that the cited source supports the claim. EvidenceRAG is designed around
the opposite order: preserve verifiable evidence first, then build retrieval and answers
on top of that contract, and measure both quality and failure modes.

## Current scope

Implemented in Phase 0.1:

- an installable `evidence_rag` Python package with a public version;
- a reproducible `uv.lock` development environment;
- Ruff formatting/linting, strict mypy checks, and pytest tests;
- GitHub Actions CI for Python 3.11 and 3.14;
- architecture, status, and foundation-decision documentation.

Implemented in Phase 0.2:

- a FastAPI application factory with `/health` and `/ready`;
- injectable, validated local application settings;
- a frozen Pydantic `EvidenceUnit` contract with document-version provenance;
- zero-based pages and validated normalized top-left bounding boxes;
- honest region, page, and unavailable anchor precision;
- opaque client-safe asset references and contract tests.

Implemented in Phase 0.3:

- versioned JSONL evaluation-item and document-manifest contracts;
- validation for answerability, provenance, document versions, anchors, and split leakage;
- two deterministic, repository-owned CC0 PDF fixtures;
- four human-verifiable contract rows, explicitly not benchmark results;
- documented metric definitions, data card, and frozen-test policy.

Implemented in Phase 0.4:

- a minimal multi-stage container with a non-root runtime user;
- a working HTTP health check and read-only Compose service;
- CI validation for deterministic fixtures, evaluation data, Compose, and image builds;
- commit-SHA traceability without image publication or deployment.

Implemented in Phase 1.1:

- bounded multipart PDF upload with both raw-request and exact streamed file limits;
- filename sanitization, path-independent generated IDs, and confined local storage;
- streamed SHA-256, logical-document IDs, and immutable content-version labels;
- idempotent duplicate handling and changed-content versioning;
- atomic source/manifest publication with partial-artifact cleanup;
- client-safe metadata/status responses whose initial state is honestly `received`.

Implemented in Phase 1.2:

- pinned PyMuPDF extraction behind a narrow parser boundary;
- deterministic page text, conservative headings, captions, captioned embedded figures,
  and page-local structured tables;
- zero-based pages and reading order with parser-native and normalized source regions;
- versioned persisted evidence artifacts and explicit parser/representation metadata;
- truthful `parsing`, `parsed`, `partial`, and `failed` lifecycle states;
- configurable page/evidence limits and source-safe parser diagnostics.

Implemented in Phase 1.3:

- bounded RGB PNG rendering of the visible crop box at a fixed versioned profile;
- atomic publication of complete version-scoped page sets and their manifest;
- opaque page asset IDs, PNG hashes, safe immutable-cache headers, and scoped preview access;
- preserved media box, crop box, source dimensions, rotation, DPI, and pixel dimensions;
- rotation-aware source-normalized to display-normalized and pixel transforms;
- page and unavailable precision that never invent region boxes;
- pixel-based and manually inspected overlay verification on the owned table fixture.

Implemented in Phase 1.4:

- an explicit validated lifecycle from `received` through `validating`, `parsing`,
  `rendering`, and `persisting` to the terminal `ready`, `partial`, or `failed` states;
- synchronous upload-and-ingest, status, retry, and re-index APIs with server-generated
  request IDs, stage timings, attempt counts, and content-safe structured logs;
- atomic readiness only after version-matching evidence and complete page assets exist;
- recovery from an immutable intake snapshot, source-integrity checks, and automatic
  rebuild when a ready artifact is missing or inconsistent;
- full replacement of derived artifacts on retry/re-index, preventing stale pages or
  duplicate evidence from surviving a successful attempt;
- a bounded owned-fixture end-to-end CI job and failure-injection lifecycle tests.

Planned for later reviewed phases:

- BM25, dense, hybrid, and reranked retrieval baselines;
- grounded answers, citation validation, and calibrated abstention;
- a visual retrieval path only if experiments justify its compute and complexity.

## Non-goals for this phase

Phase 1 deliberately excludes OCR, scanned-page recovery, equation semantics, vector
diagram understanding, multi-page table linking, a polished viewer, Qdrant, LLM SDKs,
Redis, PostgreSQL, distributed jobs, model downloads, and deployment. It makes no claims
about retrieval quality, answer accuracy, broad document understanding, latency, or
production readiness.

## Requirements

- Python 3.11 or newer
- [`uv`](https://docs.astral.sh/uv/) 0.12.7 or compatible

The supported Python policy is `>=3.11`. CI tests the oldest supported minor (3.11) and
the newest minor targeted by this foundation (3.14). Support for an older minor may be
dropped only through a documented decision and a deliberate project change.

## Development setup

From a clean clone:

```bash
uv sync --all-extras --dev
```

Run the complete local quality gate:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest
```

Verify the package and version manually:

```bash
uv run python -c "import evidence_rag; print(evidence_rag.__version__)"
```

Start the current API slice:

```bash
uv run uvicorn evidence_rag.api:create_app --factory
```

Then request `http://127.0.0.1:8000/health` or `/ready`. Readiness currently means only
that required local configuration is valid; it does not imply a database, index, completed
document parse, or model is available.

Upload an owned PDF fixture:

```bash
curl -F "file=@datasets/fixtures/atlas-narrative.pdf;type=application/pdf" \
  http://127.0.0.1:8000/api/v1/ingestions
```

This one-shot endpoint synchronously returns `ready`, `partial`, or `failed`. The response
contains opaque document/version/asset identifiers and never a filesystem path. The older
`POST /api/v1/documents` intake-only endpoint remains available and returns `received`.
Use the identifiers with:

```text
GET /api/v1/documents/{document_id}/versions/{document_sha256}
GET /api/v1/documents/{document_id}/versions/{document_sha256}/status
GET /api/v1/documents/{document_id}/versions/{document_sha256}/ingestion
POST /api/v1/documents/{document_id}/versions/{document_sha256}/ingest
POST /api/v1/documents/{document_id}/versions/{document_sha256}/retry
POST /api/v1/documents/{document_id}/versions/{document_sha256}/reindex
POST /api/v1/documents/{document_id}/versions/{document_sha256}/parse
GET /api/v1/documents/{document_id}/versions/{document_sha256}/evidence
POST /api/v1/documents/{document_id}/versions/{document_sha256}/render
GET /api/v1/documents/{document_id}/versions/{document_sha256}/pages
GET /api/v1/documents/{document_id}/versions/{document_sha256}/pages/{page_index}/preview
GET /api/v1/documents/{document_id}/versions/{document_sha256}/evidence/{evidence_id}/anchor
```

Non-secret intake settings use the `EVIDENCERAG_` prefix:

- `EVIDENCERAG_ARTIFACT_ROOT` (default `artifacts`)
- `EVIDENCERAG_MAX_UPLOAD_BYTES` (default 10 MiB)
- `EVIDENCERAG_UPLOAD_CHUNK_BYTES` (default 64 KiB)
- `EVIDENCERAG_MAX_PDF_PAGES` (default 200)
- `EVIDENCERAG_MAX_EVIDENCE_UNITS` (default 10,000)
- `EVIDENCERAG_RENDER_DPI` (default 144)
- `EVIDENCERAG_MAX_RENDER_PIXELS_PER_PAGE` (default 20,000,000)
- `EVIDENCERAG_MAX_RENDER_PIXELS_TOTAL` (default 100,000,000)

The default deployment remains a local, single-process, single-user MVP. The upload limit
is enforced once over the raw multipart request and again over streamed PDF bytes. Intake
checks the PDF header and a bounded EOF trailer; orchestration then revalidates the source,
structurally parses it, renders all bounded previews, commits complete derived artifacts,
and only then marks the version ready. An in-process lock serializes attempts and is not a
distributed concurrency guarantee. See ADR-0006 for the measured conditions that would
justify a durable job system.

Validate all committed evaluation data and deterministic fixtures:

```bash
uv run python scripts/generate_fixtures.py --check
uv run python -m evidence_rag.eval.validate \
  --manifest datasets/manifests/fixtures.json \
  datasets/eval/fixture_items.jsonl
```

Build and run the hardened local container:

```bash
docker compose config
docker build --build-arg VCS_REF=local -t evidencerag:local .
docker run --rm -p 8000:8000 evidencerag:local
```

The runtime image is non-root and intentionally excludes datasets, PDFs, tests, source
control metadata, secrets, indexes, and model weights. CI builds a candidate image but does
not publish or deploy it. PyMuPDF licensing and the repository's own license must be resolved
before any build is distributed.

`uv` installs the project in editable mode and resolves exact transitive versions from
the committed lockfile. CI also verifies that `uv.lock` still matches `pyproject.toml`.

## Repository map

```text
src/evidence_rag/             Importable application package
tests/                        Executable package-contract tests
docs/PROJECT_STATUS.md        Verified state and next work
docs/architecture.md          Current boundary and planned direction
docs/decisions/               Architecture decision records
src/evidence_rag/documents/   Intake, parsing, rendering, manifests, and local artifacts
.github/workflows/ci.yml      Reproducible automated quality gate
```

Read [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) before continuing development.
Planned architecture is not implemented architecture; the status file is authoritative
about what has actually been verified.

## Security and data hygiene

Do not commit secrets, local environments, generated indexes, model weights, private
documents, or generated artifacts. `.env.example` is documentation only and contains no
credentials. Future legal test PDFs must be explicitly repository-owned or redistributable
fixtures rather than arbitrary public documents.

## License

No project license has been selected yet. Until one is added, the default copyright
rules apply; do not assume permission to redistribute the code or future datasets.
