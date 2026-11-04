# Phase 2 candidate-label review packet

Dataset SHA-256 (LF-normalized): `cc8ee84a47f4d1930154b2d466e2a56c26739b0fe45ec267f988ddaf7afb5a46`.

All 31 labels below are AI-proposed and **not human verified**. Open each linked
source PDF and inspect the cited page or region. For an unanswerable question,
inspect the entire source document before confirming that the requested fact
is absent. Check the question, answer, source support, evidence selection,
category, ambiguity, and visual dependence. A checked box means you completed
that review; write corrections beside the item or send them by query ID.

The five frozen-test labels may be checked for source correctness, but their
retrieval results must stay sealed until configuration lock. This packet contains
no model rankings or scores.

## Development (13)

### p2_atlas_rate

**Question:** What is the calibration sampling rate of the Atlas sensor?

**Proposed answer:** 20 hertz

**Category:** `narrative_fact`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Atlas Sensor Note](../fixtures/atlas-narrative.pdf).

**Proposed source support:**

- Page 1, `ev_db963e2e6b7064f643c914bace118433`: “The Atlas sensor samples at 20 hertz during calibration.”

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_atlas_path

**Question:** Which stage follows the filter in the Atlas process flow?

**Proposed answer:** Archive

**Category:** `diagram_interpretation`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Atlas Sensor Note](../fixtures/atlas-narrative.pdf).

**Proposed source support:**

- Page 1, `ev_c395759200fd36e917985b8e305bb305`: “Figure 1. Calibration data flow: Sensor -> Filter -> Archive.”

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_atlas_filter

**Question:** What happens to each Atlas sample before it is archived?

**Proposed answer:** It passes through a filter.

**Category:** `narrative_fact`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Atlas Sensor Note](../fixtures/atlas-narrative.pdf).

**Proposed source support:**

- Page 1, `ev_5cee49445595c480dfc55a1c71a45dfd`: “Each sample passes through a filter before archival.”

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_atlas_weight

**Question:** What is the mass of the Atlas sensor?

**Proposed answer:** Unanswerable (confirm absence)

**Category:** `unanswerable`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Atlas Sensor Note](../fixtures/atlas-narrative.pdf).

**Proposed source support:** No gold evidence; inspect the full PDF.

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_retry_protocol

**Question:** Which protocol ID names the chunk-transfer experiment?

**Proposed answer:** CR-42

**Category:** `exact_identifier`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Checksum and Retry Protocol Note](../fixtures/checksum-retry.pdf).

**Proposed source support:**

- Page 1, `ev_430c54a3edba548c5daeaf46122b035c`: “Protocol ID CR-42 identifies this synthetic chunk-transfer experiment.”

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_retry_digest

**Question:** Which digest algorithm does each chunk carry?

**Proposed answer:** SHA-256

**Category:** `exact_identifier`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Checksum and Retry Protocol Note](../fixtures/checksum-retry.pdf).

**Proposed source support:**

- Page 1, `ev_f652a5a6f126186aba2b702a0f5f93e4`: “Each chunk carries a SHA-256 digest and a 4096-byte payload.”

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_retry_chunk_bytes

**Question:** What is the chunk payload size in bytes?

**Proposed answer:** 4096 bytes

**Category:** `exact_number`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Checksum and Retry Protocol Note](../fixtures/checksum-retry.pdf).

**Proposed source support:**

- Page 1, `ev_f652a5a6f126186aba2b702a0f5f93e4`: “Each chunk carries a SHA-256 digest and a 4096-byte payload.”

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_retry_ack

**Question:** What does the receiver do before acknowledging a chunk?

**Proposed answer:** It recomputes the digest.

**Category:** `narrative_fact`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Checksum and Retry Protocol Note](../fixtures/checksum-retry.pdf).

**Proposed source support:**

- Page 1, `ev_51884f4371ade7cc944734f0c7bf8928`: “The receiver recomputes the digest before acknowledging a chunk.”

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_retry_formula

**Question:** How does Equation 1 calculate total payload bytes?

**Proposed answer:** Chunk count multiplied by chunk payload bytes.

**Category:** `equation_lookup`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Checksum and Retry Protocol Note](../fixtures/checksum-retry.pdf).

**Proposed source support:**

- Page 1, `ev_f9371df406bfe115e68f01c9db7b5f2f`: “Equation 1: payload bytes = chunk count x chunk payload bytes.”

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_retry_total

**Question:** For three chunks, how many payload bytes are sent without headers?

**Proposed answer:** 12288 bytes

**Category:** `equation_calculation`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Checksum and Retry Protocol Note](../fixtures/checksum-retry.pdf).

**Proposed source support:**

