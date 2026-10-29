# Project Status

Updated: 2026-10-29

Current phase: Phase 0 complete; awaiting owner review and merge

## Implemented and verified

- Repository connected to `ompatelz/EvidenceRAG`; default branch was `main` at `8504c3a`
  before this work.
- Python package skeleton exposes `evidence_rag.__version__` without runtime integrations.
- Development dependencies and transitive versions are declared through `pyproject.toml`
  and `uv.lock`.
- Local and CI quality gates cover Ruff linting/formatting, strict mypy, and pytest.
- Foundation architecture and decision boundaries are documented.
- FastAPI application factory exposes verified `/health` and `/ready` semantics.
- Typed evidence models enforce immutable document provenance, zero-based page indexes,
  normalized region bounds, honest anchor precision, stable serialization, and opaque
  asset references.
- Versioned evaluation and manifest contracts reject inconsistent answerability, anchors,
  provenance, hashes, unknown versions, duplicates, malformed JSONL, and split conflicts.
- Two repository-owned CC0 PDFs regenerate byte-for-byte; both pages were rendered and
  visually inspected, and extracted text matches the intended narrative, diagram, and table.
- Multi-stage container installs only runtime dependencies, runs as UID 10001, and exposes
  a verified HTTP health check. Compose adds a read-only filesystem and no-new-privileges.
- CI now validates Python quality, deterministic fixtures, evaluation data, Compose, the
  container build, container health, and the runtime UID without publishing or deploying.

Verification evidence is updated in this file only after commands have actually run.

## In progress

- Owner review and merge decision for the complete Phase 0 pull request.

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
- `uv run pytest` — passed after Phase 0.2; 18 tests passed in 0.46 seconds.
- `uv run uvicorn evidence_rag.api:create_app --factory --port 8765` — started
  successfully; live `/health` and `/ready` requests both returned HTTP 200 with the
  documented JSON, then the server shut down cleanly.
- `uv run python scripts/generate_fixtures.py --check` — passed; both committed PDFs are
  byte-for-byte deterministic.
- Evaluation CLI — passed for the committed manifest and JSONL file.
- `uv run pytest` — passed after Phase 0.3; 30 tests passed in 0.57 seconds.
- Complete Phase 0 Python gate — passed; 30 tests passed in 0.70 seconds.
- `docker compose config --quiet` — passed.
- Candidate image build — passed using pinned Python and uv base-image digests.
- Candidate container — reached `healthy`; `/health` and `/ready` returned HTTP 200,
  runtime UID was 10001, and datasets, tests, Git history, and `.env` were absent.
- Clean-room Git archive of commit `972c8042380f11cb890a10dba4ba6af2609520ec` — fresh
  install, complete Python gate, deterministic fixtures, data validation, Compose, pinned
  image build, container health, and UID 10001 all passed; 30 tests passed in 1.69 seconds.
- GitHub Actions — Python 3.11, Python 3.14, and Container jobs passed on the complete
  Phase 0 implementation.
- Temporary clean-room copy: `uv sync --all-extras --dev` plus the complete Ruff, mypy,
  and pytest gate passed independently; 2 tests passed in 0.09 seconds. The verified
  temporary directory was removed afterward.

Environment: Windows, `uv 0.12.7`, CPython 3.12.9 managed by uv. GitHub Actions
passed on Linux for Python 3.11 and Python 3.14 in PR #2.

## Experiment registry / latest valid metrics

- None. No retrieval, generation, or evaluation system exists yet.

## Known technical debt / risks

- No ingestion, retrieval, database, or answer-generation runtime exists. The evaluation
  rows are schema fixtures, not a representative benchmark.
- Python 3.11 and 3.14 are covered by CI, but other supported minors are not individually
  exercised in Phase 0.1.
- The project has no selected license.
- Windows is the only locally verified operating system for this first branch; CI provides
  Linux coverage.

## Decisions changed since master context

- None. ADR-0001 narrows the master context to the smallest Phase 0.1 foundation and
  defers all runtime dependencies.

## Next 3 tasks

1. Review the complete Phase 0 PR and its architecture/evaluation decisions.
2. Merge only with owner approval after the final docs-only CI run remains green.
3. Synchronize `main`, then begin Phase 1 evidence-preserving PDF ingestion.
