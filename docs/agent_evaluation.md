# Evaluate the agent interfaces

## Purpose

Separate improvements from retrieval tools, agent instructions, and verifier
changes. Do not infer an improvement from adding an MCP server or skill.

Run three arms on identical eligible development/validation queries:

| Arm | Agent context |
| --- | --- |
| baseline | Existing agent/document retrieval workflow, explicitly recorded |
| tools_only | EvidenceRAG tools and their schemas, without the companion skill |
| tools_and_skill | The same tools plus the exact bundled skill revision |

Fix agent/model revision, temperature/seed when supported, source versions,
retrieval mode/configuration, question set and generation limits. Give each arm
the same overall time, token and tool-call budget. Record any unavoidable client
differences. Use isolated conversations and separate artifact directories; do not
let an arm see another arm's responses, labels or reviewer judgments.

## Eligible sources

Use development and validation rows in datasets/eval/reviewed_labels.jsonl.
Never load frozen/test rows into the agent session. Preserve historical and
reserved final-test documents, labels, raw outputs and thresholds. Findings
already seen in final-test reports must not become targeted tuning examples.
New development examples need independent source construction and review.

## Capture each outcome

For every question save the raw response, tool calls/results, retrieved IDs,
final answer/abstention, claim citations, support signals, timings, token use
and observed cost when available. Record corpus/dataset/config/skill hashes,
Git SHA, model identifiers and the complete invocation. Record tool failures
separately from intentional abstention.

Have a reviewer inspect source pages for answer correctness, per-claim support,
citation precision and missing qualifications. Owner-approved benchmark labels
are not owner-approved judgments of a new generated answer. Mark agent-only
source audits separately from human judgments. Blind the reviewer to the arm
where practical.

## Metrics and acceptance

Report numerator and denominator for correct answers, answerable coverage,
false abstentions, unsupported answers on unanswerable questions, supported
claim/citation links, and operational failures. Also report latency, token cost
and tool-call counts. Break out tables, exact facts, cross-page reasoning,
negative statements and unanswerable questions where labels support it.

Before the run, predeclare that higher coverage is acceptable only if unsupported
answers do not increase on the matched cohort. Report uncertainty and the small
synthetic cohort; zero observed errors is not zero population risk.

## Verifier diagnosis

First run the existing local semantic audit on its development/validation cases.
Its expected judgments are provisional and require review. A source-valid
citation can accompany an unsupported draft; retrieval Hit@K alone is not proof
of a verifier failure. Distinguish missing pack context, truncation, an invalid
draft, missing model files and a genuine support-assessment error.

Do not relax grounding-v1 or alter thresholds in this interface change. A later
verifier change needs reviewed independent development cases, before/after raw
outcomes with retrieval and drafts fixed, negative controls, and separate
validation. Retain historical raw outputs.

## Current status

The [exploratory three-arm trial](../reports/agent-comparison/README.md) records
four actual development questions, raw operations and independent agent source
judgments. It found no quality gain, and its model/source fingerprinting and
sample size do not meet the stronger protocol above. Deterministic tests use
explicit doubles for semantic outcomes and establish integration behavior only.
No provider key or paid generation is required for installation or CI.
