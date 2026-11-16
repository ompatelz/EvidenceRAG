# Owner source review guide

Open the linked source at the indicated page. For each ID, return **confirm** or **correct** with the replacement answerability, answer, page/region, category, or visual-dependence flag as applicable. For full-document checks, confirm the requested fact is absent. The [review packet](REVIEW_PACKET.md) has evidence IDs and notes fields. The [decision ledger](owner_decisions.json) records completed decisions. Review of the frozen source labels is for recordkeeping only. The prior frozen run stays closed.

Coordinates are normalized `x0, y0, x1, y1` from the top left, rounded for navigation.

## Development

| ID and question | Proposal | Source and decision |
| --- | --- | --- |
| `p2_atlas_rate`<br>What is the calibration sampling rate of the Atlas sensor? | Answerable — 20 hertz | [Atlas Sensor Note](../fixtures/atlas-narrative.pdf), p. 1, region `0.09, 0.12, 0.53, 0.14`. Confirm 20 hertz applies during calibration. |
| `p2_atlas_path`<br>Which stage follows the filter in the Atlas process flow? | Answerable — Archive | [Atlas Sensor Note](../fixtures/atlas-narrative.pdf), p. 1, region `0.11, 0.33, 0.54, 0.35`. Confirm Archive follows Filter and the caption alone supports it. |
| `p2_atlas_filter`<br>What happens to each Atlas sample before it is archived? | Answerable — It passes through a filter. | [Atlas Sensor Note](../fixtures/atlas-narrative.pdf), p. 1, region `0.09, 0.14, 0.50, 0.16`. Confirm filtering happens before archival. |
| `p2_atlas_weight`<br>What is the mass of the Atlas sensor? | Unanswerable | [Atlas Sensor Note](../fixtures/atlas-narrative.pdf), entire PDF. Check the full note for mass or weight. |
| `p2_retry_protocol`<br>Which protocol ID names the chunk-transfer experiment? | Answerable — CR-42 | [Checksum and Retry Protocol Note](../fixtures/checksum-retry.pdf), p. 1, region `0.09, 0.17, 0.59, 0.18`. Confirm CR-42 identifies the experiment. |
| `p2_retry_digest`<br>Which digest algorithm does each chunk carry? | Answerable — SHA-256 | [Checksum and Retry Protocol Note](../fixtures/checksum-retry.pdf), p. 1, region `0.09, 0.20, 0.55, 0.21`. Confirm SHA-256 is the per-chunk digest. |
| `p2_retry_chunk_bytes`<br>What is the chunk payload size in bytes? | Answerable — 4096 bytes | [Checksum and Retry Protocol Note](../fixtures/checksum-retry.pdf), p. 1, region `0.09, 0.20, 0.55, 0.21`. Confirm 4096 bytes is payload size. |
| `p2_retry_ack`<br>What does the receiver do before acknowledging a chunk? | Answerable — It recomputes the digest. | [Checksum and Retry Protocol Note](../fixtures/checksum-retry.pdf), p. 1, region `0.09, 0.23, 0.57, 0.25`. Confirm recomputation takes place before acknowledgement. |
| `p2_retry_formula`<br>How does Equation 1 calculate total payload bytes? | Answerable — Chunk count multiplied by chunk payload bytes. | [Checksum and Retry Protocol Note](../fixtures/checksum-retry.pdf), p. 1, region `0.09, 0.29, 0.55, 0.31`. Confirm chunk count multiplied by chunk payload bytes. |
| `p2_retry_total`<br>For three chunks, how many payload bytes are sent without headers? | Answerable — 12288 bytes | [Checksum and Retry Protocol Note](../fixtures/checksum-retry.pdf), p. 1, region `0.09, 0.32, 0.51, 0.34`. Confirm 3 × 4096 = 12,288 payload bytes, with headers excluded. |
| `p2_retry_attempts`<br>How many attempts per chunk are allowed including the initial send? | Answerable — 3 attempts | [Checksum and Retry Protocol Note](../fixtures/checksum-retry.pdf), p. 2, region `0.09, 0.17, 0.55, 0.18`. Confirm the initial send is included in the three attempts. |
| `p2_retry_second_backoff`<br>How long is the wait before the second retry? | Answerable — 100 ms | [Checksum and Retry Protocol Note](../fixtures/checksum-retry.pdf), p. 2, region `0.09, 0.36, 0.36, 0.37`. Confirm attempt 3 is the second retry and waits 100 ms. |
| `p2_retry_loss`<br>What measured packet-loss percentage does the experiment report? | Unanswerable | [Checksum and Retry Protocol Note](../fixtures/checksum-retry.pdf), p. 2, final note, and entire PDF. Confirm the note gives no measured packet-loss percentage. |

