# Project Status

Updated: 2026-11-04

Current phase: Phase 2.3 dense baseline implemented and verified on draft PR #5;
Subphase 2.4 awaits the owner's next checkpoint instruction. Phase 1 PR #4 is
merged into `main` at `37e485c`; its final head `dfa3cd4` is an ancestor of
current `main`.

## Phase 2.3 checkpoint

- Selected FastEmbed `0.9.1` on CPU with the Apache-2.0 MiniLM ONNX model at
  pinned Qdrant repository revision `d13954661f83248295ba75c1ed411eef3b7b936e`
  (384 dimensions). Qdrant client `1.20.0` and NumPy `<2.5` are locked; no model
  download occurs in ordinary CI. Official model, FastEmbed, and Qdrant contracts
  were checked before implementation; details are in `docs/dense_baseline.md`.
- E1 uses the same persisted canonical evidence units and development/validation
  questions as E0. It validates dataset hash, document versions, query IDs, binary
  evidence-unit relevance, and K=1/3/5 compatibility before running. The frozen
  chart family was not searched.
- The Qdrant index checks dimensions, cosine distance, model revision, and active
  generation; version scope is applied inside Qdrant before results are returned.
  Duplicate upsert, whole-generation rebuild, stale-version deletion, and outage
  failure are tested with a deterministic download-free embedding double. A bounded
  server integration job passed in hosted CI.
- Real CPU E1 run saved to `reports/runs/e1-phase2-pilot.json`: 8 queries, 6 scored
  answerable nonvisual candidate labels, 11 evidence units. E0 and E1 have the
  **same relevant-unit ranks for all six**. In both splits, both methods have
  Hit Rate@1=2/3, Hit Rate@3=3/3, Recall@3=3/3, MRR@3=5/6, and nDCG@3≈0.877.
  These are provisional unreviewed-label diagnostics, not evidence of parity on
  a representative benchmark. Raw rankings, manifests, and separate query embed/
  vector-search timings support the comparison.
- Local Docker Desktop was unavailable, so live Qdrant server behavior awaits CI.
  Final pre-commit local gate passed: `uv sync --all-extras --dev`, `uv lock --check`,
  Ruff lint/format, strict mypy, and 110 pytest tests in 8.35 seconds; the live
  Qdrant test was skipped locally because no server URL was configured. Deterministic
  fixture and strict seed validation also passed. Commit
  `faf550637da0eeac820fe1fb957ad6cf8b9778d6` is pushed to draft PR #5.
  GitHub Actions run 41865852141 passed all five checks: Python 3.11, Python
  3.14, Ingestion end-to-end, Qdrant integration, and Container.

## Phase 2.2 checkpoint

- Corrected the Phase 2 corpus manifest and evaluation rows to use the canonical
  filename-derived document IDs produced by ingestion. Strict validation now rejects
  any future manifest/ingestion identity mismatch.
- E0 BM25 rebuilds from persisted canonical evidence artifacts, retains exact
  document/version provenance, applies scope before ranking, and gives deterministic
  evidence-ID ordering on ties. Its tokenizer, parameters, identity, lifecycle,
  deletion, and metric definitions are documented in `docs/bm25_baseline.md`.
- The CLI saves raw per-query rankings, timings, source/dataset/manifest hashes,
  index ID, configuration, environment, and evidence-unit metrics for development
  and validation only. The frozen-test family was not searched.
- Candidate-label E0 run: 8 queries, 6 scored answerable nonvisual queries,
  11 evidence units. Both splits have Hit Rate@1 2/3, Hit Rate@3 3/3,
  Recall@3 3/3, and MRR@3 5/6. These are **provisional, unreviewed-label**
  diagnostics from `reports/runs/e0-phase2-pilot.json`, not portfolio claims.
- Final pre-commit local quality gate passed: `uv sync --all-extras --dev`, Ruff
  lint/format, strict mypy, and 102 pytest tests in 6.98 seconds. Lock check,
  deterministic fixture regeneration, strict seed validation, and E0 CLI run
  passed. Principal Subphase 2.2 commit `eb44a0f21f281633405265a5b260ca60d234d687`
  was pushed to the existing draft PR #5. The documentation follow-up commit
  `2654460e1e6ff44b101634eb537e3ad5018d3c81` has all four GitHub Actions
  checks passing (Python 3.11, Python 3.14, Ingestion end-to-end, Container).

