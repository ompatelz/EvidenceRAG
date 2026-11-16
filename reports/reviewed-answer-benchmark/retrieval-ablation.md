# Answer benchmark retrieval ablation

These development and validation diagnostics use a shared corpus and evidence-unit relevance. Frozen queries were excluded. Live answers and claim judgments are pending.

| Method | Cohort | Split | Scored / total | Hit@3 | Recall@3 | nDCG@5 |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| E0 BM25 | All candidates | development | 13 / 16 | 0.923 | 0.897 | 0.831 |
| E0 BM25 | All candidates | validation | 11 / 15 | 0.909 | 0.909 | 0.797 |
| E0 BM25 | Owner verified | development | 3 / 4 | 1.000 | 1.000 | 0.877 |
| E0 BM25 | Owner verified | validation | 0 / 0 | — | — | — |
| E1 dense | All candidates | development | 13 / 16 | 1.000 | 1.000 | 0.905 |
| E1 dense | All candidates | validation | 11 / 15 | 0.909 | 0.909 | 0.814 |
| E1 dense | Owner verified | development | 3 / 4 | 1.000 | 1.000 | 0.877 |
| E1 dense | Owner verified | validation | 0 / 0 | — | — | — |
| E2 hybrid | All candidates | development | 13 / 16 | 0.923 | 0.923 | 0.886 |
| E2 hybrid | All candidates | validation | 11 / 15 | 0.909 | 0.909 | 0.781 |
| E2 hybrid | Owner verified | development | 3 / 4 | 1.000 | 1.000 | 0.833 |
| E2 hybrid | Owner verified | validation | 0 / 0 | — | — | — |
| E3 reranker | All candidates | development | 13 / 16 | 1.000 | 1.000 | 0.915 |
| E3 reranker | All candidates | validation | 11 / 15 | 0.909 | 0.909 | 0.814 |
| E3 reranker | Owner verified | development | 3 / 4 | 1.000 | 1.000 | 0.877 |
| E3 reranker | Owner verified | validation | 0 / 0 | — | — | — |

Raw outputs are in [runs](runs/).

Only answerable nonvisual examples enter the scored denominator. The owner-verified subset is a convenience sample. Its figures carry no population-level inference.
The reranker comparison uses E2's fixed candidate settings. It measures rankings only.
