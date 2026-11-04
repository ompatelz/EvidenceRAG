# Evaluation fixtures

This directory contains tiny repository-authored fixtures for testing data contracts. They
are not a benchmark and their synthetic values are not EvidenceRAG performance results.

## Contents

- `fixtures/`: deterministic PDFs owned by this repository.
- `manifests/fixtures.json`: source, permission, hash, version, and redistribution records.
- `eval/fixture_items.jsonl`: small human-verifiable evaluation records.
- `eval/phase2_seed.jsonl`: 13 candidate questions, all pending owner review.

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

The pilot has three repository-authored, CC0-1.0, one-page PDF families: Atlas narrative
and diagram, a structured retrieval table, and a queue-wait bar chart. Source, creation
date, SHA-256, and redistribution terms are in `manifests/fixtures.json`; the generating
source is `scripts/generate_fixtures.py`. No external acquisition or paid API is needed.

The 13 candidate items split 4 development (Atlas), 4 validation (table), and 5 frozen
test (chart). Three are unanswerable (23.1%); two require reading bar heights from the
chart. All 13 have `needs_review` status. They were inspected and proposed by an AI
assistant, so **zero are currently human verified**. The owner must check each source
page, answer, evidence anchor, ambiguity, category, and visual-dependence claim before
changing a status to `verified`. The small synthetic corpus does not cover equations,
multi-page tables, external technical PDFs, or representative production layouts.

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
