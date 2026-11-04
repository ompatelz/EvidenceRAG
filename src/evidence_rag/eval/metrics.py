"""Binary evidence-unit retrieval metrics with explicit denominators."""

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalMetrics:
    """Metrics for one answerable question at one cutoff."""

    hit_rate: float
    recall: float
    mrr: float
    ndcg: float


def score_ranking(ranked_ids: Sequence[str], relevant_ids: set[str], *, k: int) -> RetrievalMetrics:
    """Score unique evidence IDs; MRR is truncated to the supplied cutoff."""
    if k <= 0:
        raise ValueError("k must be positive")
    if not relevant_ids:
        raise ValueError("answerable metric requires at least one relevant evidence ID")
    if len(set(ranked_ids)) != len(ranked_ids):
        raise ValueError("ranking contains duplicate evidence IDs")
    top = ranked_ids[:k]
    relevant_ranks = [rank for rank, item in enumerate(top, 1) if item in relevant_ids]
    dcg = sum(1 / math.log2(rank + 1) for rank in relevant_ranks)
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(k, len(relevant_ids)) + 1))
    return RetrievalMetrics(
        hit_rate=float(bool(relevant_ranks)),
        recall=len(relevant_ranks) / len(relevant_ids),
        mrr=0.0 if not relevant_ranks else 1 / relevant_ranks[0],
        ndcg=dcg / ideal,
    )


def mean_metrics(rows: Sequence[RetrievalMetrics]) -> RetrievalMetrics:
    """Macro-average by answerable query; reject an empty denominator."""
    if not rows:
        raise ValueError("no scored answerable questions")
    count = len(rows)
    return RetrievalMetrics(
        hit_rate=sum(row.hit_rate for row in rows) / count,
        recall=sum(row.recall for row in rows) / count,
        mrr=sum(row.mrr for row in rows) / count,
        ndcg=sum(row.ndcg for row in rows) / count,
    )
