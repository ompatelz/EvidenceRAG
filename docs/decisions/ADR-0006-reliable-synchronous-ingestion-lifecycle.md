# ADR-0006: Reliable synchronous ingestion lifecycle

Status: Accepted

Date: 2026-10-29

## Context

Phase 1 already accepted immutable PDF bytes, extracted evidence, and rendered page
previews, but each operation was explicit and independent. A client could observe parsed
evidence without previews, previews without a final readiness claim, or remnants from an
interrupted attempt. Phase 1 needs one truthful boundary at which all required artifacts
for an exact document version are available together.

The current product is a bounded, local, single-user MVP. Measurements on the two small
owned fixtures complete well within an HTTP request, and no requirement yet needs work to
survive a process restart. Adding a broker, worker, or distributed database would therefore
add failure modes without solving an observed bottleneck.

## Decision

### State machine and readiness

The version manifest is the lifecycle record. The orchestration path uses these states:

```text
received -> validating -> parsing -> rendering -> persisting -> ready
                    |          |           |           |
                    +----------+-----------+-----------+-> failed
                               +-------------------------> partial
failed/partial/interrupted -> validating
ready -> validating (explicit re-index)
```

The implementation validates every transition. `ready` is a commit marker: it is written
only after the version-matching evidence artifact, complete page-preview set, and their
metadata have been atomically published. A failed final manifest write removes derived
artifacts and records failure where possible. `partial` preserves useful, explicitly
qualified output but is never presented as ready.

### Synchronous orchestration and concurrency

One service performs validation, parsing, rendering, persistence, and the final manifest
transition synchronously. An in-process lock serializes attempts in this local MVP. This is
not a cross-process or multi-host lock, and the deployment must remain one process until a
durable coordinator is introduced.

### Identity, duplicates, retry, and re-index

- Exact bytes retain the SHA-256 version identity established in ADR-0003.
- A duplicate upload returns an already-consistent ready version without another attempt.
- If a ready manifest references a missing or inconsistent derived artifact, the service
  marks it failed and rebuilds it instead of returning false success.
- `retry` is permitted for failed, partial, or interrupted work. It removes derived output
  and rebuilds from the immutable source.
- `reindex` deliberately rebuilds a ready version. Stable evidence IDs replace, rather
  than append to, the evidence artifact.
- Every attempt regenerates the entire evidence artifact and complete pages directory, so
  stale evidence and stale previews cannot survive a successful attempt.

### Recovery and atomicity

Intake stores both a mutable `manifest.json` and an immutable received-state
`intake.json`. If the mutable manifest is missing, it can be recreated from the intake
snapshot only when the immutable source still exists. Before processing, source size and
SHA-256 are revalidated.

The store continues to use same-filesystem atomic replacement. Rendering stages a complete
page directory; evidence is a complete versioned JSON artifact. Only after both are
committed may the manifest transition to `ready`.

### Observability and privacy

Every HTTP request receives a server-generated opaque request ID returned as
`X-Request-ID`. The manifest records the last request ID, attempt count, stage timings,
safe failure code, and failure stage. JSON logs contain only request/version identifiers,
state, stage, duration, and bounded error codes. Filenames, extracted text, private paths,
and parser exception strings are excluded.

Timings are diagnostic wall-clock durations, not benchmark results. They cover validation,
parsing, rendering, persistence, and total orchestration time. They are not suitable for
billing or distributed tracing.

### When to move to durable jobs

Synchronous ingestion remains appropriate while bounded documents finish comfortably
inside the configured HTTP timeout and one process is the supported deployment. Revisit
this decision when measurements show any of the following:

- ingestion p95 approaches 50% of the request timeout or the product latency objective;
- permitted page or pixel limits regularly make requests exceed that objective;
- concurrent uploads create material lock wait or starve health/API traffic;
- work must resume automatically after process or host failure;
- retries must survive restarts or be scheduled independently of a client request;
- horizontal workers, fair scheduling, cancellation, or per-tenant isolation become real
  requirements.

At that point, preserve this state machine and idempotent artifact contract behind a
durable job record, lease/heartbeat, and transactional or compare-and-swap ready commit.
Do not add a queue solely because ingestion is conceptually asynchronous.

## Consequences

The API now offers one-shot upload-and-ingest plus explicit status, ingest, retry, and
re-index operations. Clients can rely on `ready` having a precise meaning, and operators
can distinguish failed stages without exposing document content.

The trade-off is that one long document occupies an HTTP request and all attempts in one
process are serialized. A process can stop between atomic writes; the next explicit retry
detects the nonterminal state and restarts from the immutable source. Automatic restart
recovery and multi-process exclusion remain deferred.

## Alternatives considered

- **Keep independent parse and render endpoints only.** Rejected because no atomic
  readiness boundary would exist. The endpoints remain for inspection and compatibility.
- **Append evidence and previews incrementally.** Rejected because retries could retain
  stale or duplicate artifacts.
- **Introduce a distributed queue now.** Rejected because owned-fixture measurements and
  the single-process scope do not justify its operational cost.
- **Use a database transaction for all artifacts.** Rejected for this local file-backed
  phase; large binary previews remain better represented as versioned files.

## Verification and rollback

Unit and integration tests exercise valid/invalid transitions, duplicates, changed
versions, re-index, parser/renderer/storage/manifest failures, cleanup, recovery, missing
assets, interrupted states, structured-log privacy, and version/page consistency. A
dedicated CI job runs the bounded lifecycle suite using only repository-owned fixtures.

Rollback is the principal Phase 1.4 commit. Existing intake, parse, render, evidence, page,
and anchor endpoints remain separately usable at the Phase 1.3 boundary. Any rollback must
also remove the new lifecycle endpoints and state fields together so clients cannot observe
states that no service owns.
