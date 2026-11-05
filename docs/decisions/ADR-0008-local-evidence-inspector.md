# ADR-0008: Local evidence inspector

Status: accepted for the grounded-QA draft milestone, 2026-11-05.

## Decision

Serve a static three-panel inspector from the existing API. Keep upload,
question, answer and retrieval trace, and cited source page visible as one
workflow. Resolve citations through the exact-version anchor endpoint, then
load the existing preview endpoint. Draw an overlay only for a region-precise
anchor with display coordinates. Treat page-only and missing previews as
distinct visible states.

Expose a local query mode selector for BM25, dense, hybrid RRF, and optional
reranking. Display ranks and labelled scores without pretending the score
scales are comparable. Report stage timings with model/index setup included.
Use cached model snapshots only. Keep optional fixture answer generation off
unless explicitly enabled by local configuration; the default answer path
abstains.

## Rationale and limits

This reuses already versioned evidence and preview contracts without adding a
frontend build, a remote service, or a new persistence layer. The browser
never sees private artifact paths. The inspector demonstrates inspectability,
not semantic claim verification. Its one fixture answer tests the full
navigation path but is not a general answering model. Dense indexing is
rebuilt in memory for each request, so its timings are demonstrative.

The repository-owned fixture was the only document used in the manual
end-to-end check. No permission to use an additional private PDF was assumed.

## Reversal

Remove the `/inspector` routes and static assets, the optional demo generator,
and the additional query-mode selection. The versioned evidence, anchors,
page previews, and offline retrieval runners remain usable independently.
