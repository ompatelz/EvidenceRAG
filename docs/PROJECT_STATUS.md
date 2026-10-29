# Project Status

Updated: 2026-10-29

Current phase: Phase 1.4 local acceptance gate passed; principal commit and PR CI are in
progress

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
- Phase 1.3 adds bounded fixed-profile PNG rendering, atomic page-set publication, opaque
  page asset IDs, source/crop/media/pixel metadata, and manifest-backed preview responses.
- Anchor resolution maps unrotated source-normalized boxes through page rotation into
  display-normalized and containing pixel boxes. Page and unavailable precision return no
  invented region.
- Rendering lookups are scoped by generated document ID, exact hash/version, evidence ID,
  and zero-based page index. Cross-document, stale-version, invalid-page, and missing-file
  requests fail safely without exposing paths.
- Phase 1.4 connects intake, source-integrity validation, parsing, evidence creation,
  rendering, and artifact persistence through an explicit validated state machine.
- `ready` is now a final commit marker written only after complete version-matching evidence
  and page artifacts are committed. Failures and partial output never claim readiness.
- One-shot ingestion, detailed status, retry, and re-index APIs use server-generated request
  IDs, attempt counts, stage timings, safe error codes, and content-safe JSON logs.
- Retry and re-index regenerate complete derived artifacts from immutable source bytes;
  stale evidence/pages are removed, and stable evidence IDs are replaced rather than
  appended. Ready versions with missing/corrupt artifacts are detected and rebuilt.
- An immutable intake snapshot permits recovery of a missing mutable manifest when the
  original source remains present and hash-valid.
- The focused lifecycle suite injects parser, renderer, evidence, and final-manifest
  failures and checks interruption recovery, cleanup, duplicate/version semantics, rotated
  and blank PDFs, log privacy, and evidence/page identity consistency.

Verification evidence is updated in this file only after commands have actually run.

## In progress

- Create and push the exact Phase 1.4 principal commit, verify all four PR jobs, update the
  final remote evidence, and convert PR #4 from draft to ready for owner review.

## Pending pull requests / links

- [Draft PR #4: Phase 1 — evidence-preserving PDF ingestion](https://github.com/ompatelz/EvidenceRAG/pull/4)
  remains the single Phase 1 PR. The current remote head `2324a81` passed Python 3.11,
  Python 3.14, and Container CI for the final Subphase 1.3 documentation repair. The PR
  remains draft and unmerged while Subphase 1.4 is verified.

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
- Phase 1.3 focused rendering suite — 21 tests passed in 2.04 seconds. Coverage includes all
  four rotations, inverse round trips, multiple DPI scales, boundary boxes, crop/media
  offsets, security scopes, stale versions, missing/corrupt artifacts, rendering/per-page/
  total-pixel limits, geometry mismatches, page-only and unavailable precision, and a
  pixel-based owned-table regression.
- Manual 144-DPI overlay inspection — the computed `(144, 319, 1065, 592)` pixel box
  enclosed the complete owned fixture table border and cells and excluded its separately
  extracted caption. No clipping, overlap, or alignment defect was observed.
- Complete Phase 1.3 Python gate — `uv sync`, Ruff lint/format, strict mypy, and pytest
  passed on the exact pre-commit tree; 76 tests passed in 3.36 seconds. `uv lock --check`,
  deterministic fixture regeneration, and committed evaluation-data validation also passed.
- `docker compose config --quiet` and the Phase 1.3 candidate image build passed. The
  temporary container reached healthy as UID 10001; upload returned `received`, parsing
  returned `parsed`, rendering produced one PNG, the served 48,106-byte PNG matched its
  manifest SHA-256, and the table anchor resolved to `(144, 319, 1065, 592)`. The temporary
  container was removed after verification.
- GitHub Actions for PR #4 head `07a7da5` — Python 3.11 passed in 21 seconds, Python 3.14
  passed in 23 seconds, and Container passed in 19 seconds.
- Phase 1.4 focused lifecycle suite — 16 tests passed in 2.85 seconds. It covers successful
  owned-fixture ingestion, duplicates, changed versions, re-index, retry, parser/renderer/
  evidence/final-manifest failures, cleanup, manifest recovery, missing ready assets,
  corrupt/blank/rotated PDFs, interrupted work, log privacy, and invalid transitions.
- Complete Phase 1.4 Python gate — `uv sync`, lock check, Ruff lint/format, strict mypy,
  and all 92 tests passed in 7.96 seconds. Deterministic fixture regeneration and committed
  evaluation-data validation also passed.
- Manual 96-DPI inspection passed for the owned Atlas narrative/diagram, owned structured
  table, and a temporary 90° rotated fixture. Every reported region enclosed its visible
  source; the table box excluded its caption; rotation metadata and display dimensions
  agreed. No anchors were downgraded in these three PDFs. Detailed bounded timings and
  unsupported vector-diagram behavior are recorded in `docs/phase1_gate.md`.
- `docker compose config --quiet` passed and `evidencerag:phase-1` built successfully with
  `VCS_REF=phase-1.4-local`. A temporary container became healthy, ran as UID 10001,
  ingested the owned table fixture through the one-shot endpoint, returned `ready` on the
  first attempt with five evidence units, one preview, and all five timing stages, then was
  removed.

Environment: Windows, `uv 0.12.7`, CPython 3.12.9 managed by uv. GitHub Actions
passed on Linux for Python 3.11 and Python 3.14 in PR #2.

## Experiment registry / latest valid metrics

- None. No retrieval, generation, or evaluation system exists yet.

## Known technical debt / risks

- No polished viewer, retrieval, database, durable background jobs, or answer-generation
  runtime exists. The evaluation rows are schema fixtures, not a representative benchmark.
- Ingestion occupies one HTTP request and uses a process-local lock. It neither coordinates
  multiple processes nor automatically resumes after a restart; interrupted work requires
  an explicit retry. ADR-0006 defines the measurements that would justify durable jobs.
- Table detection is page-local. Complex reading order, multi-page tables, vector diagrams,
  equations, unusual malformed page boxes, and rotated/cropped production documents are not
  yet validated broadly.
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
- ADR-0005 defines the fixed rendering profile, crop/rotation transforms, containing-pixel
  rounding, atomic page publication, page asset security, manual verification, and rollback.
- ADR-0006 defines the synchronous state machine, atomic ready boundary, whole-artifact
  retry/re-index policy, immutable intake recovery, safe telemetry, and durable-job triggers.

## Next 3 tasks

1. Complete the Phase 1.4 full local, container, manual-inspection, and CI gates.
2. Review and merge Phase 1 PR #4 only after owner approval.
3. Begin Phase 2 — evaluation seed and search baselines only after Phase 1 is merged and
   explicitly authorized.
