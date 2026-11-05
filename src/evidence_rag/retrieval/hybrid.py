"""Versioned reciprocal rank fusion of scoped canonical evidence rankings."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from time import perf_counter

from evidence_rag.retrieval.bm25 import BM25Index, RankedEvidence
from evidence_rag.retrieval.dense import DenseIndex

FUSION_VERSION = "rrf-evidence-v1"


@dataclass(frozen=True)
class HybridConfig:
    rrf_k: int = 60
    prefetch: int = 20
    final_k: int = 5

    def __post_init__(self) -> None:
        if self.rrf_k < 1 or self.prefetch < 1 or self.final_k < 1:
            raise ValueError("fusion depths and constant must be positive")
        if self.final_k > self.prefetch * 2:
            raise ValueError("final K cannot exceed the union of prefetched candidates")


@dataclass(frozen=True)
class HybridHit:
    evidence_id: str
    document_id: str
    document_version: str
    page_index: int
    rank: int
    score: float
    anchor_precision: str
    bbox: dict[str, float] | None
    bm25_rank: int | None
    bm25_score: float | None
    dense_rank: int | None
    dense_score: float | None


@dataclass(frozen=True)
class HybridResult:
    hits: tuple[HybridHit, ...]
    bm25_ms: float
    embedding_ms: float
    vector_search_ms: float
    fusion_ms: float
    bm25_index_id: str
    dense_index_id: str


def fuse(
    lexical: Sequence[RankedEvidence],
    dense: Sequence[RankedEvidence],
    *,
    config: HybridConfig,
    versions: Sequence[tuple[str, str]],
) -> tuple[HybridHit, ...]:
    """Fuse by canonical ID; duplicate occurrences use the best rank per method."""
    allowed = set(versions)
    by_id: dict[str, dict[str, RankedEvidence]] = {}
    for method, ranking in (("bm25", lexical), ("dense", dense)):
        for hit in ranking:
            if (hit.document_id, hit.document_version) not in allowed:
                raise ValueError("retriever returned evidence outside the requested scope")
            if hit.rank < 1 or hit.rank > config.prefetch or not math.isfinite(hit.score):
                raise ValueError("retriever returned an invalid rank or score")
            methods = by_id.setdefault(hit.evidence_id, {})
            for previous in methods.values():
                if (
                    previous.document_id,
                    previous.document_version,
                    previous.page_index,
                    previous.anchor_precision,
                    previous.bbox,
                ) != (
                    hit.document_id,
                    hit.document_version,
                    hit.page_index,
                    hit.anchor_precision,
                    hit.bbox,
                ):
                    raise ValueError("conflicting provenance for one evidence ID")
            if method not in methods or hit.rank < methods[method].rank:
                methods[method] = hit
    scored = []
    for evidence_id, methods in by_id.items():
        lexical_hit = methods.get("bm25")
        dense_hit = methods.get("dense")
        source = lexical_hit or dense_hit
        assert source is not None
        score = sum(1 / (config.rrf_k + hit.rank) for hit in methods.values())
        scored.append((score, evidence_id, source, lexical_hit, dense_hit))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return tuple(
        HybridHit(
            evidence_id=evidence_id,
            document_id=source.document_id,
            document_version=source.document_version,
            page_index=source.page_index,
            rank=rank,
            score=score,
            anchor_precision=source.anchor_precision,
            bbox=source.bbox,
            bm25_rank=lexical_hit.rank if lexical_hit else None,
            bm25_score=lexical_hit.score if lexical_hit else None,
            dense_rank=dense_hit.rank if dense_hit else None,
            dense_score=dense_hit.score if dense_hit else None,
        )
        for rank, (score, evidence_id, source, lexical_hit, dense_hit) in enumerate(
            scored[: config.final_k], 1
        )
    )


class HybridRetriever:
    def __init__(self, bm25: BM25Index, dense: DenseIndex, config: HybridConfig) -> None:
        self.bm25 = bm25
        self.dense = dense
        self.config = config

    def search(self, query: str, *, versions: Sequence[tuple[str, str]]) -> HybridResult:
        """Both components must succeed; scope is mandatory and passed into each index."""
        if not versions or not query.strip():
            return HybridResult(
                (), 0, 0, 0, 0, self.bm25.index_id, self.dense.index_id or "unbuilt"
            )
        lexical = self.bm25.search(query, k=self.config.prefetch, versions=versions)
        dense = self.dense.search(query, k=self.config.prefetch, versions=versions)
        started = perf_counter()
        hits = fuse(lexical.hits, dense.hits, config=self.config, versions=versions)
        fusion_ms = (perf_counter() - started) * 1000
        return HybridResult(
            hits,
            lexical.search_ms,
            dense.embedding_ms,
            dense.vector_search_ms,
            fusion_ms,
            lexical.index_id,
            dense.index_id,
        )
