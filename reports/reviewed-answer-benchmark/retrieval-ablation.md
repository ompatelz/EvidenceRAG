# Answer benchmark retrieval ablation

These development and validation diagnostics use a shared corpus and evidence-unit relevance. Frozen queries were excluded. Live answers and claim judgments are pending.

| Method | Cohort | Split | Scored / total | Hit@3 | Recall@3 | nDCG@5 |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| E0 BM25 | Owner verified | development | 13 / 16 | 0.923 | 0.897 | 0.831 |
| E0 BM25 | Owner verified | validation | 11 / 15 | 0.909 | 0.909 | 0.797 |
| E1 dense | Owner verified | development | 13 / 16 | 1.000 | 1.000 | 0.905 |
| E1 dense | Owner verified | validation | 11 / 15 | 0.909 | 0.909 | 0.842 |
| E2 hybrid | Owner verified | development | 13 / 16 | 0.923 | 0.923 | 0.886 |
| E2 hybrid | Owner verified | validation | 11 / 15 | 0.909 | 0.909 | 0.808 |
| E3 reranker | Owner verified | development | 13 / 16 | 1.000 | 1.000 | 0.915 |
| E3 reranker | Owner verified | validation | 11 / 15 | 0.909 | 0.909 | 0.842 |

Raw outputs are in [runs](runs/).

Only answerable nonvisual examples enter the scored denominator. The synthetic sample supports descriptive figures for these families.
The reranker comparison uses E2's fixed candidate settings. It measures rankings only.
