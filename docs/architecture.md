# Architecture

## Current implemented architecture

Phase 0.2 remains deliberately small:

```text
FastAPI /health + /ready
           |
    application factory ---- injectable settings

EvidenceUnit ---- document hash/version + page + honest anchor precision
     |
normalized bbox + parser/representation versions + opaque asset reference

All boundaries ---- Ruff + mypy + pytest in CI
```

The package exposes operational HTTP endpoints and validates evidence objects. There are
no database calls, document reads, model loads, retrieval operations, or external network
calls behind package import or application creation.

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

FastAPI and Pydantic now implement the local HTTP and contract boundaries. SQLite is the
planned initial metadata store, and local files are the planned artifact store; neither is
implemented yet.

## Deferred components

The following are deferred until a reviewed phase or measured need justifies them:

- Docling or another PDF parser;
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
