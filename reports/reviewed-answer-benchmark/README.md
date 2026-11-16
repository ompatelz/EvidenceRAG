# Retrieval run record

The four Atlas source reviews confirmed the proposed labels without changing
the question, answers, or evidence. The benchmark revision also adds five
candidates. The refreshed development denominator increases from 11 to 13
scored queries. BM25 Hit@3 moves from 10/11 to 12/13 and Recall@3 moves from
0.909 to 0.897. Dense Hit@3 stays at 1.000. Both baselines retain validation
Hit@3 of 10/11. These are changes in the diagnostic sample and rankings.
The confirmed Atlas caption is still a shared rank-1 miss. The refreshed
run supports no new claim about general retrieval quality or live answers.

The fixed-draft claim-support ablation is a separate historical experiment.
It has no newly approved claim judgments. The frozen report and raw
outputs remain part of the historical release record.

## Reproduce

Run against the current label snapshot and the pinned local model cache.

```powershell
uv run --locked --all-extras python scripts/reviewed_retrieval.py --output-dir reports/generated/answer-benchmark
```

## Raw SHA-256

UTF-8 text hashes normalize line endings to LF.

- `e0.json` · `2f67aaf754816b7b94c3fab87af53a682816b0da717e6a5aa25890d4ec0947cc`
- `e1.json` · `d9f4637140d48c7de81214ed213fd3ad8d8361da12fdc0446f178229a48f1f0c`
- `e2.json` · `b73353eb60611a839bac4fabfa5697820f8287db156c6b82fbdfdd2c900ff243`
- `e3.json` · `0b51a73cf674d1c81b1640df57fe79aaff9d6d8c78164186d4e3cd17e688fb49`
