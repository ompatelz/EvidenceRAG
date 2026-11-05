# Optional CPU reranking — checkpoint 2

## Model and execution contract

The opt-in reranker uses [FastEmbed's supported ONNX cross-encoder](https://qdrant.github.io/fastembed/examples/Supported_Models/),
`Xenova/ms-marco-MiniLM-L-6-v2`, pinned to Hugging Face revision
`a09144355adeed5f58c8ed011d209bf8ee5a1fec`. FastEmbed reports its
license as Apache-2.0 and approximate model size as 0.08 GB. The pinned
unquantized ONNX file is 90,992,115 bytes. Its [model config](https://huggingface.co/Xenova/ms-marco-MiniLM-L-6-v2/blob/main/config.json)
has a 512-position limit. This implementation uses a stricter 256-token
pair limit with right-side `longest_first` tokenizer truncation, a 512-character
question limit, and a 2,048-character passage limit. It scores at most five
hybrid candidates per query, in batches of four, on CPU with two ONNX threads.
Peak process memory was not measured. No paid API or PDF upload occurs.

The model is loaded only for the opt-in run. An enabled reranker without the
model fails configuration; disabled mode returns hybrid order without model
work. The candidate evidence ID must resolve to a unit in the requested exact
document/version scope, with matching version and page. A mismatch is an
error, not a fallback. Equal cross-encoder scores sort by evidence ID.
The final ranking retains fusion rank/score and BM25/dense provenance.

The per-query timeout is 2,000 ms. It bounds how long the caller waits, not
the duration of already-running ONNX work. A timed-out query returns the
unchanged hybrid ranking and disables further submissions on that reranker
instance; the one existing worker may finish in the background. A scoring
exception or invalid score also returns unchanged hybrid order, with an
explicit `failure_fallback` status. This is a local synchronous MVP policy,
not hard process isolation. Use a separate worker process if hard cancellation
becomes necessary.

## Reproduce and compare

Run after `uv sync --all-extras --dev` and the cached E2 run. Explicitly cache
the pinned public model into the ignored `tmp/hf-model-cache` before the first
run; ordinary CI never downloads it:

```bash
uv run python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='Xenova/ms-marco-MiniLM-L-6-v2', revision='a09144355adeed5f58c8ed011d209bf8ee5a1fec', cache_dir='tmp/hf-model-cache', allow_patterns=['config.json','tokenizer.json','tokenizer_config.json','special_tokens_map.json','vocab.txt','onnx/model.onnx'])"
uv run python -m evidence_rag.eval.rerank_run
```

The runner reuses the exact selected E2 candidate rankings and their recorded
retrieval times from `reports/runs/e2-hybrid-validation.json`. It measures
reranking separately and saves every query's final ranking, scorer status,
retrieval time, reranking time, and summed total in
`reports/runs/e3-rerank-validation.json`. Model load and corpus preparation
are excluded from per-query times. Development and validation are included;
frozen test is not searched. All labels remain provisional and unreviewed.

| Split | Method | Hit@5 | MRR@5 | nDCG@5 | Mean retrieval | Mean rerank | Mean total |
|---|---|---:|---:|---:|---:|---:|---:|
| Development | Hybrid | 1.000 | 0.867 | 0.899 | 10.33 ms | — | 10.33 ms |
| Development | Reranked | 1.000 | 0.864 | 0.899 | 10.33 ms | 30.51 ms | 40.84 ms |
| Validation | Hybrid | 0.909 | 0.727 | 0.781 | 9.86 ms | — | 9.86 ms |
| Validation | Reranked | 0.909 | 0.773 | 0.814 | 9.86 ms | 45.04 ms | 54.89 ms |

Validation p95 retrieval/reranking/total were 13.35/67.72/77.04 ms in this
single local run. All 26 queries were scored without a fallback. On validation,
`p2_cache_limit` moved from first-relevant rank 2 to 1; the other ten scored
queries did not change first-relevant rank. On development,
`p2_atlas_path` improved 3→2 and `p2_retry_chunk_bytes` improved 5→2,
while `p2_retry_second_backoff` worsened 1→2. These changes are the full
category-level win/loss evidence on this tiny corpus, not a general claim.

Reranking remains available but disabled by default. Its one validation
improvement reaches the dense baseline's MRR@5 and nDCG@5, at substantial
extra CPU time. It cannot recover an evidence unit missing from the five
hybrid candidates. Reassess after human label review and broader documents.
