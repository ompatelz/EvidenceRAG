# Project Status

Updated: 2026-10-29

Current phase: Phase 1.2 complete and CI-verified; awaiting owner review on the Phase 1 draft PR

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
- Phase 1.2 pins PyMuPDF `1.28.2` after a measured Docling/PyMuPDF feasibility gate and
  records the dependency, licensing, and replacement conditions in ADR-0004.
- Explicit parsing extracts deterministic text, conservative headings, captions, captioned
  embedded figures, and page-local structured tables into versioned evidence artifacts.
- Evidence retains zero-based page/read order, stable IDs, parser/representation versions,
  unrotated top-left PDF-point boxes, page geometry/rotation, and normalized top-left boxes.
- Lifecycle records now distinguish `received`, `parsing`, `parsed`, `partial`, and `failed`;
  bounded parser issues never expose source content or private paths.
- Tests cover deterministic fixture extraction, API persistence, parser metadata, tables,
  captions, source and normalized geometry, rotated pages, page ordering, page-only fallback,
  blank pages, malformed PDFs, partial extraction, unexpected exceptions, and page limits.

Verification evidence is updated in this file only after commands have actually run.

## In progress

- Owner review of the Subphase 1.2 implementation and teaching handoff.

## Pending pull requests / links

- [Draft PR #4: Phase 1 — evidence-preserving PDF ingestion](https://github.com/ompatelz/EvidenceRAG/pull/4)
  remains the single Phase 1 PR. Subphase 1.2 principal commit `31a38d3` passed Python 3.11,
  Python 3.14, and Container CI and remains unmerged for review.

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
- Phase 1.2 parser feasibility — PyMuPDF extracted the owned narrative fixture in 0.018
  seconds and the owned structured-table fixture in 0.011 seconds. Docling `2.129.0`
  resolved 106 packages (approximately 1177.8 MiB) plus approximately 494.4 MiB of model
  data but did not finish the first tiny fixture within the bounded local window.
- Phase 1.2 focused parser suite — 11 tests passed.
- Complete Phase 1.2 Python gate — Ruff lint and format checks passed, strict mypy passed
  for 19 source files, and all 55 tests passed in 1.42 seconds.
- `uv lock --check`, deterministic fixture regeneration, and committed evaluation-data
  validation passed after adding pinned PyMuPDF `1.28.2`.
- `uv sync --all-extras --dev` and `docker compose config --quiet` passed. The Phase 1.2
  candidate image built with pinned PyMuPDF, reached healthy as UID 10001, accepted the
  owned table fixture, changed from `received` to `parsed`, persisted five evidence units
  including one structured table, and was removed after verification.
- GitHub Actions for PR #4 head `31a38d3` — Python 3.11 passed in 17 seconds, Python 3.14
  passed in 16 seconds, and Container passed in 17 seconds.

Environment: Windows, `uv 0.12.7`, CPython 3.12.9 managed by uv. GitHub Actions
passed on Linux for Python 3.11 and Python 3.14 in PR #2.

## Experiment registry / latest valid metrics

- None. No retrieval, generation, or evaluation system exists yet.

## Known technical debt / risks

- Parsing exists, but no OCR, rendered-page viewer, retrieval, database, automatic parsing
  queue, or answer-generation runtime exists. The evaluation rows are schema fixtures, not
  a representative benchmark.
- Table detection is page-local. Complex reading order, multi-page tables, vector diagrams,
  equations, crop-box offsets, and rotated-preview mapping are not yet validated broadly.
- PyMuPDF uses AGPL/commercial licensing, while this repository has no selected license.
  Container/source redistribution must not begin until licensing is resolved.
- Python 3.11 and 3.14 are covered by CI, but other supported minors are not individually
  exercised in Phase 0.1.
- The project has no selected license.
- Windows is the only locally verified operating system for this first branch; CI provides
  Linux coverage.

## Decisions changed since master context

- ADR-0003 selects filename-derived logical document identity, exact-byte SHA-256 versions,
  global local-store deduplication, atomic file/manifest publication, and an honest
  `received` intake state.
- ADR-0004 selects pinned PyMuPDF after a bounded feasibility gate and defines parser-native
  coordinates, normalized regions, table structure, conservative relationships, failure
  states, licensing constraints, and rollback.

## Next 3 tasks

1. Review Subphase 1.2 and the updated draft Phase 1 PR.
2. Resolve the project/PyMuPDF distribution-license strategy before publishing a build.
3. Say `continue Phase 1` only when ready to authorize Subphase 1.3.
