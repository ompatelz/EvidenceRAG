# Architecture

## Current implemented architecture

Phase 1.2 extends the verified Phase 0 boundary with safe intake and explicit parsing:

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
- BM25, embedding models, Qdrant, and rerankers;
- external or local LLM integrations;
- a frontend or evidence inspector;
- Redis, PostgreSQL, durable distributed queues, and object storage;
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
