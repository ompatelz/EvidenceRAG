# Hybrid retrieval checkpoint — provisional comparison

The run uses the same 52 canonical evidence units, 26 development/validation
questions, binary evidence-unit relevance, and K=1/3/5 as E0 and E1. Eleven
answerable nonvisual questions are scored in each split. All 31 dataset labels
remain `needs_review`; these numbers are diagnostics, not validated performance.
Frozen-test questions were neither searched nor used for configuration choice.

Run `python -m evidence_rag.eval.benchmark --config configs/grounded-qa-e2.json`
after installing all extras and caching the pinned MiniLM model as documented in
`docs/dense_baseline.md`. The command saves all four tested configurations and
every raw per-query ranking in `reports/runs/e2-hybrid-validation.json`.
The selection rule is validation nDCG@5, then MRR@5, then configuration order.
All four tied; the chosen configuration is constant 60, prefetch 10 per method,
and final K=5. The real-model run is opt-in; required CI uses deterministic
fusion fixtures and downloads no model.

| Split | Method | Hit@5 | Recall@5 | MRR@5 | nDCG@5 |
|---|---|---:|---:|---:|---:|
| Development | BM25 | 0.909 | 0.909 | 0.818 | 0.842 |
| Development | Dense | 1.000 | 1.000 | 0.894 | 0.921 |
| Development | Hybrid | 1.000 | 1.000 | 0.867 | 0.899 |
| Validation | BM25 | 0.909 | 0.909 | 0.758 | 0.797 |
| Validation | Dense | 0.909 | 0.909 | 0.773 | 0.814 |
| Validation | Hybrid | 0.909 | 0.909 | 0.727 | 0.781 |

First-relevant-rank comparisons across 22 scored questions: versus BM25,
hybrid improves `p2_retry_chunk_bytes`, `p2_retry_total`, and
`p2_cache_limit`, but worsens `p2_atlas_path` and `p2_cache_ratio`. Versus
dense, it improves `p2_cache_eviction`, but worsens `p2_atlas_path`,
`p2_retry_chunk_bytes`, `p2_cache_limit`, and `p2_cache_lru_latency`.
The remaining questions tie at the first relevant rank. `p2_cache_best_hit`
is missed by all three within K=5. Category effects are sparse: these
per-query IDs, categories, and raw rankings are the auditable comparison;
small category averages should not be read as generalization.

On one local Windows cold-process run, hybrid validation mean per-query times
were BM25 0.14 ms, query embedding 6.74 ms, vector search 2.92 ms, fusion
0.05 ms, total 9.86 ms. Saved E0 validation BM25 mean was 0.045 ms; saved
E1 embedding plus vector mean was about 4.60 ms. Those baseline artifacts
were produced in different runs, so this is an exploratory cost comparison,
not a controlled latency benchmark. Build and corpus preparation are excluded
from query timing; peak memory was not measured.

The hybrid run records no retrieval failures. It still returns candidates for
unanswerable questions; retrieval alone does not establish abstention or claim
support. Figure-caption matches are text evidence, not chart understanding.
