# Phase 2 search baselines — provisional gate report

## Provenance and reproduction

- Dataset SHA-256: `77c6e1750a3841c346406c7aca449b11e727963e33531efeda1ac8d917257fe3`; manifest SHA-256: `c78fe687d261a1a1200a08aa94c778045c29f7ea0b4eaabf435f6a593403e757`.
- Dataset and source text hashes normalize line endings to LF so Windows and Linux checkouts have the same identity.
- E0 raw run: `reports/runs/e0-phase2-pilot.json`; run Git SHA `defdfe2a9b5db2a83131234cdb0ab0b22a293d5b`; index `sha256:4924fb23fcbfa8df0d9470bf8d84bb998313000db59f9748e279fcccf983dda8`.
- E0 source SHA-256 `5affd19b6421d5a9569a3dfb336ba4d2db810e3dedc0d9867ad89e0487deb085`; source uncommitted at run: `true`.
- E1 raw run: `reports/runs/e1-phase2-pilot.json`; run Git SHA `defdfe2a9b5db2a83131234cdb0ab0b22a293d5b`; index `sha256:e710416e100a4c4af984ea20c130c5d6f1e23766f431968c7c4fe6d5b8f8686d`; model revision `d13954661f83248295ba75c1ed411eef3b7b936e`.
- E1 source SHA-256 `c9af8fcf7e8f30bfba81d95e35cc78ed2c3442fec0b0879e1901f641262e61dc`; source uncommitted at run: `true`.
- Both runs use the same canonical evidence units, exact document versions, query IDs, evidence-unit binary relevance, and K=1/3/5.
- Run `uv run python -m evidence_rag.eval.benchmark --config configs/phase2-e0.json`.
- With the pinned model cached, run `uv run python -m evidence_rag.eval.benchmark --config configs/phase2-e1.json`. For the first download, set `download_model` to `true` in a copy of that config; ordinary CI never downloads model weights.
- Generate this report with `uv run python -m evidence_rag.eval.report`.
- Timings are exploratory single cold-process observations without warmup; E1 separates query embedding from vector search. They are not latency benchmarks. Peak memory was not measured.

## Dataset and gate

- 13 candidate questions: 8 development/validation queries and 5 frozen-test queries; 0 human verified. 6 answerable nonvisual questions are scored in each run.
- The frozen test was not searched or used for tuning. 13 labels require owner review.
- **Phase 2 gate: NOT PASSED.** The target is 30-50 human-verified questions; this pilot has 13 candidate labels and 0 verified. It also lacks equations and broader external document coverage. The PR remains draft.

## Aggregate evidence-unit results

| Split | Method | Scored | Hit@1 | Hit@3 | Recall@3 | MRR@3 | nDCG@3 |
|---|---|---:|---:|---:|---:|---:|---:|
| development | E0 | 3 | 0.667 | 1.000 | 1.000 | 0.833 | 0.877 |
| development | E1 | 3 | 0.667 | 1.000 | 1.000 | 0.833 | 0.877 |
| validation | E0 | 3 | 0.667 | 1.000 | 1.000 | 0.833 | 0.877 |
| validation | E1 | 3 | 0.667 | 1.000 | 1.000 | 0.833 | 0.877 |

## Per-category diagnostics

Categories with no scored answerable nonvisual questions have no retrieval metric.

| Category | Method | Scored | Hit@1 | Hit@3 |
|---|---|---:|---:|---:|
| diagram_interpretation | E0 | 1 | 0.000 | 1.000 |
| diagram_interpretation | E1 | 1 | 0.000 | 1.000 |
| narrative_fact | E0 | 2 | 1.000 | 1.000 |
| narrative_fact | E1 | 2 | 1.000 | 1.000 |
| table_calculation | E0 | 1 | 1.000 | 1.000 |
| table_calculation | E1 | 1 | 1.000 | 1.000 |
| table_lookup | E0 | 2 | 0.500 | 1.000 |
| table_lookup | E1 | 2 | 0.500 | 1.000 |
| unanswerable | E0 | 0 | — | — |
| unanswerable | E1 | 0 | — | — |

## Controlled comparison and failures

- E0 wins on first relevant rank: none observed.
- E1 wins on first relevant rank: none observed.
- Both miss relevant evidence within K=5: none observed.
- `p2_atlas_path` places its provisional relevant unit at rank 2 in both runs. At K=1 this is a ranking failure (taxonomy d); both retrieve it by K=3.
- Unanswerable questions still return candidates; this retrieval-only benchmark cannot measure abstention (taxonomy g).
- No parser/OCR/layout (a) or indexing/chunking (b) failure can be established from these eight queries. No relevant-source miss by K=5 (c) is observed. Interpretation (e), citation support (f), and security (h) are outside this retrieval evaluation; document/version isolation has separate tests.
- Visual chart questions stay in the frozen family. Their parsing and annotation quality cannot be inferred from this run. All provisional labels could change after source-page review.
- Recorded query failures: E0=0, E1=0; any future partial failures are saved per query and excluded from scored denominators.

## Limits

These figures are diagnostics from a small repository-authored synthetic pilot, not validated generalization or a portfolio improvement claim. There are no observed E0 wins, E1 wins, or joint misses at K=5 to illustrate; creating such examples would misrepresent the saved runs.
