# Agent workflows in v0.4.0

EvidenceRAG retrieves and checks sources; the caller's model reasons and writes.
This release adds recovery explanations, connected context, collection search,
calculation recipes, optional OCR, visual handoff, setup checks and evaluation
records. It does not change grounding-v1 thresholds or establish an accuracy gain.

## Setup and diagnostics

Run `evidence-rag doctor` (or `rag.doctor()` / MCP `doctor`). Checks are offline:
core and optional dependencies, a temporary storage write, pinned verifier files
and local OCR language data. `ready` means core storage/dependencies are present;
warnings may still prevent optional features. A file-presence check does not prove
that an inference session will load successfully. Doctor never downloads models.

## Context and recovery

`rag.context(document, evidence_id, radius=1)` returns the seed first, explicit
caption/table relationships, the nearest preceding heading, and reading-order
neighbors. Radius is 0–2; neighbors can cross a page boundary. This is structural
context expansion, not inferred semantic links or guaranteed evidence completeness.
The five-item, 1200-character/item, 4000-character pack limits still apply. Read
excluded IDs and truncation; use explicit page/evidence fetches for more context.

`rag.explain_check(document, question, evidence_ids, draft)` preserves the existing
check result and adds diagnostics per claim. These describe observed rule/model
signals, citations and next actions. The checker cannot know which unstated
qualifier would fix a claim, so recovery guidance does not fabricate one. Some
claims may remain unassessed after an earlier rule/citation failure.

The companion workflow maintains one budget across all claims/documents: at most
two additional searches and one recheck. It requires a concrete new premise or
drafting correction before revision, and stops on a still-withheld result.
`RecoveryBudget` is an immutable caller-owned SDK ledger. This is workflow
accounting, not server-enforced session state; calling tools directly does not
create an autonomous recovery loop or resettable hidden session.

CLI: `context --document-id ID --sha256 SHA --evidence-id EV`, and
`explain --document-id ID --sha256 SHA --question Q --evidence-id EV --draft FILE`.
MCP equivalents: `fetch_connected_evidence` and `explain_check`.

## Collections and conflicting sources

```python
from evidence_rag.sdk import CollectionSearchRequest

result = rag.search_collection(CollectionSearchRequest(
    documents=(first_document, second_document),
    question="Which retry timeout is documented?",
    contextual_indexing=True,
))
```

Select 1–20 explicit document/SHA pairs. All must be ready; invalid versions fail
the request instead of silently disappearing. The total evidence count is bounded
by `max_evidence_units`. Shared BM25 provides comparable collection ranks. Section
headings can enrich the index; returned text and citations remain canonical.
Dense/hybrid collection retrieval is not implemented in this release.

The engine caches one BM25 index per trusted process using a hash of its complete
indexed evidence. Repeated searches reuse it; changed sources/context options
invalidate it. Re-ingesting an unchanged ready PDF reuses existing artifacts.
The lifecycle/status API exposes stages and timings. This is version reuse and
process caching, not incremental extraction of unchanged pages inside a changed PDF.

Use `check_collection(CollectionDraftRequest(...))` to check scoped drafts against
each source independently. Every source entry contains `document`, `evidence_ids`
and `draft`; the request also contains `question`. Reuse identical claim text when
comparing the same proposition across versions. `conflicting_claim_texts` surfaces
observed supported/contradicted signals, not a comprehensive conflict audit.
Neither search nor checking guesses publication dates or silently selects the
latest source. Ingestion timestamps are not source publication dates.

CLI: `search-collection --request FILE` / `check-collection --request FILE`.
MCP: `search_collection(request=...)` / `check_collection(request=...)`.

## Exact calculation recipes

Use `rag.calculate_recipe(document, CalculationRecipe(...))`, CLI `recipe
--document-id ID --sha256 SHA --calculation FILE`, or MCP `calculate_recipe`.
Recipes have 1–8 ordered steps; inputs are existing source selectors or references
to earlier steps. Constants/code/free numeric inputs and forward references are
rejected. The final result and every step are exact rational strings.

