# Search baselines — provisional gate report

## Provenance and reproduction

- Dataset SHA-256: `c8139440fc359cc4615727b6933dc7d69afa7b8132c13fa722008b5424e10098`; manifest SHA-256: `fae53809868b44108837cf14f96fbfc220072cb3e62d80b12df0866e9e7622ec`.
- Dataset and source text hashes normalize line endings to LF so Windows and Linux checkouts have the same identity.
- E0 raw run: `reports/reviewed-answer-benchmark/runs/e0.json`; run Git SHA `d375038d10ca1264aed069be6984fbc7b1b526a0`; index `sha256:04957b073c73ce311bf4671e141d7d25768e246a089c0e983dee017158301db6`.
- E0 source SHA-256 `df8cd08b3ba5ee5859f309a002aa6a844025127ec8053cf6545d1a747f90aaa0`; source uncommitted at run: `false`.
- E1 raw run: `reports/reviewed-answer-benchmark/runs/e1.json`; run Git SHA `d375038d10ca1264aed069be6984fbc7b1b526a0`; index `sha256:97577d6709c2154e404e18659f52caf7de1d3f7a663331dcfcf55b66399604c7`; model revision `d13954661f83248295ba75c1ed411eef3b7b936e`.
- E1 source SHA-256 `7deaf66d2db0d675e5fc545d6d289460a39d9c4518b06ac52182ff5d813f2ae2`; source uncommitted at run: `false`.
- Both runs use the same canonical evidence units, exact document versions, query IDs, evidence-unit binary relevance, and K=1/3/5.
- Regenerate E0 through E3 using `python scripts/reviewed_retrieval.py --output-dir reports/generated/answer-benchmark` with the pinned local model cache.
- Timings are exploratory single cold-process observations without warmup; E1 separates query embedding from vector search. They are not latency benchmarks. Peak memory was not measured.

## Dataset and gate

- 36 candidate questions: 31 development/validation queries and 5 frozen-test queries; 4 human verified. 24 answerable nonvisual questions are scored in each run.
- The frozen test was not searched or used for tuning. 32 labels require owner review.
- **Phase 2 gate: NOT PASSED.** The target is 30-50 human-verified questions; this pilot has 36 candidate labels and 4 verified. Broader external document coverage remains untested. A code merge does not complete the human-review gate.

## Aggregate evidence-unit results

| Split | Method | Scored | Hit@1 | Hit@3 | Recall@3 | MRR@3 | nDCG@3 |
|---|---|---:|---:|---:|---:|---:|---:|
| development | E0 | 13 | 0.692 | 0.923 | 0.897 | 0.808 | 0.815 |
| development | E1 | 13 | 0.769 | 1.000 | 1.000 | 0.872 | 0.905 |
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
| multi_page | E0 | 1 | 1.000 | 1.000 |
| multi_page | E1 | 1 | 1.000 | 1.000 |
| narrative_fact | E0 | 4 | 1.000 | 1.000 |
| narrative_fact | E1 | 4 | 0.750 | 1.000 |
| table_calculation | E0 | 1 | 1.000 | 1.000 |
| table_calculation | E1 | 1 | 1.000 | 1.000 |
| table_lookup | E0 | 6 | 0.333 | 0.833 |
| table_lookup | E1 | 6 | 0.500 | 0.833 |
| unanswerable | E0 | 0 | — | — |
| unanswerable | E1 | 0 | — | — |
| visual | E0 | 0 | — | — |
| visual | E1 | 0 | — | — |

## Controlled comparison and failures

- E0 wins on first relevant rank: p2_cache_ratio, p2_cache_eviction.
- E1 wins on first relevant rank: p2_retry_chunk_bytes, p2_retry_total, p2_cache_limit, p2_cache_lru_latency.
- Both miss relevant evidence within K=5: p2_cache_best_hit.
- `p2_atlas_path` has its labeled relevant unit at rank 2 in E0 and 2 in E1; both miss at K=1 (taxonomy d).
- Unanswerable questions still return candidates; this retrieval-only benchmark cannot measure abstention (taxonomy g).
- No parser/OCR/layout (a) or indexing/chunking (b) failure can be established from these 31 development/validation queries. Relevant-source misses by K=5 (c): 1. Interpretation (e), citation support (f), and security (h) are outside this retrieval evaluation; document/version isolation has separate tests.
- Frozen-family chart questions are outside this run. Pending labels could change after source-page review.
- Recorded query failures: E0=0, E1=0; any future partial failures are saved per query and excluded from scored denominators.

## Limits

These figures are diagnostics from repository-authored synthetic PDFs, not validated generalization or a portfolio improvement claim. The comparison lists only observed wins and misses; absent failure categories are not illustrated with invented examples.
