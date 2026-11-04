# Evaluation fixtures

This directory contains tiny repository-authored fixtures for testing data contracts. They
are not a benchmark and their synthetic values are not EvidenceRAG performance results.

## Contents

- `fixtures/`: deterministic PDFs owned by this repository.
- `manifests/fixtures.json`: source, permission, hash, version, and redistribution records.
- `eval/fixture_items.jsonl`: small human-verifiable evaluation records.
- `eval/phase2_seed.jsonl`: 31 candidate questions, all pending owner review.
- `eval/REVIEW_PACKET.md`: source-only checklist for direct owner review.

The fixtures are dedicated to the public domain under CC0-1.0 as recorded in
`LICENSE-FIXTURES.txt`. Regenerate and verify them with:

```bash
uv run python scripts/generate_fixtures.py
uv run python scripts/generate_fixtures.py --check
uv run python -m evidence_rag.eval.validate \
  --manifest datasets/manifests/fixtures.json \
  datasets/eval/fixture_items.jsonl
```

Evaluation splits operate at document-family level. Questions from the same document ID
must never cross development, validation, and frozen-test boundaries.

## Phase 2 pilot

The pilot has five repository-authored, CC0-1.0 PDF families: Atlas narrative
and diagram, a structured retrieval table, a queue-wait bar chart, a two-page
checksum/retry note, and a two-page cache-admission note. The new notes add
equations, exact identifiers, numeric facts, table-like policy comparisons,
and multi-page source references. Source, creation date, SHA-256, and
redistribution terms are in `manifests/fixtures.json`; the generating source
is `scripts/generate_fixtures.py`. No paid API is needed.

The 31 candidate items split 13 development (Atlas and checksum/retry), 13
validation (retrieval table and cache admission), and the original 5 frozen
test (chart). Five are unanswerable (16.1%); two require reading bar heights
from the chart. All 31 have `needs_review` status. They were inspected and
proposed by an AI assistant, so **zero are currently human verified**. The
owner can review the linked source pages and proposed evidence in
`eval/REVIEW_PACKET.md`. The corpus still lacks external technical PDFs,
multi-page tables, and representative production layouts.

Visual chart items use a page region with no `EvidenceUnit` ID because the parser emits
the chart's labels and caption but not its bar geometry as a semantic figure. They are
page/region judgments, not evidence-unit judgments; text-only E0/E1 comparisons must
report them separately. The frozen chart family must not be used for implementation,
model choice, or threshold tuning. Its question rows exist only to define the sealed
split; do not run retrieval on them before configuration lock.

Validate source hashes and all parsed evidence references with:

```bash
uv run python scripts/generate_fixtures.py --check
uv run python -m evidence_rag.eval.validate --manifest datasets/manifests/fixtures.json --verify-evidence datasets/eval/phase2_seed.jsonl
```
