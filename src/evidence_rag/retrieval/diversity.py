"""Optional rank-preserving page diversity over an explicit bounded candidate pool."""

from collections import Counter
from collections.abc import Sequence

from evidence_rag.retrieval.bm25 import RankedEvidence


def select_candidates(
    hits: Sequence[RankedEvidence],
    *,
    diversify_pages: bool,
    limit: int = 5,
) -> tuple[RankedEvidence, ...]:
    """Prefer at most two units per document/page, then fill by original rank.

    This is a retrieval heuristic, not a relevance or support judgment. Complete
    version identity participates in the page key. Original BM25 scores/ranks
    remain unchanged for inspection.
    """
    if not 1 <= limit <= 5:
        raise ValueError("selection limit must be between one and five")
    if not diversify_pages:
        return tuple(hits[:limit])
    counts: Counter[tuple[str, str, int]] = Counter()
    selected = []
    deferred = []
    for hit in hits:
        key = (hit.document_id, hit.document_version, hit.page_index)
        if counts[key] < 2:
            selected.append(hit)
            counts[key] += 1
        else:
            deferred.append(hit)
    return tuple((selected + deferred)[:limit])
