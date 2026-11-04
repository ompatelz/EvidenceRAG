"""Shared, failure-aware evidence-unit evaluation for lexical and dense search."""

from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import asdict
from typing import Any

from evidence_rag.eval.metrics import RetrievalMetrics, mean_metrics, score_ranking
from evidence_rag.eval.models import EvaluationItem, EvaluationSplit
from evidence_rag.retrieval.bm25 import RankedEvidence

CUTOFFS = (1, 3, 5)
Search = Callable[
    [EvaluationItem, list[tuple[str, str]]],
    tuple[Sequence[RankedEvidence], dict[str, float]],
]


def development_items(items: Sequence[EvaluationItem]) -> list[EvaluationItem]:
    """Keep the frozen family out of retrieval and reject an empty evaluation."""
    selected = [
        item
        for item in items
        if item.split in {EvaluationSplit.DEVELOPMENT, EvaluationSplit.VALIDATION}
    ]
    if not selected:
        raise ValueError("no development or validation items")
    return selected


def aggregate_rows(rows: Sequence[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    """Macro averages with an explicit scored-query denominator for each group."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row[key])].append(row)
    result: dict[str, dict[str, Any]] = {}
    for group, members in sorted(groups.items()):
        scored = [row for row in members if row["metrics"] is not None]
        result[group] = {
            "queries": len(members),
            "scored": len(scored),
            "failures": sum(row.get("failure") is not None for row in members),
            "metrics": {
                str(k): (
                    asdict(
                        mean_metrics([RetrievalMetrics(**row["metrics"][str(k)]) for row in scored])
                    )
                    if scored
                    else None
                )
                for k in CUTOFFS
            },
        }
    return result


def evaluate_queries(
    items: Sequence[EvaluationItem], search: Search
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Save each retrieval failure without exposing an exception's document text."""
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for item in development_items(items):
        scope = sorted((ref.document_id, ref.document_version) for ref in item.documents)
        gold_ids = {ref.evidence_id for ref in item.gold_evidence if ref.evidence_id}
        row: dict[str, Any] = {
            "query_id": item.query_id,
            "split": item.split.value,
            "category": item.category,
            "review_status": item.review_status.value,
            "answerable": item.answerable,
            "requires_visual_evidence": item.requires_visual_evidence,
            "scope": scope,
            "gold_evidence_ids": sorted(gold_ids),
            "ranking": [],
            "metrics": None,
            "failure": None,
        }
        try:
            hits, timings = search(item, scope)
        except Exception as exc:
            failure = {
                "query_id": item.query_id,
                "stage": "retrieval",
                "error_type": type(exc).__name__,
            }
            row["failure"] = failure
            failures.append(failure)
        else:
            row["ranking"] = [asdict(hit) for hit in hits]
            row.update(timings)
            if item.answerable and not item.requires_visual_evidence:
                ranked_ids = [hit.evidence_id for hit in hits]
                row["metrics"] = {
                    str(k): asdict(score_ranking(ranked_ids, gold_ids, k=k)) for k in CUTOFFS
                }
        rows.append(row)
    return rows, failures
