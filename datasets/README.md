# Evaluation fixtures

This directory contains tiny repository-authored fixtures for testing data contracts. They
are not a benchmark and their synthetic values are not EvidenceRAG performance results.

## Contents

- `fixtures/`: deterministic PDFs owned by this repository.
- `manifests/fixtures.json`: source, permission, hash, version, and redistribution records.
- `eval/fixture_items.jsonl`: small human-verifiable evaluation records.

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