- Page 1, `ev_7aca34499f352ed1bf759397c9f00fc8`: “For 3 chunks, the total payload is 3 x 4096 = 12288 bytes.”

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_retry_attempts

**Question:** How many attempts per chunk are allowed including the initial send?

**Proposed answer:** 3 attempts

**Category:** `exact_number`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Checksum and Retry Protocol Note](../fixtures/checksum-retry.pdf).

**Proposed source support:**

- Page 2, `ev_0ed3ae1b52a2404de250ca7e1c909abc`: “The maximum is 3 attempts per chunk, including the initial send.”

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_retry_second_backoff

**Question:** How long is the wait before the second retry?

**Proposed answer:** 100 ms

**Category:** `table_lookup`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Checksum and Retry Protocol Note](../fixtures/checksum-retry.pdf).

**Proposed source support:**

- Page 2, `ev_87747218c53c5146da939bd13fbbaee7`: “Attempt 3 | second retry | wait 100 ms”

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_retry_loss

**Question:** What measured packet-loss percentage does the experiment report?

**Proposed answer:** Unanswerable (confirm absence)

**Category:** `unanswerable`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Checksum and Retry Protocol Note](../fixtures/checksum-retry.pdf).

**Proposed source support:** No gold evidence; inspect the full PDF.

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

## Validation (13)

### p2_table_best

**Question:** Which retrieval method has the highest F1 in Table 1?

**Proposed answer:** Hybrid, 0.86

**Category:** `table_lookup`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Retrieval Baseline Fixture](../fixtures/retrieval-table.pdf).

**Proposed source support:**

- Page 1, `ev_2b83704fed94b06b9188054b10043ab8`: “| Method | Precision | Recall | F1 |
| --- | --- | --- | --- |
| Lexical | 0.78 | 0.72 | 0.75 |
| Dense | 0.82 | 0.80 | 0.81 |
| Hybrid | 0.88 | 0.84 | 0.86 |”

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_table_dense_recall

**Question:** What recall does the Dense row report?

**Proposed answer:** 0.80

**Category:** `table_lookup`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Retrieval Baseline Fixture](../fixtures/retrieval-table.pdf).

**Proposed source support:**

- Page 1, `ev_2b83704fed94b06b9188054b10043ab8`: “| Method | Precision | Recall | F1 |
| --- | --- | --- | --- |
| Lexical | 0.78 | 0.72 | 0.75 |
| Dense | 0.82 | 0.80 | 0.81 |
| Hybrid | 0.88 | 0.84 | 0.86 |”

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_table_f1_gap

**Question:** How many points higher is Hybrid F1 than Lexical F1?

**Proposed answer:** 0.11

**Category:** `table_calculation`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Retrieval Baseline Fixture](../fixtures/retrieval-table.pdf).

**Proposed source support:**

- Page 1, `ev_2b83704fed94b06b9188054b10043ab8`: “| Method | Precision | Recall | F1 |
| --- | --- | --- | --- |
| Lexical | 0.78 | 0.72 | 0.75 |
| Dense | 0.82 | 0.80 | 0.81 |
| Hybrid | 0.88 | 0.84 | 0.86 |”

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_table_latency

**Question:** What is the Dense method's latency in milliseconds?

**Proposed answer:** Unanswerable (confirm absence)

**Category:** `unanswerable`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Retrieval Baseline Fixture](../fixtures/retrieval-table.pdf).

**Proposed source support:** No gold evidence; inspect the full PDF.

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_cache_study_id

**Question:** What study ID identifies the cache experiment?

**Proposed answer:** CA-09

**Category:** `exact_identifier`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Cache Admission Study Note](../fixtures/cache-admission.pdf).

**Proposed source support:**

- Page 1, `ev_64765a47aecd11fe55268e39db858989`: “Study ID CA-09 identifies this synthetic cache experiment.”

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_cache_capacity

**Question:** What is the cache capacity?

**Proposed answer:** 64 MiB

**Category:** `exact_number`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Cache Admission Study Note](../fixtures/cache-admission.pdf).

**Proposed source support:**

- Page 1, `ev_3106fbfc00a04d67e4f6fc9655947361`: “The cache capacity is 64 MiB.”

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_cache_formula

**Question:** What equation defines hit ratio in the study?

**Proposed answer:** hits / (hits + misses)

**Category:** `equation_lookup`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Cache Admission Study Note](../fixtures/cache-admission.pdf).

**Proposed source support:**

- Page 1, `ev_ace047e2a9ec126336deb5074eed1f3d`: “Equation 1: hit ratio = hits / (hits + misses).”

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_cache_ratio

**Question:** What hit ratio follows from 800 hits and 200 misses?

**Proposed answer:** 0.80

**Category:** `equation_calculation`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Cache Admission Study Note](../fixtures/cache-admission.pdf).

