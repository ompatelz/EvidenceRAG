# Project Status

Updated: 2026-10-29

Current phase: Phase 1.1 complete; awaiting owner review on the Phase 1 draft PR

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
- Phase 0 PR #2 was merged into `main` at `c2aec908f2d24397a7ba014e19fbe486eafb60df`;
  all three final Phase 0 CI jobs passed and local `main` was fast-forwarded to that commit.
- Phase 1.1 implements bounded multipart PDF intake, streamed SHA-256, logical document and
  immutable content-version identity, safe local artifact allocation, atomic manifests,
  idempotent duplicates, changed versions, cleanup, and safe metadata/status responses.
- The focused Phase 1.1 suite covers owned-fixture upload, empty/corrupt/wrong-signature
  files, unusual/traversal filenames, limits, duplicates, changed versions, interrupted and
  failed writes, manifest validation/atomicity, confinement, and path-safe responses.

Verification evidence is updated in this file only after commands have actually run.

## In progress

- Owner review of the Subphase 1.1 implementation and teaching handoff.
- Phase 1.2 is intentionally not started until the owner says `continue Phase 1`.

## Pending pull requests / links

- [Issue #3: Phase 1 — evidence-preserving PDF ingestion](https://github.com/ompatelz/EvidenceRAG/issues/3)
  tracks all four subphases.
- [Draft PR #4: Phase 1 — evidence-preserving PDF ingestion](https://github.com/ompatelz/EvidenceRAG/pull/4)
  contains commit `0e2eb11`; Python 3.11, Python 3.14, and Container CI passed.

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
- Phase 1 baseline after synchronizing merged `main`: complete quality gate passed; 30
  tests passed in 0.57 seconds.
- Phase 1.1 focused tests: 14 passed in 0.86 seconds.
- Focused Ruff check passed. Strict mypy initially found one incompatible test-stream
  override; the annotation was corrected before the full gate.
- Complete Phase 1.1 Python gate — `uv sync`, Ruff lint/format, strict mypy, and pytest
  passed on the exact pre-commit tree; 44 tests passed in 0.85 seconds. A separate
  `uv lock --check` passed after dependency resolution.
- Deterministic fixture regeneration and committed evaluation-data validation passed.
- `docker compose config --quiet` passed with a named artifact volume preserving the
  read-only root filesystem boundary.
- `docker build --build-arg VCS_REF=phase-1.1-local -t evidencerag:phase-1 .` passed.
- Temporary Phase 1 candidate container reached healthy, ran as UID 10001, accepted the
  owned Atlas fixture, returned `received`, created exactly one manifest, and was removed.
- GitHub Actions for PR #4 — Python 3.11 passed in 16 seconds, Python 3.14 passed in
  18 seconds, and Container passed in 24 seconds.

Environment: Windows, `uv 0.12.7`, CPython 3.12.9 managed by uv. GitHub Actions
passed on Linux for Python 3.11 and Python 3.14 in PR #2.

## Experiment registry / latest valid metrics

- None. No retrieval, generation, or evaluation system exists yet.

## Known technical debt / risks

- Intake exists, but no PDF page parsing, page-count validation, extraction, rendering,
  retrieval, database, or answer-generation runtime exists. The evaluation rows are schema
  fixtures, not a representative benchmark.
- Python 3.11 and 3.14 are covered by CI, but other supported minors are not individually
  exercised in Phase 0.1.
- The project has no selected license.
- Windows is the only locally verified operating system for this first branch; CI provides
  Linux coverage.

## Decisions changed since master context

- ADR-0003 selects filename-derived logical document identity, exact-byte SHA-256 versions,
  global local-store deduplication, atomic file/manifest publication, and an honest
  `received` intake state. Parser integration remains deferred to the Phase 1.2 research
  gate.

## Next 3 tasks

1. Review Subphase 1.1 and the draft Phase 1 PR.
2. Say `continue Phase 1` only when ready to authorize Subphase 1.2.
3. On continuation, inspect the existing branch, both Phase 1.1 commits, PR CI, and review
   feedback before the parser research gate.
