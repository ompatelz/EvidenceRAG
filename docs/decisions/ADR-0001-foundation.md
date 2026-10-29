# ADR-0001: Python-first modular-monolith foundation

- Status: Accepted
- Date: 2026-10-29
- Decision owners: Om Patel and project maintainers

## Context

EvidenceRAG aims to become an evidence-grounded retrieval system for visually complex
technical PDFs. The master context proposes many possible components, but no application,
dataset, benchmark, or bottleneck has yet been implemented or measured. Starting with
parsers, vector databases, model SDKs, queues, and a frontend would create integration
surface before the evidence and evaluation contracts are stable.

The first milestone therefore needs a reproducible, teachable repository foundation that
can grow through small pull requests without pretending that planned features exist.

## Decision

1. Use Python 3.11+ and a `src` package layout.
2. Build a Python-first modular monolith for the local, single-user MVP.
3. Use `uv` project management and commit the universal lockfile.
4. Use Ruff, strict mypy, and pytest as the initial quality gate.
5. Keep package imports lightweight and free of runtime integrations.
6. Introduce FastAPI in the next vertical slice, after the repository foundation is
   reviewed. FastAPI is a direction, not an implemented Phase 0.1 feature.
7. Make evidence provenance the central domain boundary: future retrieval and answers
   must retain immutable document version, page, element type, and honest region precision.
8. Start future persistence with SQLite metadata and local artifacts unless concurrent or
   operational requirements prove they are insufficient.
9. Defer heavy visual models, distributed queues, cloud deployment, microservices, and
   multi-tenancy until measured requirements justify their complexity.

## Dependency and version policy

- `pyproject.toml` uses bounded compatible ranges for direct tools so intentional upgrades
  are possible without accepting arbitrary future major versions.
- `uv.lock` records exact direct and transitive versions and is committed.
- CI installs from the lockfile and checks that it is current.
- Python `>=3.11` is supported; CI tests 3.11 and 3.14 in this phase.
- Dependency upgrades must regenerate the lockfile, pass the full quality gate, and be
  reviewed in a pull request. Security fixes may justify an expedited focused PR.
- Runtime dependencies are added only when the phase implements behavior that uses them.

## Consequences

### Positive

- Clean clones get the same tool versions across supported platforms.
- The `src` layout tests the installed package rather than accidentally importing directly
  from the repository root.
- A single process keeps early debugging, local use, and evaluation reproducible.
- Deferred integrations cannot slow imports or create hidden downloads in this phase.

### Costs and limitations

- There is no working API or evidence model yet.
- A modular monolith does not provide independent scaling or fault isolation.
- SQLite and local artifacts will not suit high write concurrency, multiple application
  replicas, or tenant isolation if those requirements appear.
- Supporting Python 3.11 limits use of syntax introduced only in newer Python releases.

## Rejected alternatives

- **Microservices now:** rejected because there are no measured scaling boundaries and it
  would add deployment, tracing, networking, and failure modes before a vertical slice.
- **Qdrant/PostgreSQL/Redis now:** rejected because Phase 0.1 stores no application data and
  has no retrieval workload.
- **Heavy visual model now:** rejected because hardware feasibility and benchmark benefit
  have not been measured; a CPU-friendly baseline comes first.
- **FastAPI and parser dependencies in the foundation:** rejected for this subphase so the
  repository contract remains smaller than the next functional slice.
- **Flat repository package:** rejected because it can hide packaging mistakes by importing
  source files from the current directory rather than the installed distribution.
- **Unbounded dependency versions:** rejected because silent tool changes undermine
  reproducibility; exact-only declarations were also rejected because the lockfile already
  captures exact resolutions while compatible ranges communicate upgrade policy.

## Conditions for revisiting

Change this decision through a new ADR when evidence shows one or more of the following:

- measured CPU, memory, latency, or fault-isolation limits require a separate service;
- multiple concurrent users or replicas require PostgreSQL and explicit authorization;
- ingestion duration and restart-loss risk require a durable queue;
- object volume, remote execution, or retention requirements exceed local artifact storage;
- a controlled evaluation shows a visual model materially improves visual queries at an
  acceptable latency, memory, and maintenance cost;
- a supported dependency or security policy requires raising the Python floor;
- two genuine provider implementations reveal a stable interface worth abstracting.

## Rollback

Before merge, discard the feature branch. After merge, revert the Phase 0.1 commit or PR;
the previous repository contained only the original README and no data migration or
external runtime resource needs reversal.
