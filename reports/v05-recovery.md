# v0.5.0 recovery and retrieval delivery record

This increment addresses two engineering gaps: recovery budgets were previously
caller-owned instructions/ledgers, and collection search did not expose all
candidate/selection decisions. It does not change grounding-v1 or claim a general
answer-quality improvement. [Behavior and boundaries](../docs/recovery_sessions.md)

The new session manager fixes the original document/version and question, counts
failed search execution, permits two additional searches and one final recheck,
and closes after rechecking. Only IDs observed in the initial checked pack or
session searches can enter that recheck. Repeated starts return the existing
session, including its counters/closed state. State is bounded, expires after
30 minutes and is confined to one trusted engine process.

Tests cover final withholding, terminal verifier failure, failed-attempt counting,
idempotent starts, unobserved evidence, expiry/capacity/process boundaries and
concurrent searches. Page-selection tests check version-aware diversity, fallback
when only one page matches, preserved scores and actual pack/coverage accounting.
MCP protocol tests exercise session start/search/recheck and rejection after close.

An isolated agent received the revised workflow, one authorized owned development
PDF and a saved empty-evidence/insufficient draft for a calibration-rate question.
It used the actual cached pinned local verifier, one BM25 recovery search and one
recheck. The final receipt was closed/answered, with a valid region citation and
model-estimated support. No generation provider or model download was used.
[Raw operations, model outcome and hashes](v05-recovery-trial.json)

The executor closed the first interactive process after its initial empty-pack
check, before any search/recheck. That aborted receipt and the subsequent
operational restart with zero prior consumed search/recheck budget are preserved.
The successful retrieval/check ran in one subsequent live process. This is one
usability observation, not a matched comparison, a human review or evidence that
false abstentions have generally been resolved.

The natural-PDF script retains the six fixed development probes and the pinned
48-page publisher PDF. It preserves the original five-candidate variants and adds
three variants sharing a 20-candidate pool: plain, source headings and headings
plus page diversity. Raw artifacts include all rankings, pack decisions, coverage,
source/code hashes and timings; CI summaries expose per-query page selections.
These agent-audited page judgments still await human review. A page hit is not
answer accuracy, full premise recall, citation support or reliable abstention.

Default ranked selection, current pack budgets and historical frozen test
families/outcomes are preserved. Optional diversity can displace useful same-page
material and is therefore explicit, inspectable and disabled by default.
