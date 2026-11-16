# ADR-0010 · Claim support and abstention

Status · Implemented for the local pilot, 2026-11-16. Human evaluation review pending.

The structured answer contract covers the displayed text with ordered,
cited claims. Validate scope, exact version, pack membership, and source
resolution before inspecting claim meaning. Reuse the source-page and region
resolver in ADR-0005 so answer and inspector anchors follow the same rules.

Use exact arithmetic over unambiguous cited table cells where possible.
Use a separately trained, pinned and optional local NLI model for prose,
with bounded inference and explicit truncation, failure, and conflict
states. Keep semantic labels and citation validity in separate API fields.
The decision policy uses pack availability, the table rule, and the model
verdict and margin in that order. Its margin is provisionally selected from
scripted validation signals. The opt-in policy protects the existing
fixture demonstration from changes to its default requirements.

ADR-0009's visual no-go applies. The verifier consumes extracted text and
tables. A question flagged as requiring pixel inspection receives a
modality outcome. No visual capability is inferred from a resolvable crop.

The evaluation compares fixed retrieval and draft outputs with support and
policy off and on. The shared provenance gate applies to both arms. Document
versions, retrieval ranks, drafts, decisions, human-review status, and raw
timings are retained with the run. An emitted correct string can still carry
an irrelevant citation, so the report has separate support, page, and region
metrics. See [the controlled comparison](../../reports/ablation_study.md).

Runtime rollback is to turn the abstention policy off and disable the optional
verifier. Reverting the feature commits in reverse order also removes the
deterministic checks and restores the old generator response contract. Local
source PDFs, evidence artifacts, and previews require no migration.
