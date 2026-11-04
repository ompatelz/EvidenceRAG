# Phase 2 search baselines — provisional gate report

## Provenance and reproduction

- Dataset SHA-256: `cc8ee84a47f4d1930154b2d466e2a56c26739b0fe45ec267f988ddaf7afb5a46`; manifest SHA-256: `282ec1b50522c1969f0f3a553421f887de8f2c14624ce5bd6ff2e444412cc433`.
- Dataset and source text hashes normalize line endings to LF so Windows and Linux checkouts have the same identity.
- E0 raw run: `reports/runs/e0-phase2-pilot.json`; run Git SHA `15edd0612daa15a29f90a04fcf54de4f92cc56f5`; index `sha256:b060bce67d8752ae0fc16df0b33c3447c0dc1c41e586cc0a8581e0786e7aa542`.
- E0 source SHA-256 `5affd19b6421d5a9569a3dfb336ba4d2db810e3dedc0d9867ad89e0487deb085`; source uncommitted at run: `false`.
- E1 raw run: `reports/runs/e1-phase2-pilot.json`; run Git SHA `15edd0612daa15a29f90a04fcf54de4f92cc56f5`; index `sha256:c75946feda3b91910063ec9aacb2b14d5639ecfd22ccb4a0851b27b88902124f`; model revision `d13954661f83248295ba75c1ed411eef3b7b936e`.
- E1 source SHA-256 `c9af8fcf7e8f30bfba81d95e35cc78ed2c3442fec0b0879e1901f641262e61dc`; source uncommitted at run: `false`.
- Both runs use the same canonical evidence units, exact document versions, query IDs, evidence-unit binary relevance, and K=1/3/5.
- Run `uv run python -m evidence_rag.eval.benchmark --config configs/phase2-e0.json`.
- With the pinned model cached, run `uv run python -m evidence_rag.eval.benchmark --config configs/phase2-e1.json`. For the first download, set `download_model` to `true` in a copy of that config; ordinary CI never downloads model weights.
- Generate this report with `uv run python -m evidence_rag.eval.report`.
- Timings are exploratory single cold-process observations without warmup; E1 separates query embedding from vector search. They are not latency benchmarks. Peak memory was not measured.

## Dataset and gate

- 31 candidate questions: 26 development/validation queries and 5 frozen-test queries; 0 human verified. 22 answerable nonvisual questions are scored in each run.
- The frozen test was not searched or used for tuning. 31 labels require owner review.
- **Phase 2 gate: NOT PASSED.** The target is 30-50 human-verified questions; this pilot has 31 candidate labels and 0 verified. Broader external document coverage remains untested. The PR remains draft.

## Aggregate evidence-unit results

| Split | Method | Scored | Hit@1 | Hit@3 | Recall@3 | MRR@3 | nDCG@3 |
|---|---|---:|---:|---:|---:|---:|---:|
| development | E0 | 11 | 0.727 | 0.909 | 0.909 | 0.818 | 0.842 |
| development | E1 | 11 | 0.818 | 1.000 | 1.000 | 0.894 | 0.921 |
| validation | E0 | 11 | 0.636 | 0.909 | 0.909 | 0.758 | 0.797 |
| validation | E1 | 11 | 0.636 | 0.909 | 0.909 | 0.773 | 0.814 |

## Per-category diagnostics

Categories with no scored answerable nonvisual questions have no retrieval metric.

| Category | Method | Scored | Hit@1 | Hit@3 |
|---|---|---:|---:|---:|
| diagram_interpretation | E0 | 1 | 0.000 | 1.000 |
| diagram_interpretation | E1 | 1 | 0.000 | 1.000 |
| equation_calculation | E0 | 2 | 0.500 | 1.000 |
| equation_calculation | E1 | 2 | 0.500 | 1.000 |
| equation_lookup | E0 | 2 | 1.000 | 1.000 |
| equation_lookup | E1 | 2 | 1.000 | 1.000 |
| exact_identifier | E0 | 3 | 1.000 | 1.000 |
| exact_identifier | E1 | 3 | 1.000 | 1.000 |
| exact_number | E0 | 4 | 0.500 | 0.750 |
| exact_number | E1 | 4 | 0.750 | 1.000 |
| narrative_fact | E0 | 4 | 1.000 | 1.000 |
| narrative_fact | E1 | 4 | 0.750 | 1.000 |
| table_calculation | E0 | 1 | 1.000 | 1.000 |
| table_calculation | E1 | 1 | 1.000 | 1.000 |
| table_lookup | E0 | 5 | 0.400 | 0.800 |
| table_lookup | E1 | 5 | 0.600 | 0.800 |
| unanswerable | E0 | 0 | — | — |
| unanswerable | E1 | 0 | — | — |

## Controlled comparison and failures

- E0 wins on first relevant rank: p2_cache_ratio, p2_cache_eviction.
- E1 wins on first relevant rank: p2_retry_chunk_bytes, p2_retry_total, p2_cache_limit, p2_cache_lru_latency.
- Both miss relevant evidence within K=5: p2_cache_best_hit.
- `p2_atlas_path` has its provisional relevant unit at rank 2 in E0 and 2 in E1; both miss at K=1 (taxonomy d).
- Unanswerable questions still return candidates; this retrieval-only benchmark cannot measure abstention (taxonomy g).
- No parser/OCR/layout (a) or indexing/chunking (b) failure can be established from these 26 development/validation queries. Relevant-source misses by K=5 (c): 1. Interpretation (e), citation support (f), and security (h) are outside this retrieval evaluation; document/version isolation has separate tests.
- Visual chart questions stay in the frozen family. Their parsing and annotation quality cannot be inferred from this run. All provisional labels could change after source-page review.
- Recorded query failures: E0=0, E1=0; any future partial failures are saved per query and excluded from scored denominators.

## Limits

These figures are diagnostics from repository-authored synthetic PDFs, not validated generalization or a portfolio improvement claim. The comparison lists only observed wins and misses; absent failure categories are not illustrated with invented examples.
