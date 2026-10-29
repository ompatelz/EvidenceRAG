# EvidenceRAG

EvidenceRAG is a planned evidence-first retrieval system for technical PDFs. Its goal is
to retrieve text, tables, figures, and equations with honest page or region provenance,
then produce answers whose material claims can be inspected against their sources.

This repository is intentionally at the **Phase 0.1 foundation** stage. It currently
provides only a Python package skeleton, project documentation, tests, dependency
locking, and continuous integration. It does **not** yet parse PDFs, retrieve evidence,
run an API, generate answers, or report benchmark results.

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

Planned for later reviewed phases:

- a minimal FastAPI application and typed evidence-provenance contract;
- evaluation schemas and repository-owned PDF fixtures;
- evidence-preserving PDF ingestion;
- BM25, dense, hybrid, and reranked retrieval baselines;
- grounded answers, citation validation, and calibrated abstention;
- a visual retrieval path only if experiments justify its compute and complexity.

## Non-goals for this phase

Phase 0.1 deliberately excludes FastAPI, PDF parsers, Docling, Qdrant, LLM SDKs,
frontends, Redis, PostgreSQL, Docker, model downloads, and deployment. It also makes no
claims about retrieval quality, answer accuracy, latency, or production readiness.

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

`uv` installs the project in editable mode and resolves exact transitive versions from
the committed lockfile. CI also verifies that `uv.lock` still matches `pyproject.toml`.

## Repository map

```text
src/evidence_rag/             Importable application package
tests/                        Executable package-contract tests
docs/PROJECT_STATUS.md        Verified state and next work
docs/architecture.md          Current boundary and planned direction
docs/decisions/               Architecture decision records
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
