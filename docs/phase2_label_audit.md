# Phase 2 candidate-label source audit

This is an **AI source audit**, not human verification. The owner instructed the
assistant to carry out the review and merge, so all 31 `review_status` values remain
`needs_review`. The Phase 2 human-review gate is still **not passed**. This audit
supports merging the implementation as a provisional pilot at the owner's direction;
it does not convert its retrieval metrics into validated performance claims.

Dataset SHA-256 (LF-normalized):
`cc8ee84a47f4d1930154b2d466e2a56c26739b0fe45ec267f988ddaf7afb5a46`.

## Method

- Rendered and visually inspected every page of the five repository-owned PDF
  families (seven pages total). The two new two-page notes and the original
  Atlas, table, and chart pages were legible and unclipped.
- Compared each proposed answer with its cited page and source text. Recomputed
  the F1 gap (0.86 - 0.75 = 0.11) and cache hit ratio
  (800 / (800 + 200) = 0.80). Compared all three policy rows for the maximum
  cache hit ratio.
- Inspected each entire PDF for the five unanswerable questions. The requested
  sensor mass, Dense latency, failed-request count, packet-loss percentage,
  and cache energy use are absent. The last two source notes explicitly state
  that those measurements are not reported.
- Visually checked the frozen chart's tallest FIFO bar and shortest Priority
  bar. This was label-source inspection only; no frozen-test retrieval was run.
- Ran strict dataset validation against reparsed canonical evidence. Every
  nonvisual gold evidence ID, document version, page index, anchor precision,
  and bounding box resolved. The five frozen-test rows were unchanged during
  the corpus expansion.

## Item-by-item finding

| Query ID | Source check | Finding |
|---|---|---|
| `p2_atlas_rate` | Atlas page 1 text | 20 hertz supported |
| `p2_atlas_path` | Atlas page 1 caption and diagram | Archive supported; caption makes it text-answerable |
| `p2_atlas_filter` | Atlas page 1 text | Filter step supported |
| `p2_atlas_weight` | Entire Atlas page | Sensor mass absent |
| `p2_table_best` | Table page 1, all method rows | Hybrid F1 0.86 is highest |
| `p2_table_dense_recall` | Table page 1, Dense row | Recall 0.80 supported |
| `p2_table_f1_gap` | Table page 1, Hybrid and Lexical rows | Difference 0.11 supported |
| `p2_table_latency` | Entire table page | Dense latency absent |
| `p2_chart_id` | Chart page 1 text | QS-17 supported |
| `p2_chart_budget` | Chart page 1 text | 250 ms supported |
| `p2_chart_tallest` | Chart page 1 bar geometry | FIFO tallest; requires visual evidence |
| `p2_chart_shortest` | Chart page 1 bar geometry | Priority shortest; requires visual evidence |
| `p2_chart_errors` | Entire chart page | Failed-request count absent |
| `p2_retry_protocol` | Checksum page 1 text | CR-42 supported |
| `p2_retry_digest` | Checksum page 1 text | SHA-256 supported |
| `p2_retry_chunk_bytes` | Checksum page 1 text | 4096 bytes supported |
| `p2_retry_ack` | Checksum page 1 text | Recompute digest before acknowledgment supported |
| `p2_retry_formula` | Checksum page 1 equation | Chunk count times payload bytes supported |
| `p2_retry_total` | Checksum page 1 worked example | 12288 payload bytes supported |
| `p2_retry_attempts` | Checksum page 2 text | Three total attempts supported |
| `p2_retry_second_backoff` | Checksum page 2 schedule | Second retry waits 100 ms |
| `p2_retry_loss` | Both checksum pages | Measured packet-loss percentage absent |
| `p2_cache_study_id` | Cache page 1 text | CA-09 supported |
| `p2_cache_capacity` | Cache page 1 text | 64 MiB supported |
| `p2_cache_formula` | Cache page 1 equation | Hits divided by hits plus misses supported |
| `p2_cache_ratio` | Cache page 1 counts and equation | 0.80 supported by calculation |
| `p2_cache_limit` | Cache page 1 admission rule | 8 MiB maximum inferred from “larger than 8 MiB” rejection |
| `p2_cache_eviction` | Cache page 1 text | Eviction on capacity exceedance supported |
| `p2_cache_best_hit` | Cache page 2, all three policy rows | TinyLFU 0.84 highest |
| `p2_cache_lru_latency` | Cache page 2, LRU row | 9 ms supported |
| `p2_cache_energy` | Both cache pages | Energy consumption absent |

No source-supported answer correction was identified. This is a small synthetic
pilot, so label plausibility does not establish generalization, and a human
may still disagree with a question's ambiguity or evidence selection.