**Proposed source support:**

- Page 1, `ev_6ad6ad372f5d19cc6464e3bdf3db7d6a`: “The observation window recorded 800 hits and 200 misses.”
- Page 1, `ev_ace047e2a9ec126336deb5074eed1f3d`: “Equation 1: hit ratio = hits / (hits + misses).”

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_cache_limit

**Question:** What is the largest object size permitted by admission?

**Proposed answer:** 8 MiB

**Category:** `exact_number`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Cache Admission Study Note](../fixtures/cache-admission.pdf).

**Proposed source support:**

- Page 1, `ev_93c5a685a081b0bc33384f0d1cd28ab3`: “Admission rejects any object larger than 8 MiB.”

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_cache_eviction

**Question:** When does the cache evict an object?

**Proposed answer:** When admission would exceed capacity.

**Category:** `narrative_fact`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Cache Admission Study Note](../fixtures/cache-admission.pdf).

**Proposed source support:**

- Page 1, `ev_9c89b8f08690639fd914a9daa062b7f0`: “Eviction occurs when admitting an object would exceed capacity.”

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_cache_best_hit

**Question:** Which policy has the highest synthetic hit ratio?

**Proposed answer:** TinyLFU at 0.84

**Category:** `table_lookup`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Cache Admission Study Note](../fixtures/cache-admission.pdf).

**Proposed source support:**

- Page 2, `ev_bbef2a2a496ae0b6e132730d9544fc22`: “FIFO | 0.71 | 12 ms”
- Page 2, `ev_75b062f00ee430ef54a064e0997c1d9a`: “LRU | 0.80 | 9 ms”
- Page 2, `ev_858081074b40947f3c812981638ae62c`: “TinyLFU | 0.84 | 11 ms”

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_cache_lru_latency

**Question:** What median lookup latency is listed for LRU?

**Proposed answer:** 9 ms

**Category:** `table_lookup`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Cache Admission Study Note](../fixtures/cache-admission.pdf).

**Proposed source support:**

- Page 2, `ev_75b062f00ee430ef54a064e0997c1d9a`: “LRU | 0.80 | 9 ms”

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_cache_energy

**Question:** How much energy did the cache experiment consume?

**Proposed answer:** Unanswerable (confirm absence)

**Category:** `unanswerable`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Cache Admission Study Note](../fixtures/cache-admission.pdf).

**Proposed source support:** No gold evidence; inspect the full PDF.

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

## Frozen Test (5)

### p2_chart_id

**Question:** What is the queue experiment identifier?

**Proposed answer:** QS-17

**Category:** `exact_identifier`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Queue Scheduling Note](../fixtures/queue-chart.pdf).

**Proposed source support:**

- Page 1, `ev_b2b35ac374207bd1356157d77808e4a2`: “Experiment QS-17 compares three scheduler modes.”

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_chart_budget

**Question:** What is the per-request timeout budget?

**Proposed answer:** 250 ms

**Category:** `exact_number`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Queue Scheduling Note](../fixtures/queue-chart.pdf).

**Proposed source support:**

- Page 1, `ev_642c7e2d8322f507972eccbb0a3f3104`: “The timeout budget was 250 ms per request.”

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_chart_tallest

**Question:** Which scheduler mode has the greatest median queue wait in Figure 1?

**Proposed answer:** FIFO

**Category:** `visual_chart`; visual-dependent: `true`; review status: `needs_review`.

**Source:** [Queue Scheduling Note](../fixtures/queue-chart.pdf).

**Proposed source support:**

- Page 1, visual region `{'x0': 0.18, 'y0': 0.3, 'x1': 0.84, 'y1': 0.62}`; no parsed evidence-unit ID. Inspect the actual image.

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_chart_shortest

**Question:** Which scheduler mode has the shortest bar in Figure 1?

**Proposed answer:** Priority

**Category:** `visual_chart`; visual-dependent: `true`; review status: `needs_review`.

**Source:** [Queue Scheduling Note](../fixtures/queue-chart.pdf).

**Proposed source support:**

- Page 1, visual region `{'x0': 0.18, 'y0': 0.3, 'x1': 0.84, 'y1': 0.62}`; no parsed evidence-unit ID. Inspect the actual image.

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _

### p2_chart_errors

**Question:** How many requests failed in the queue experiment?

**Proposed answer:** Unanswerable (confirm absence)

**Category:** `unanswerable`; visual-dependent: `false`; review status: `needs_review`.

**Source:** [Queue Scheduling Note](../fixtures/queue-chart.pdf).

**Proposed source support:** No gold evidence; inspect the full PDF.

- [ ] I inspected the source, answer, evidence, category, and ambiguity; the proposed label is correct or my correction is recorded.
- Correction / notes: _