## Validation

| ID and question | Proposal | Source and decision |
| --- | --- | --- |
| `p2_table_best`<br>Which retrieval method has the highest F1 in Table 1? | Answerable — Hybrid, 0.86 | [Retrieval Baseline Fixture](../fixtures/retrieval-table.pdf), p. 1, region `0.12, 0.20, 0.87, 0.37`. Confirm Hybrid is highest and its F1 is 0.86. |
| `p2_table_dense_recall`<br>What recall does the Dense row report? | Answerable — 0.80 | [Retrieval Baseline Fixture](../fixtures/retrieval-table.pdf), p. 1, region `0.12, 0.20, 0.87, 0.37`. Confirm 0.80 comes from the Dense Recall cell. |
| `p2_table_f1_gap`<br>How many points higher is Hybrid F1 than Lexical F1? | Answerable — 0.11 | [Retrieval Baseline Fixture](../fixtures/retrieval-table.pdf), p. 1, region `0.12, 0.20, 0.87, 0.37`. Confirm 0.86 − 0.75 = 0.11 on the F1 scale and whether the word “points” is clear. |
| `p2_table_latency`<br>What is the Dense method's latency in milliseconds? | Unanswerable | [Retrieval Baseline Fixture](../fixtures/retrieval-table.pdf), entire PDF. Check the full fixture for Dense latency in ms. |
| `p2_cache_study_id`<br>What study ID identifies the cache experiment? | Answerable — CA-09 | [Cache Admission Study Note](../fixtures/cache-admission.pdf), p. 1, region `0.09, 0.17, 0.51, 0.18`. Confirm CA-09 is the study ID. |
| `p2_cache_capacity`<br>What is the cache capacity? | Answerable — 64 MiB | [Cache Admission Study Note](../fixtures/cache-admission.pdf), p. 1, region `0.09, 0.20, 0.31, 0.21`. Confirm the capacity is 64 MiB. |
| `p2_cache_formula`<br>What equation defines hit ratio in the study? | Answerable — hits / (hits + misses) | [Cache Admission Study Note](../fixtures/cache-admission.pdf), p. 1, region `0.09, 0.26, 0.40, 0.28`. Confirm hits divided by the sum of hits and misses. |
| `p2_cache_ratio`<br>What hit ratio follows from 800 hits and 200 misses? | Answerable — 0.80 | [Cache Admission Study Note](../fixtures/cache-admission.pdf), p. 1, region `0.09, 0.23, 0.52, 0.25`; p. 1, region `0.09, 0.26, 0.40, 0.28`. Confirm 800 / (800 + 200) = 0.80. Decide whether the adjacent line giving 0.80 also counts as evidence. |
| `p2_cache_limit`<br>What is the largest object size permitted by admission? | Answerable — 8 MiB | [Cache Admission Study Note](../fixtures/cache-admission.pdf), p. 1, region `0.09, 0.32, 0.43, 0.34`. Confirm 8 MiB is inclusive. |
| `p2_cache_eviction`<br>When does the cache evict an object? | Answerable — When admission would exceed capacity. | [Cache Admission Study Note](../fixtures/cache-admission.pdf), p. 1, region `0.09, 0.36, 0.56, 0.37`. Confirm eviction happens when admitting an object would exceed capacity. |
| `p2_cache_best_hit`<br>Which policy has the highest synthetic hit ratio? | Answerable — TinyLFU at 0.84 | [Cache Admission Study Note](../fixtures/cache-admission.pdf), p. 2, region `0.09, 0.20, 0.23, 0.21`; p. 2, region `0.09, 0.23, 0.21, 0.25`; p. 2, region `0.09, 0.26, 0.25, 0.28`. Compare all three hit-ratio cells and confirm TinyLFU at 0.84. |
| `p2_cache_lru_latency`<br>What median lookup latency is listed for LRU? | Answerable — 9 ms | [Cache Admission Study Note](../fixtures/cache-admission.pdf), p. 2, region `0.09, 0.23, 0.21, 0.25`. Confirm 9 ms is median lookup latency on the LRU row. |
| `p2_cache_energy`<br>How much energy did the cache experiment consume? | Unanswerable | [Cache Admission Study Note](../fixtures/cache-admission.pdf), p. 2, final note, and entire PDF. Confirm the note says energy was not measured and gives no value. |

