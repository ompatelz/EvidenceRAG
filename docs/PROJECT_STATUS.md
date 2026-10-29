# Project Status

Updated: 2026-10-29

Current phase: Phase 0.1 — Repository Foundation and Core CI

## Implemented and verified

- Repository connected to `ompatelz/EvidenceRAG`; default branch was `main` at `8504c3a`
  before this work.
- Python package skeleton exposes `evidence_rag.__version__` without runtime integrations.
- Development dependencies and transitive versions are declared through `pyproject.toml`
  and `uv.lock`.
- Local and CI quality gates cover Ruff linting/formatting, strict mypy, and pytest.
- Foundation architecture and decision boundaries are documented.

Verification evidence is updated in this file only after commands have actually run.

## In progress

- Owner review and merge decision for Phase 0.1.

## Pending pull requests / links

- [PR #2: Phase 0.1 — establish Python foundation and core CI](https://github.com/ompatelz/EvidenceRAG/pull/2)
  is open and intentionally unmerged.

## Last test commands and outcomes

- `uv sync --all-extras --dev` — passed; created a CPython 3.12.9 environment and
  installed 13 locked packages.
- `uv lock --check` — passed; lockfile matches project metadata.
- `uv run ruff check .` — passed.
- `uv run ruff format --check .` — passed; 2 Python files already formatted.
- `uv run mypy src tests` — passed; no issues in 2 source files.
- `uv run pytest` — passed; 2 tests passed in 0.11 seconds.
- Temporary clean-room copy: `uv sync --all-extras --dev` plus the complete Ruff, mypy,
  and pytest gate passed independently; 2 tests passed in 0.09 seconds. The verified
  temporary directory was removed afterward.

Environment: Windows, `uv 0.12.7`, CPython 3.12.9 managed by uv. GitHub Actions
passed on Linux for Python 3.11 and Python 3.14 in PR #2.

## Experiment registry / latest valid metrics

- None. No retrieval, generation, or evaluation system exists yet.

## Known technical debt / risks

- No API, evidence model, ingestion, retrieval, evaluation dataset, or runtime exists.
- Python 3.11 and 3.14 are covered by CI, but other supported minors are not individually
  exercised in Phase 0.1.
- The project has no selected license.
- Windows is the only locally verified operating system for this first branch; CI provides
  Linux coverage.

## Decisions changed since master context

- None. ADR-0001 narrows the master context to the smallest Phase 0.1 foundation and
  defers all runtime dependencies.

## Next 3 tasks

1. Review, pass CI, and merge Phase 0.1 (approximately 15–30 minutes of owner review).
2. Phase 0.2: add the FastAPI health slice and typed evidence contract (2–4 focused hours).
3. Phase 0.3: add versioned evaluation schemas and safe fixtures (2–4 focused hours).
