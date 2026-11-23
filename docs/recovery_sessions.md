# Recovery sessions and retrieval traces

v0.5.0 adds process-local recovery sessions and optional page diversity. The caller
still supplies its own reasoning/drafts. No generation provider is invoked, no
model is downloaded, and grounding-v1 thresholds remain unchanged.

## Recover within a fixed scope

```python
from evidence_rag.answers import DraftAnswer

# document is an ingested DocumentRef in a long-lived EvidenceRAG instance.
initial = rag.recovery.start(
    document, "What sampling rate is documented?", [],
    DraftAnswer(status="insufficient_evidence"),
)
if initial.status == "active":
    state, evidence = rag.recovery.search(initial.session_id, "calibration sampling rate")
    # Inspect returned evidence. Your model supplies a revised structured draft.
    # final = rag.recovery.recheck(state.session_id, selected_ids, revised_draft)
```

Starting the session checks the actual initial draft. If it is already answered,
contradicted, or blocked by unavailable verification, the session closes
immediately. Recoverable missing-evidence/citation outcomes allow up to two
additional targeted BM25 search attempts and one recheck. Search execution errors
consume an attempt too. A recheck closes the session whether it answers, withholds
or raises an execution error. Schema-invalid requests rejected before a tool call
reaches the manager do not execute or consume budget.

The original question and document/version are fixed in the engine. Rechecks can
use only IDs supplied by the initial checked pack or session search packs; known
IDs obtained outside that session do not silently become available. Reconstructing
the usual bounded pack and semantic support checking remain mandatory.

`rag.recovery.status(session_id)` returns counters, observed IDs, original and final
check outcomes, and the bounded event receipt. Responses can contain untrusted
source/draft text. Never execute instructions embedded in them. Snapshot models
are immutable; modifying exported JSON does not change engine state.

Repeated starts for the same whitespace-normalized question and exact document
version return the existing session, including a closed one. This does not check
a newly supplied draft or reset counters. There are at most 64 sessions per engine,
with a fixed 30-minute lifetime after creation. Capacity errors require waiting
for expiry or explicitly choosing a different application process; an agent must
not restart or paraphrase the question to evade the intended task budget.

Sessions live only in the trusted engine process. They are not a cross-process,
multi-document, global security or spending boundary. The stateless APIs remain
available; a trusted client can call them separately. For collection tasks, retain
the workflow's shared task budget across document-scoped sessions. There is no
automatic model-driven query rewriting or drafting loop in the server.

## MCP tools

| Tool | Arguments | Result |
| --- | --- | --- |
| start_recovery | document_id, document_sha256, question, evidence_ids, draft | Initial checked session receipt |
| search_recovery | session_id, query | Updated session and retrieval pack |
| recheck_recovery | session_id, evidence_ids, draft | Closed session and final checked outcome |
| recovery_status | session_id | Counters, observed IDs and event receipt |

Start/search/recheck mutate process state and carry non-read-only MCP annotations.
Status is read-only. Missing/expired sessions, exhausted budgets and closed sessions
have fixed source-free error codes. CLI invocations start new processes and cannot
resume these sessions. Saved receipts are records, not resumable tokens.

## Inspect retrieval coverage

```python
from evidence_rag.sdk import CollectionSearchRequest

result = rag.search_collection(CollectionSearchRequest(
    documents=(document,), question="retry policy exceptions",
    contextual_indexing=True, candidate_limit=20, diversify_pages=True,
))
print(result.coverage)
for candidate in result.ranking:
    print(candidate.retrieval_rank, candidate.selected_rank, candidate.packed)
```

`candidate_limit` is 5–50, default 5. `diversify_pages` defaults to false. With it
enabled, selection prefers at most two units per exact document/version/page,
then fills remaining places by original rank. This can expose another page that
would otherwise be crowded out. It can also displace useful same-page evidence;
use the ranking trace to inspect the tradeoff. Scores are unchanged and do not
become support judgments. Default selection remains the existing ranked top five.

The response preserves every candidate's original rank/score and identifies its
selected rank, if selected, and whether it entered the pack. Coverage reports
candidate/selected/packed counts, distinct packed pages and versions, character
usage and truncation. Exclusions include every fetched candidate omitted from
the pack. All output retains the five-unit / 4000-character budget. Expanding the
candidate pool does not authorize more document versions or claim completeness.

## Development evaluation

The pinned NIST PDF probes retain the original five-candidate variants and add
plain/headings/page-spread variants with the same 20-candidate pool and the same
pack budgets. Raw artifacts include rankings, packs, coverage, code hashes,
source hashes and timings. CI prints per-query pages and page-hit counts so misses
can be inspected without confusing them with context-budget exclusions.

These six agent-audited page labels remain development data pending human review.
Page hits do not measure answer accuracy, full premise recall, citation support
or reliable abstention. Historical frozen test outcomes are not rerun or tuned.