## Frozen source record

| ID and question | Proposal | Source and decision |
| --- | --- | --- |
| `p2_chart_id`<br>What is the queue experiment identifier? | Answerable — QS-17 | [Queue Scheduling Note](../fixtures/queue-chart.pdf), p. 1, region `0.09, 0.12, 0.51, 0.14`. Confirm QS-17 is the experiment ID. |
| `p2_chart_budget`<br>What is the per-request timeout budget? | Answerable — 250 ms | [Queue Scheduling Note](../fixtures/queue-chart.pdf), p. 1, region `0.09, 0.16, 0.44, 0.18`. Confirm 250 ms applies per request. |
| `p2_chart_tallest`<br>Which scheduler mode has the greatest median queue wait in Figure 1? | Answerable — FIFO (visual) | [Queue Scheduling Note](../fixtures/queue-chart.pdf), p. 1, region `0.18, 0.30, 0.84, 0.62`. Confirm FIFO is tallest and the label requires visually associating bars and categories. |
| `p2_chart_shortest`<br>Which scheduler mode has the shortest bar in Figure 1? | Answerable — Priority (visual) | [Queue Scheduling Note](../fixtures/queue-chart.pdf), p. 1, region `0.18, 0.30, 0.84, 0.62`. Confirm Priority is shortest and the label requires visually associating bars and categories. |
| `p2_chart_errors`<br>How many requests failed in the queue experiment? | Unanswerable | [Queue Scheduling Note](../fixtures/queue-chart.pdf), entire PDF. Check the full page for failures distinct from the number processed. |

## Expansion candidates

| ID and question | Proposal | Source and decision |
| --- | --- | --- |
| `harbor_partner_limit` How many items can a Partner account borrow at once? | Answerable, 10 items | [Harbor Library](../fixtures/library-loans.pdf), p. 1, table region (0.09, 0.21, 0.80, 0.31). Confirm Partner and Loan limit intersect at 10 items. |
| `harbor_renewed_period` What is the total loan period for an eligible Resident item after one renewal? | Answerable, 35 days | [Harbor Library](../fixtures/library-loans.pdf), p. 1, table region (0.09, 0.21, 0.80, 0.31), and p. 2 (0.09, 0.16, 0.46, 0.22). Confirm 21 + 14 days, one renewal and the eligibility qualifier. |
| `harbor_overdue_fee` What daily overdue fee does the schedule charge a Resident account? | Unanswerable | [Harbor Library](../fixtures/library-loans.pdf), both pages. Confirm no fee is given. |
| `juniper_north_meadow` Which feature is directly north of the Meadow in Figure 1? | Answerable, Pond, visual | [Juniper Garden](../fixtures/garden-map.pdf), p. 1, map region (0.19, 0.25, 0.79, 0.60). Confirm the layout establishes north of Meadow and the caption gives only orientation. |
| `juniper_closing_time` At what time does Juniper Garden close to visitors? | Unanswerable | [Juniper Garden](../fixtures/garden-map.pdf), entire page. Confirm no hours appear. |