```json
{
  "steps": [
    {"operation":"convert", "inputs":[{"kind":"text","evidence_id":"EV_HITS","unit":"hits"}], "target_unit":"count"},
    {"operation":"convert", "inputs":[{"kind":"text","evidence_id":"EV_MISSES","unit":"misses"}], "target_unit":"count"},
    {"operation":"add", "inputs":[{"kind":"step","index":0},{"kind":"step","index":1}]},
    {"operation":"percentage", "inputs":[{"kind":"step","index":0},{"kind":"step","index":2}]}
  ]
}
```

Replace IDs with actual returned sources. Read contexts to establish that the
counts belong to the same population and interval before interpreting this ratio.
Count normalization records the original categories; hits cannot become misses.

| Operation | Definition |
| --- | --- |
| add / subtract / multiply / divide | First input operator second input |
| percentage | First / second × 100; identical input units required |
| percent_change | (Second − first) / first × 100; identical input units required |
| convert | One input, explicit target_unit; receipt records exact conversion factor |

Conversions are case-sensitive, linear and explicit: ms/s/seconds/minutes/hours/days;
mm/cm/m/km; g/kg; B/KB/MB/KiB/MiB; hits/misses/requests to count. No temperature,
currency, arbitrary compound-unit or inferred category conversions. Add/subtract
also require identical units; convert first. Zero denominators and oversized
intermediates fail explicitly. Version scope, ambiguous extraction and source
truncation checks remain in force. `arithmetic_verified` always leaves
`claim_support=not_assessed`; recipes never override an abstention.

## Scans and visual questions

OCR uses PyMuPDF's local Tesseract integration. Install language data yourself and
set `EVIDENCERAG_OCR_ENABLED=true`, `EVIDENCERAG_OCR_TESSDATA=/path/to/tessdata`, and
optionally `EVIDENCERAG_OCR_LANGUAGE=eng`. Only pages without native text receive
full-page OCR. Missing data, OCR failure and pixel-budget violations are explicit
failures. No download occurs. OCR profiles appear in parser representation metadata.
Use a fresh artifact root when changing the extraction profile; a ready version
is not silently reparsed. OCR text can be wrong, and OCR does not interpret charts.

For a chart/diagram, explicitly request MCP `fetch_visual_page`, CLI `visual
--document-id ID --sha256 SHA --page-index N`, or Python
`evidence_rag.visual.page_image(rag, document, N)`. A bounded PNG packet identifies
the exact page image by SHA-256. A visual-capable calling agent can interpret it
under the user's data-sharing authorization. `VisualObservation` and
`check_observation` bind that observation to the actual image, model and limitations.
They check provenance only. No built-in vision model is invoked, and the text/NLI
checker cannot verify visual observations. Unavailable visual capability requires
an explicit unsupported result. [Official OCR API](https://pymupdf.readthedocs.io/en/latest/page.html#Page.get_textpage_ocr)

## Inspector and evaluation

Expand a claim's decision to inspect its rule/model signals and source links.
The inspector can import a SDK/CLI calculation receipt (JSON up to 64 KiB), show
its steps and open the original sources. Imported receipts must match the loaded
PDF version and are clearly marked as untrusted, not recomputed by the browser.

`scripts/natural_document_evaluation.py --download --output FILE` explicitly
downloads the official 48-page NIST AI RMF 1.0 PDF and records its SHA-256,
canonical packs, page rankings and search times for six development probes with
and without source headings. Use `--pdf FILE` for an existing copy and
`--expected-sha256 SHA` to select a different explicitly frozen source fingerprint.
The default is the recorded publisher PDF SHA-256 in
[the development manifest](../datasets/manifests/natural-development.json).
The CI record is an artifact;
page relevance labels are agent audits pending human review. No generated-answer
accuracy or quality improvement follows from this retrieval smoke.

For independent direct/tools/tools-plus-skill comparisons, record `AgentTrial`
JSONL and run `scripts/summarize_agent_comparison.py INPUT --output FILE`.
Records require matched model revision, configuration/corpus hashes and code
commit per question/repeat; the skill arm also needs the skill hash. Run multiple
repeats in isolated contexts with equal budgets. Only explicitly human-reviewed
judgments enter quality counts. Missing token/cost telemetry stays unobserved.
Historical frozen test families and outcomes remain untouched.
