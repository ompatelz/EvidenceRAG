# Local reliability

Run the app on loopback for one user and one process. Compose binds the
published port to loopback. The query path loads the requested immutable
document version and rejects an artifact whose embedded identity disagrees
with its storage location. Page previews also verify their content hash.
Re-ingestion can regenerate missing derived files from the original PDF.

| Failure | What the caller sees |
| --- | --- |
| Empty, invalid or oversized upload | Intake rejects it with a bounded error. |
| Parser, renderer or persistence failure | The ingestion record retains the failed stage. Retry rebuilds derived artifacts from the source. |
| Missing, mismatched or corrupt artifact | The query returns an artifact error or policy abstention. The preview endpoint rejects missing or invalid assets. |
| Missing cached model | Dense or reranked query returns HTTP 503. BM25 has no model dependency. |
| Local retrieval fails | HTTP 503 or an indexing abstention under the configured policy. |
| Missing generator, invalid citation, contradictory assessed evidence | The response carries a reason and withholds the answer when the applicable checks fail. |

The API assigns an `X-Request-ID` and logs a route template, status and
elapsed time at INFO. Query events add mode, bounded outcome and stage times.
Logs omit questions, evidence text, filenames and exception messages. Run
with Uvicorn's `--no-access-log` to omit raw paths from its access log.
`/health` checks liveness. `/ready` probes writable artifact storage.
Optional model failures remain scoped to requests that need those models.

Generation waits up to two seconds by default. A timed-out adapter retains
its single slot until its call exits, and further attempts fail closed
while that slot is occupied. Adapters must enforce their own I/O deadlines
because Python cannot interrupt a running native or network call safely.
The verifier and reranker also have bounded waits. In-process PDF parsing
and dense model loading have resource limits but no hard wall-clock
preemption. Uploads and queries have no automatic service-level retry.
Document contents can contain instructions. The built-in fixture adapter
uses a fixed response and scoped evidence, and citation validation runs
for injected adapters. General generator injection resistance remains
unmeasured.

## Measured local smoke

`uv run --locked python scripts/measure_local.py --output reports/generated/local-smoke.json`
runs one Atlas PDF and two sequential BM25 queries through the ASGI app
with a fresh artifact store and application. It checks both a cited
fixture answer and an abstention, then resolves and fetches the citation.
The OS file cache was uncontrolled. The run used a Windows i7-13700H
with 20 logical CPUs. [Raw results](../reports/runs/local-release-smoke.json).

| Measurement | Time or size |
| --- | ---: |
| One-page ingestion, request wall time | 173.21 ms/page |
| Validation / parsing / rendering / persistence | 2.23 / 17.07 / 47.88 / 14.82 ms |
| Ingestion lifecycle total | 95.98 ms |
| Cited query, wall / handler / BM25 search | 12.24 / 6.27 / 0.10 ms |
| Unsupported query, wall / handler / BM25 search | 6.98 / 3.24 / 0.07 ms |
| Process CPU time for ingestion, queries and citation fetch | 281.25 ms |
| Persisted artifacts / served PNG | 61,125 / 46,423 bytes |

The smoke builds an in-memory BM25 index over six evidence units per query.
There is no on-disk BM25 index to size. It records CPU time and artifact
size. Peak memory and steady-state throughput remain unmeasured.
