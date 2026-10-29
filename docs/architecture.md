# Architecture

## Current implemented architecture

Phase 1 connects the verified Phase 0 boundary to one reliable ingestion lifecycle:

```text
FastAPI /health + /ready
           |
    application factory ---- injectable settings

EvidenceUnit ---- document hash/version + page + honest anchor precision
     |
normalized bbox + parser/representation versions + opaque asset reference

All boundaries ---- Ruff + mypy + pytest in CI

Evaluation JSONL ---- typed validator ---- document manifest ---- hashed owned PDFs

multipart upload ---- raw body limit ---- spooled UploadFile
                                      |
                    chunked write + streamed SHA-256
                                      |
              bounded PDF markers + safe logical identity
                                      |
              confined version directory + atomic manifest
                                      |
            received metadata/status with opaque asset ID
                                      |
                  explicit bounded PyMuPDF parse
                                      |
          text + tables + reliable caption relationships
                                      |
       versioned evidence.json + parsed/partial/failed state
                                      |
             explicit bounded crop-box PNG rendering
                                      |
       atomic pages/ manifest + opaque page asset IDs
                                      |
        rotation-aware evidence-to-pixel anchor resolution
                                      |
               complete evidence + complete page set
                                      |
                      atomic `ready` manifest
```

The package exposes operational HTTP endpoints and validates evidence objects. There are
no database calls, document reads, model loads, retrieval operations, or external network
calls behind package import or application creation.

The offline evaluation boundary validates data before any retriever exists. Every item
resolves to a manifest document version and every committed fixture hash is checked against
its bytes. The evaluation plane does not call the API or claim measured performance yet.

The container boundary installs the locked runtime package in a builder stage, copies only
the resulting environment into a small Python runtime, and runs the API as an unprivileged
user. CI builds but does not publish this candidate artifact.

The intake boundary never uses the supplied filename as a path. A sanitized canonical
filename determines a local logical document ID; exact bytes determine the immutable
`sha256:<digest>` version. Artifact directories contain generated allowlisted identifiers.
The source PDF and JSON manifest are each published with same-filesystem atomic replacement,
and a manifest failure removes the unpublished version directory.

Global content idempotency is deliberate: bytes already accepted return the existing
document/version even if a later upload uses another filename. Changed bytes under the
same canonical filename create another version beneath the same logical document. This is
a local single-user policy, not tenant-aware deduplication.

`received` means bytes and the manifest are durable. An explicit version-specific operation
then records `parsing` and produces `parsed`, `partial`, or `failed`. A `parsed` artifact has
version-matching evidence and no parser issues; `partial` preserves useful evidence while
recording bounded issues. Neither state claims retrieval or answer readiness.

PyMuPDF `1.28.2` supplies text blocks, embedded-image metadata, and page-local tables. The
adapter stores stable application contracts rather than raw parser objects. Every reliable
region keeps the unrotated top-left PDF-point box, page dimensions and rotation, plus a
normalized top-left box. Evidence without a reliable box is page-precise, never guessed.
Reading order and page indexes are zero-based. Table structure stays page-local.

The rendering boundary uses the same pinned PyMuPDF version but a separately versioned
`png-rgb-no-annotations-v1` profile. It stages the complete page set beside the immutable
version, records crop/media boxes and source/pixel geometry, writes its manifest, and then
publishes the directory atomically. Client requests are scoped by generated document ID,
exact hash/version, and zero-based page index; responses contain opaque asset IDs or PNG
bytes, never private paths.

Evidence boxes are normalized in unrotated crop-box-relative source space. Rotation is
applied before scaling by actual pixmap dimensions. Region anchors return source,
display, and containing pixel boxes. Page anchors return only the preview. Unavailable
anchors return neither.

The lifecycle orchestrator owns `received -> validating -> parsing -> rendering ->
persisting -> ready`, with explicit `partial` and `failed` terminals. It validates every
transition and writes `ready` only after complete, version-consistent evidence and page
artifacts are committed. A retry or re-index removes all derived artifacts first and
rebuilds them from the immutable, hash-validated source; derived files are never appended.
The immutable received-state `intake.json` snapshot permits recovery of a missing mutable
manifest when the source is still present.

Each attempt records a server-generated request ID, count, safe failure stage/code, and
validation/parsing/rendering/persistence/total timings. Structured logs omit filenames,
source text, private paths, and raw exception messages. A process-local lock serializes
attempts for the supported single-process deployment. It is not a distributed lock and
does not make work durable across process failure; a later explicit retry restarts an
interrupted attempt from the source.

## Planned direction, not implemented

EvidenceRAG is intended to remain a Python-first modular monolith during the local,
single-user MVP. Future modules will live in one process and repository while retaining
clear boundaries for:

1. document validation, hashing, parsing, and page artifacts;
2. structured evidence with document-version and page/region provenance;
3. lexical, dense, hybrid, and optional reranked retrieval;
4. evidence-constrained answer generation;
5. deterministic citation checks and measured support/abstention;
6. offline evaluation using the same retrieval and answer functions as the API.

The central invariant is **evidence before answers**. A retrieved item must retain stable
document/version identity and honest page or region precision. Later answers may cite
only real evidence identifiers; a page link alone is not proof that a claim is supported.

FastAPI and Pydantic implement the local HTTP and contract boundaries. Local files now
implement the first artifact store. SQLite remains a planned metadata option and is not
needed for the immutable intake manifest scan at this scale.

## Deferred components

The following are deferred until a reviewed phase or measured need justifies them:

- OCR, scanned-page recovery, and semantic layout models such as Docling;
- arbitrary-DPI preview negotiation and a polished visual inspector;
- BM25, embedding models, Qdrant, and rerankers;
- external or local LLM integrations;
- a frontend or evidence inspector;
- Redis, PostgreSQL, durable distributed queues, and object storage (until measured
  latency, concurrency, or restart-durability requirements justify them);
- heavy visual-document models;
- cloud deployment, multi-tenancy, and microservices.

This avoids paying complexity, compute, and maintenance costs before there is an evidence
contract, evaluation data, or baseline worth scaling.

## Dependency direction

When modules are introduced, domain contracts should not depend on web frameworks,
database clients, or model SDKs. API and infrastructure code may depend inward on typed
domain behavior. Abstractions should appear only when there are real implementations or
test seams that require them, not in anticipation of hypothetical providers.

## Reproducibility boundary

`pyproject.toml` describes compatible direct dependencies and project policy. `uv.lock`
records the exact resolution used by clean environments. CI checks the oldest supported
Python version and the current development version, then runs the same quality commands
documented in the README.

See [ADR-0001](decisions/ADR-0001-foundation.md) for the decision, alternatives, and
conditions that would justify change.

See [ADR-0003](decisions/ADR-0003-pdf-intake-identity-and-storage.md) for intake identity,
duplicate, validation, atomicity, and storage decisions.

See [ADR-0004](decisions/ADR-0004-pymupdf-evidence-extraction.md) for the measured parser
selection, coordinate conventions, extraction boundary, licensing caveat, and rollback.

See [ADR-0005](decisions/ADR-0005-page-previews-and-anchor-transforms.md) for rendering
profile, crop/rotation transforms, atomic page publication, asset security, and rollback.

See [ADR-0006](decisions/ADR-0006-reliable-synchronous-ingestion-lifecycle.md) for the
state machine, ready commit boundary, retry/re-index policy, recovery, telemetry privacy,
and explicit conditions for moving to durable jobs.
