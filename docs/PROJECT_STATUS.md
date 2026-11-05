# Project Status

Updated: 2026-11-05

Current phase: Grounded QA checkpoint 2 on `codex/grounded-qa` (draft PR #6). Phase 2
baselines merged into `main` at `73c49f8`. All 31 candidate labels remain
`needs_review`, and the Phase 2 human-review gate is **not passed**. A merged
implementation must not be described as a validated Phase 2 benchmark.
Phase 1 PR #4 is merged into `main` at `37e485c`.

Hybrid RRF retrieval is implemented and measured in `docs/hybrid_retrieval.md`.
The selected validation configuration is RRF constant 60, per-method prefetch
10, final K=5. Validation nDCG@5 is 0.781 on provisional candidate labels,
below both BM25 (0.797) and dense (0.814); no quality gain is claimed.
Optional CPU reranking is implemented and measured in `docs/reranking.md`.
On provisional validation labels it raises hybrid MRR@5 from 0.727 to 0.773,
matching dense, with about 45 ms mean additional per-query CPU time. It is
disabled by default. Answer generation and evidence inspection await later
checkpoints.

## Phase 2 review expansion

- Two deterministic repository-owned CC0 two-page PDF families add protocol and
  cache notes with equations, exact identifiers, numeric facts, policy rows,
  multi-page evidence, and difficult negative questions. All four new pages were
  rendered and visually inspected; parser evidence IDs, pages, and regions were
  checked against the proposed labels. The five frozen chart rows are unchanged.
- The seed now contains 31 candidates: 13 development, 13 validation, 5 frozen
  test; 5 unanswerable (16.1%), 2 visual-dependent, 0 human verified.
  `datasets/eval/REVIEW_PACKET.md` gives the owner source links and an unchecked
  decision line for every item. The packet has no retriever rankings.
- Both E0/E1 were rerun on the 26 development/validation candidates over 52
  evidence units. The provisional report has 22 scored answerable nonvisual
  queries, observed examples for each method winning, and one joint miss at K=5.
  These numbers are unreviewed diagnostics, not validated performance claims.
- The expanded tree passed local locked sync/check, Ruff lint/format, strict
  mypy, 122 pytest tests with one live Qdrant-server skip, deterministic PDF
  regeneration, and strict source/evidence validation. Commit
  `15edd0612daa15a29f90a04fcf54de4f92cc56f5` passed all five hosted CI
  checks: Python 3.11, Python 3.14, Ingestion end-to-end, Qdrant integration,
  and Container. Both raw runs were regenerated against that committed source
  with clean source-tree flags and normalized dataset SHA-256
  `cc8ee84a47f4d1930154b2d466e2a56c26739b0fe45ec267f988ddaf7afb5a46`.
  Owner source-page decisions remain pending. The assistant's item-by-item
  source audit is recorded in `docs/phase2_label_audit.md`; it does not count
  as human verification.

## Phase 2.4 checkpoint

- The shared runner accepts closed E0/E1 configs for development and validation
  only. It rejects frozen-test selection, changed K values, incompatible E0/E1
  manifests, malformed configs, duplicate/cross-document rankings, and raw metric
  inconsistencies. Each retrieval error becomes a per-query failure without saving
  exception text; failed queries leave the scored denominator.
- `reports/baselines.md` is generated from the committed raw E0/E1 runs and
  includes split/category metrics, provenance, failure taxonomy, timing assumptions,
  and observed E0/E1 wins or misses. Its original 13-question pilot was a
  provisional diagnostic, not a validated quality or latency claim.
- Both benchmark configs and report generation passed locally with the cached real
  MiniLM model. The frozen test was not searched or used for tuning. The full local
  gate passed after the portability fix: locked sync, lock check, Ruff lint/format,
  strict mypy, 121 pytest tests passed and one live-server test skipped locally.
  Deterministic fixture and strict seed validation passed.
- Principal commit `defdfe2a9b5db2a83131234cdb0ab0b22a293d5b` was pushed.
  Its Python 3.11/3.14 CI jobs failed because the first report hashed raw
  Windows CRLF dataset bytes while Linux checked out LF. Dataset and source text
  hashing now normalize line endings; a regression test confirms the hash equals
  the committed blob on both platforms. Corrective commit
  `6eb85989384e83f0de1e32cc5f34e8e2c47c6f29` passed all five hosted checks:
  Python 3.11, Python 3.14, Ingestion end-to-end, Qdrant integration, Container.
  Both saved runs were regenerated against that committed source with a clean
  source tree and normalized dataset SHA-256
  `77c6e1750a3841c346406c7aca449b11e727963e33531efeda1ac8d917257fe3`.
- The human-review gate remains open until owner source-page review and a fresh
  gate run based on corrected labels are complete. The later owner instruction
  permits merging the implementation as a provisional pilot only.

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
- Local Docker Desktop was unavailable; live Qdrant behavior passed hosted CI.
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

- Owner review of all 31 candidate labels and visual-region judgments.
- Apply future owner corrections and rerun the human-review gate without using
  frozen-test results for tuning.

## Pull requests / links

- [Merged PR #4: Phase 1 — evidence-preserving PDF ingestion](https://github.com/ompatelz/EvidenceRAG/pull/4).
- [PR #5: Phase 2 — evaluation seed and search baselines](https://github.com/ompatelz/EvidenceRAG/pull/5)
  contains four implementation subphases, cross-platform correction `6eb8598`,
  and review-expansion commit `15edd06`. All five hosted checks passed on the
  expanded corpus. The
  owner requested code merge with the human-review gate explicitly outstanding;
  the provisional result and label status must remain clear after merge.

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

- E0 provisional run: `reports/runs/e0-phase2-pilot.json` contains raw rankings
  for 26 development/validation queries and 22 scored answerable nonvisual
  candidate labels. All labels await owner review; no validated performance
  result exists.
- E1 provisional run: `reports/runs/e1-phase2-pilot.json` uses the same dataset,
  corpus, query IDs, K values, and relevance unit. The report records observed
  E0/E1 wins and one joint miss at K=5. No frozen-test run exists.

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

1. Owner reviews all 31 candidate labels in `datasets/eval/REVIEW_PACKET.md` and
   records corrections or approval from direct source-page inspection.
2. Apply reviewed labels, rerun E0/E1 and the report, and verify the full gate
   including CI without using frozen-test results for tuning.
3. Decide whether remaining external-document and PyMuPDF/repository licensing
   limits are acceptable for this PR before merge or distribution.
