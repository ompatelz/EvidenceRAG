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

- `e0.json` · `2c071a57459f5610ebe6b819c0d84ddae4183e2095d70548c9ec4c5631b4e566`
- `e1.json` · `d7c87fafcde83680a2fa61ff3d34b8a49d8dda608e441ee19e4a63dba3d080e4`
- `e2.json` · `2b4fadc48aa04fb1062a18e7dfd0e7e4c5fdc6ed461a2ae8aebbceae82c93fe1`
- `e3.json` · `4ac31ea6e93c3db3a31d0370eab5bdf15bdd9be247b5abd87c5bc2ab524a7364`
