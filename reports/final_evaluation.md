# Frozen evaluation

The maintainer authorized one execution of the
[posted configuration](https://github.com/ompatelz/EvidenceRAG/pull/9#issuecomment-6921075852)
at `0eeb397e00c489c45a4ffe7ac6bb38e90125fb94` on 2026-11-16.
The run completed once with five query responses and zero execution failures.
The [freeze record](runs/release-frozen-config.json) hashes the lock, corpus
and labels. The [raw run](runs/release-frozen-bm25.json) contains scoped
rankings, response reasons, stage timings and the runtime environment.
No rerun or final-test tuning was performed.

## Results

| Measure | Eligible denominator | Observation |
| --- | ---: | --- |
| BM25 top-1 hit, provisional evidence-unit labels | 2 answerable text queries | 2/2 |
| BM25 mean recall, MRR and nDCG at K=1, 3 and 5 | Same 2 text queries | 1.0 for each metric at each K |
| Explicit unsupported-modality response | 2 flagged pixel-dependent queries | 2/2 |
| Other abstentions | 3 remaining queries | 3/3 reported `generator_unavailable` |
| Answer correctness, citation support, page/region answer grounding and visual QA | No eligible generated answers | Unmeasured |

Every item belongs to one synthetic, one-page PDF. The original run used the `needs_review` snapshot. The owner has since
reviewed those labels in [the current snapshot](../datasets/eval/reviewed_labels.jsonl). The two-query retrieval denominator provides
too little evidence for a general accuracy claim. The visual rows exercise
the caller-supplied modality flag. Three generator-unavailable responses
show the configured runtime state and provide no semantic abstention
accuracy estimate. The unanswerable question still retrieved five units.

## Source audit

Reviewed all five rows against the source page after the run. The first
retrieved units for the experiment identifier and timeout budget match
the text lines containing “QS-17” and “250 ms.” The chart image shows
FIFO as the tallest bar and Priority as shortest. The text extractor
returns axis values, labels and caption, while the association between
each bar and its height requires the rendered chart. The page lists 500
processed requests and gives no failure count. Retrieval still ranked
the experiment identifier first for that question. This audit records
direct observations and leaves formal dataset label approval outstanding.

## Operational cost

Windows 11, Intel Core i7-13700H, 20 logical CPUs, Python 3.12.9.
One fresh application and artifact store processed one PDF and five
sequential in-process ASGI queries. OS file cache was uncontrolled.
No generative or semantic model, remote calls, or persistent index
participated. The lifecycle recorded 95.81 ms for one page with 13
evidence units. Across the three BM25 requests, wall time was
7.22–10.34 ms and handler time was 3.13–4.29 ms. The two early
modality refusals returned in 4.58–4.71 ms wall time. These are individual
smoke observations, with too few samples for tail estimates.

## Reproduction record

```sh
git switch --detach 0eeb397e00c489c45a4ffe7ac6bb38e90125fb94
uv sync --locked --all-extras --dev
uv run --locked python scripts/frozen_evaluation.py run --record /path/to/release-frozen-config.json --output /path/to/new-run.json
```

The recorder checks the frozen commit, hashes, workload, and environment
and refuses to overwrite an existing output. The manifest uses host
metadata for this run. A reproduction on a different host needs its own
freeze record with matching code and inputs. Treat any reproduction as a
rerun and preserve the first execution as published above.
