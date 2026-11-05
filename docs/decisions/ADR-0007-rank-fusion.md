# ADR-0007: Scoped reciprocal rank fusion

Status: Accepted for the first grounded QA checkpoint

Date: 2026-11-05

## Decision

Fuse BM25 and dense evidence rankings using RRF v1: for each canonical evidence ID,
sum `1 / (60 + rank)` from each method that returned it. Prefetch at most 10 hits
from each index and return at most 5 fused hits. Both retrievers receive the same
exact document/version scope before searching. Empty scope or blank query returns
an empty result. A component error fails the hybrid request; it cannot silently
become a single-method result.

Deduplicate by canonical evidence ID, taking the best rank within each method.
The same ID with conflicting document, version, page, or anchor metadata is an
error. Out-of-scope candidates, invalid rank, and nonfinite source score are
errors. Descending RRF score determines order; exact score ties use evidence ID
ascending. Keep both methods' original rank and score for inspection. BM25 and
cosine scores are never added or directly compared.

## Evidence and trade-off

Four configurations (`rrf_k` 10/60 × prefetch 10/20) were measured on validation
with the fixed final K=5. All had identical validation metrics. The first-listed
configuration uses the smaller prefetch and standard constant 60. On the 11
provisional, answerable nonvisual validation questions, hybrid nDCG@5 was 0.781,
below BM25 0.797 and dense 0.814. Hybrid therefore remains an inspectable option,
not an asserted quality improvement. Results and every raw ranking are in
`reports/runs/e2-hybrid-validation.json`; labels have not been human reviewed.

RRF handles incompatible scoring scales and a missing result from either method.
It can demote a highly relevant single-method candidate when the other method
ranks distracting units well. The additional embedding and vector search cost
also exceeds BM25 alone. Tune only on validation, and re-evaluate after label
review; never tune on the frozen chart family.

## Rollback

Revert the checkpoint commit, leaving E0/E1 artifacts and code intact.
