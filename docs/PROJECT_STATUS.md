# Project status

Updated: 2026-11-23. Current release line: **v0.5.0 (alpha)**.

EvidenceRAG is a local, single-user toolkit for technical PDF retrieval and
traceable, checked answers. It can be embedded as Python, called through a JSON
CLI, exposed through local stdio MCP, or used with its bundled agent skill. The
FastAPI inspector and optional live answer adapters remain available.

## Release scope

| Area | Delivered behavior | Evidence |
| --- | --- | --- |
| PDF ingestion | Immutable versions, text/tables, previews, explicit lifecycle/retry | tests/test_lifecycle.py, tests/test_parser.py |
| Retrieval | BM25, optional dense/hybrid/reranking with pinned offline models | reports/reviewed-answer-benchmark/ |
| Grounding | Exact-version citations, source anchors, table checks, optional semantic support and abstention | tests/test_answers.py, tests/test_semantic.py, tests/test_policy.py |
| Agent interfaces | SDK, JSON CLI, setup doctor, connected context, explanations and twenty MCP tools | tests/test_sdk.py, tests/test_mcp_server.py, tests/test_agent_improvements.py |
| Arithmetic | Exact source-backed operations with context/anchors; semantic support remains unassessed | docs/source_calculations.md, tests/test_calculations.py |
| Collections and recipes | Shared scoped BM25, process cache, cross-source checks, percentages and explicit conversions | docs/agent_improvements.md, tests/test_agent_improvements.py |
| Recovery and visibility | Fixed-scope process-local sessions, attempt counters, event receipts, optional page diversity and ranking/coverage traces | docs/recovery_sessions.md, tests/test_recovery.py, tests/test_diversity.py |
| Scan/visual support | Explicit local OCR fallback and provenance-bound page-image handoff; visual interpretations unverified | src/evidence_rag/visual.py, tests/test_agent_improvements.py |
| Skill | Bundled/exportable workflow and tool contract | src/evidence_rag/evidence-rag-agent/ |
| Distribution | Wheel, source archive, standalone skill archive, provenance and checksums | scripts/check_distribution.py, scripts/package_release.py |
| CI/release | Full quality gate, real MCP protocol, fresh wheel installation, ingestion, Qdrant and container; release after successful main CI | .github/workflows/ci.yml, .github/workflows/release.yml |

[Installation](agent_integration.md) and [release notes](releases/v0.5.0.md) are
the current entry points. The Release workflow publishes only the exact commit
whose main-branch CI succeeded. See the GitHub Actions run for that commit's
verification status and the GitHub Release for downloadable artifacts.

## What the evaluation establishes

v0.5.0 adds bounded sessions and retrieval visibility without changing the semantic
verification policy. Default ranked selection is preserved. Optional page diversity
is an inspectable retrieval heuristic; it is not a completeness/support judgment.
The natural-document development probes use an official 48-page NIST PDF;
their agent-audited page labels await human review. Matched three-arm comparison
records are supported, but a human-reviewed comparative accuracy result is not
available. [Workflow scope](agent_improvements.md)

v0.3.0 added exact source arithmetic.
The [delivery record](../reports/source_calculations.md) includes deterministic
positive/incorrect-result controls and a single skill usability trial. It does
not establish an answer-accuracy gain or remove the known false-abstention limit.

The owner reviewed 36 labels across seven owned synthetic PDF families. The
four-method retrieval comparison scores 24 answerable nonvisual development and
validation questions. On the same 11 validation queries, nDCG@5 is BM25 0.797,
dense 0.842, hybrid 0.808 and reranked 0.842. These are small synthetic results.

The preserved one-shot Codex held-out run emitted correct final answers for 2/4
answerable questions, no false answers on 2 unanswerable questions, and supported
both emitted claim/citation links. Its families remain closed to tuning.
[Held-out report](../reports/reserved-final-evaluation.md)

The local verifier audit matched all 11 definite provisional development and
validation judgments; a twelfth uncertain row remains unscored. The independent
agent source audit of a four-question three-arm trial judged every emitted answer
correct, but the skill arm withheld one supported arithmetic synthesis. The trial
has incomplete model/source fingerprinting and is exploratory, not a frozen
benchmark. It establishes no accuracy improvement. [Trial report](../reports/agent-comparison/README.md)

## Boundaries

The release supports one trusted local process on loopback. OCR requires explicit
local language data and may misread scans. Visual handoff requires a capable
calling model; no native chart/diagram support verifier is provided. It has no
shared-host authentication, multi-tenant
service, distributed ingestion, or arbitrary-document accuracy guarantee. These
are outside the release scope. Semantic verification can reject supported drafts.
Missing model weights or support verification are explicit failures/abstentions.
External generation is off by default and requires provider-specific consent.

Broader natural-document validation, human judgments of newly generated claims,
and statistically useful agent comparisons remain research work. Agent audits
must never be represented as owner verification. Existing frozen outputs and
thresholds are preserved.

The application is AGPL-3.0-only; owned fixtures keep CC0 terms. Distributions
retain LICENSE and NOTICE. GitHub Releases is the distribution channel; this
project has not been registered or published on PyPI. Installing a personal
ChatGPT skill requires that client's writable skill-installation surface; the
release's skill archive/export does not silently install one.

## Historical record

[Project history](PROJECT_HISTORY.md) preserves the earlier milestone log,
measurements, decisions and historical pending items. It is not the current
release checklist.
