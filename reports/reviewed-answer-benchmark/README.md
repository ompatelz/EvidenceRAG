# Retrieval run record

All 36 source labels have owner decisions. The owner approved a 0–1 scale
clarification for `p2_table_f1_gap` and added the adjacent worked result to the
gold evidence for `p2_cache_ratio`. All other answer and evidence proposals
were confirmed. The four retrievers score the same 24 text-answerable
development and validation examples. The prior frozen artifacts are preserved
and the frozen family was excluded from this run.

## Differences from the provisional pilot

- Development grew from 11 to 13 scored queries. BM25 Hit@3 moved from
  10/11 to 12/13 and Recall@3 from 0.909 to 0.897. Dense Hit@3 stayed at 1.000.
  The new library renewal question needs three units. BM25 found two at K=3;
  dense and reranked retrieval found all three.
- On the older gold set, the dense result line for the cache ratio was ranked
  first but counted as irrelevant. With that same ranking rescored against the
  approved region, Hit@1 changes from 0 to 1 and Recall@1 from 0/2 to 1/3.
  Both retrieved all eligible regions by K=3. BM25 still hits at rank 1,
  with Recall@1 changing from 1/2 to 1/3 as the gold denominator grows.
- Validation Hit@1 moved from 7/11 to 8/11 for dense; BM25 stayed at 7/11.
  Both retained Hit@3 of 10/11. BM25 and dense still miss the cache comparison
  evidence at K=5. The clarified F1 question still hits its gold table at rank 1.
- The local fixed-draft claim-support ablation has no newly approved claim
  judgments. Live metrics and usage are unmeasured. The synthetic families
  and single historical frozen family offer limited evidence of generalization.

## Reproduce

Run against the current label snapshot and the pinned local model cache.

```powershell
uv run --locked --all-extras python scripts/reviewed_retrieval.py --output-dir reports/generated/answer-benchmark
```

## Raw SHA-256

UTF-8 text hashes normalize line endings to LF.

- `e0.json` · `3947675cd6b44014b1da831bb647ed56f4c08417caaa4b143f70077a71f30aaf`
- `e1.json` · `b71af90160c50d643a6e5590af7c85e4b0c646cb987100173ed1c552eadd37ba`
- `e2.json` · `fc48b97d0c676d21e7f4afa10c8f89e75d9ce5bc4dc627ab68de439ee27a7105`
- `e3.json` · `c27fe875e5f7ebd4da4da72df24fb47b44237af2c468ca87b380dd2f2eab8a53`
