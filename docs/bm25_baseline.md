# E0: BM25 lexical baseline

## Contract and index lifecycle

E0 indexes the `EvidenceUnit.text` from Phase 1's persisted `evidence.json` artifacts.
The experiment CLI reparses selected repository PDFs into a temporary local artifact
store, persists canonical evidence, and rebuilds an in-memory BM25 index from those
artifacts. It does not index arbitrary PDF text directly. Each result includes evidence
ID, exact document/version, page, anchor precision/box, rank, score, and search time.
Requested document/version scope is applied before document frequencies, lengths, and
scores are calculated. An empty scope returns no results. The caller must supply the
authorized scope; this local single-user baseline does not implement authorization.

Tokenization applies Unicode NFKC, then `casefold()`. It retains Unicode letter/number
sequences and internal `.`, `_`, `/`, and `-`, so `QS-17` and `0.86` remain exact tokens.
Other punctuation separates tokens. There is no stemming and no stopword removal. A
query's repeated terms count once; repeated document terms contribute term frequency.
Empty queries and empty indexes return no hits; only positive-score matches are returned.
Scores use BM25 with `k1=1.2`, `b=0.75`, and
`idf=ln(1+(N-df+0.5)/(df+0.5))`. Exact score ties sort by evidence ID ascending.
Raw BM25 scores are not comparable to future dense scores.

`index_id` hashes sorted evidence IDs, document/version, parser and representation
versions, text, tokenizer version, parameters, and index version. Rebuild replaces the
whole index, repeated IDs are deduplicated (conflicting duplicates fail), upsert
replaces by stable ID, and deletion removes an exact document/version. There is no
on-disk BM25 index yet; a process restart requires rebuilding from persisted evidence.
No stale version is searched when the caller scopes to the current version.

## Evaluation definition

Run from the repository root:

```bash
uv run python -m evidence_rag.eval.bm25_run \
  --manifest datasets/manifests/fixtures.json \
  --seed datasets/eval/phase2_seed.jsonl \
  --output reports/runs/e0-phase2-pilot.json
```

The command is fixed to development and validation; it does not search frozen-test
questions. It saves every raw ranking and query timing, source/dataset/manifest hashes,
Git SHA at run, index identity, parser/tokenizer/config, environment, and split metrics.
The Git SHA is the parent commit when generated before the code commit; the run also
records that source changes were uncommitted and hashes the runner, corpus loader,
metric module, and BM25 implementation.

Relevance is a binary **evidence-unit ID** judgment. Hit Rate@K is 1 if any gold unit
is in the top K, else 0. Recall@K is retrieved gold units divided by all gold units.
MRR@K is the reciprocal of the first gold rank (or 0). nDCG@K discounts each binary
gold hit by `1/log2(rank+1)` and divides by the ideal ranking's gain. Aggregates are
macro means over answerable, nonvisual queries. Unanswerable queries retain raw
rankings but have no relevance denominator. Visual page-region labels are excluded
from evidence-unit metrics.

## Provisional pilot observation

The saved run has 8 queries (4 per split), of which 6 answerable nonvisual candidate
labels are scored, over 11 evidence units from 2 document families. Both development
and validation have Hit Rate@1 and Recall@1 of 2/3, MRR@3 of 5/6, and Hit Rate@3 and
Recall@3 of 3/3. These are **provisional diagnostics against unreviewed labels**, not
validated retrieval claims. The raw run records exact values, rankings, identities,
and timing. The two splits each contain only three scored questions, so identical
aggregates are not evidence of generalization.

One failure: the development flow question ranks the Atlas sampling sentence above
the supporting diagram caption; the caption is rank 2. The validation best-F1
question ranks the table caption above the table unit; the table is rank 2. BM25
matches words, not whether a sentence actually contains the answer. For an
unanswerable question about the Atlas sensor's mass, BM25 still returns Atlas units;
retrieval alone cannot establish abstention.

This pilot omits equations, larger documents, and independently reviewed labels.
Query times are one cold-process engineering observation, not a latency benchmark.