## Phase 2.1 checkpoint

- Branch `codex/phase-2-search-baselines` was created from current `origin/main`.
- Three deterministic, repository-authored CC0 PDF families are recorded with source,
  date, SHA-256, content version, and redistribution permission. The new queue chart
  visually distinguishes scheduler modes without text listing bar values.
- `datasets/eval/phase2_seed.jsonl` has 13 candidate questions: 4 development,
  4 validation, and 5 frozen test; 3 unanswerable (23.1%), 2 visual-dependent.
  All 13 need owner review; **none is claimed human verified**. The older schema-only
  fixture rows were also marked `needs_review`, and their caption-answerable diagram
  item is no longer labeled visual-dependent.
- Source hashes, duplicate/near-duplicate questions, version and split references, and
  optionally parser-produced evidence ID/page/region consistency are validated. CI now
  requests strict evidence validation for the Phase 2 seed.
- The chart family is frozen. Do not run retrieval or tune on its questions. This small
  synthetic pilot does not cover equations, multi-page documents, or external sources.
- Subphase 2.1 full local quality gate passed: `uv sync --all-extras --dev`, Ruff
  lint/format, strict mypy, and 95 pytest tests (final pre-commit run: 4.85 seconds).
  `uv lock --check`, deterministic PDF regeneration, schema-fixture validation, and
  strict Phase 2 seed validation also passed.
- Principal commit `c4b285c8eb7495fe92aaa0d574777ab49369af0d` was pushed to
  [draft PR #5](https://github.com/ompatelz/EvidenceRAG/pull/5). On that head,
  GitHub Actions passed Python 3.11 (25s), Python 3.14 (22s), Ingestion end-to-end
  (10s), and Container (30s). No retrieval result or human-reviewed label is claimed.

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

- Owner review of all 13 candidate labels and visual-region judgments.
- Subphase 2.4 benchmark gate awaits the owner's next `continue Phase 2`.

## Pending pull requests / links

- [Merged PR #4: Phase 1 — evidence-preserving PDF ingestion](https://github.com/ompatelz/EvidenceRAG/pull/4).
- [Draft PR #5: Phase 2 — evaluation seed and search baselines](https://github.com/ompatelz/EvidenceRAG/pull/5)
  is open with Subphases 2.1, 2.2, and 2.3 pushed. The latest 2.3 implementation
  commit passed all five hosted checks, including Qdrant integration. The PR remains
  draft and unmerged.

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
- GitHub Actions for PR #4 principal head `9d302b5` — Python 3.11 passed in 22 seconds,
  Python 3.14 passed in 21 seconds, Ingestion end-to-end passed in 14 seconds, and Container
  passed in 23 seconds.

Environment: Windows, `uv 0.12.7`, CPython 3.12.9 managed by uv. GitHub Actions
passed on Linux for Python 3.11 and Python 3.14 in PR #2.

## Experiment registry / latest valid metrics

- E0 provisional run: `reports/runs/e0-phase2-pilot.json` contains the exact
  rankings and manifest. Its 6 scored labels are all pending human review;
  there is no validated performance result yet.
- E1 provisional run: `reports/runs/e1-phase2-pilot.json` uses the same dataset,
  corpus, query IDs, K values, and relevance unit. Both methods have identical
  relevant ranks on the six scored candidates. No frozen-test run exists.

## Known technical debt / risks

- No polished viewer, retrieval API, database, durable background jobs, or
  answer-generation runtime exists. The evaluation rows are a tiny synthetic pilot,
  not a representative human-reviewed benchmark.
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

1. Review and correct the 13 candidate labels before counting any as human verified.
2. On explicit `continue Phase 2`, harden the shared benchmark runner and publish
   the Phase 2 gate report from saved raw outputs.
3. Resolve the PyMuPDF/repository licensing strategy before distributing builds.
