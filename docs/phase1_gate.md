# Phase 1 acceptance and manual verification

Date: 2026-10-29

This record contains engineering verification for the final Phase 1 tree. It does not
claim benchmark quality, broad layout understanding, or production performance.

## Manual fixture inspection

Three legally safe local PDFs were passed through the one-shot HTTP ingestion endpoint at
96 DPI. The generated previews were rendered independently and inspected with every genuine
region anchor drawn as a red rectangle.

| Fixture | Layout | Result | Evidence | Preview | Observed total |
|---|---|---:|---:|---:|---:|
| `atlas-narrative.pdf` | heading, prose, vector flow diagram, caption | ready | 6 units | 816×1056, 28,212 bytes | 87.648 ms |
| `retrieval-table.pdf` | heading, prose, bordered table, caption | ready | 5 units | 816×1056, 31,099 bytes | 59.467 ms |
| temporary rotated PDF | 90° text and boxed label | ready | 2 units | 160×320, 5,676 bytes | 53.589 ms |

These are single local observations on small fixtures, not latency benchmarks. Each used
one attempt and one page. Validation, parsing, rendering, persistence, and total timings
were present and non-negative.

### Observations

- **Narrative/diagram:** the heading, two prose lines, three node labels, caption, and
  footer landed on their visible source text. The vector boxes and arrows were not emitted
  as a semantic figure; this is an explicit vector-diagram limitation, not a failed anchor.
- **Structured table:** the parser emitted a structured table plus caption. The table
  region enclosed the complete grid and excluded the separately anchored caption. Headers,
  rows, and visible values matched the owned fixture.
- **Rotation:** the preview recorded 90° rotation and swapped display dimensions. Both
  text anchors enclosed the visibly rotated source text; source and display coordinates
  were not mixed.
- **Downgraded anchors:** none of these three fixtures required page or unavailable
  precision. Separate automated tests verify that page-only evidence has no invented box,
  unavailable evidence has no preview, and an empty extracted page terminates as partial.
- **Resource boundary:** source files were 3,258, 3,713, and 1,103 bytes. All completed
  within the configured one-page/96-DPI bounded run. This sample is too small to justify
  concurrency, throughput, or maximum-document claims.

Temporary PDFs, rendered previews, overlays, and local artifacts live under ignored
`tmp/pdfs/` and are not release artifacts.

## Acceptance mapping

| Criterion | Evidence |
|---|---|
| Safe intake and limits | Intake tests cover valid, invalid, empty, oversized, traversal, interrupted writes, and confined paths. |
| Stable hash/version identity | Exact SHA-256 versions, duplicate idempotence, and changed-content tests; ADR-0003. |
| Provenance-preserving evidence | Parser tests and version/page identity assertions in the lifecycle suite. |
| Honest anchors and safe previews | Rotation, scale, crop, security, page-only/unavailable, pixel regression, and manual overlays. |
| Failed ingestion never ready | Parser, renderer, evidence persistence, final manifest, corrupt PDF, and blank-page failure injection. |
| Retry/re-index remain clean | Stable IDs, no duplicate evidence, stale-page removal, whole-artifact replacement, missing-page rebuild. |
| Useful safe telemetry | Request-ID/header, stage timing, attempt count, status, and log privacy tests. |
| Unit/integration/end-to-end tests | Complete pytest suite plus dedicated owned-fixture CI lifecycle job. |
| Container remains valid | Compose, build, non-root health, and one-shot container smoke evidence recorded in project status. |
| Documentation matches behavior | README, architecture, ADR-0006, this gate, and project status. |

Final command outcomes, commit identifiers, and GitHub Actions results are recorded in
`docs/PROJECT_STATUS.md` after the exact committed tree and remote CI finish.
