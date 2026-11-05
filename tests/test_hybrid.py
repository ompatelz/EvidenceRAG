"""Deterministic hand-computed fusion and failure tests; no model download."""

from dataclasses import dataclass

import pytest

from evidence_rag.retrieval.bm25 import RankedEvidence, SearchResult
from evidence_rag.retrieval.dense import DenseSearchResult
from evidence_rag.retrieval.hybrid import HybridConfig, HybridRetriever, fuse

VERSION = ("doc", "sha256:" + "a" * 64)
OLD = ("doc", "sha256:" + "b" * 64)


def hit(
    evidence_id: str, rank: int, score: float = 1.0, version: tuple[str, str] = VERSION
) -> RankedEvidence:
    return RankedEvidence(evidence_id, version[0], version[1], 0, rank, score, "page", None)


def test_hand_calculated_rrf_and_missing_candidate() -> None:
    result = fuse(
        [hit("a", 1, 9), hit("b", 2, 7)],
        [hit("b", 1, 0.8), hit("c", 2, 0.6)],
        config=HybridConfig(rrf_k=10, prefetch=2, final_k=3),
        versions=[VERSION],
    )
    assert [item.evidence_id for item in result] == ["b", "a", "c"]
    assert result[0].score == pytest.approx(1 / 12 + 1 / 11)
    assert result[0].bm25_score == 7
    assert result[0].dense_score == 0.8
    assert result[1].dense_rank is None


def test_tie_break_and_duplicate_evidence() -> None:
    result = fuse(
        [hit("z", 1), hit("a", 2), hit("z", 2)],
        [hit("a", 1), hit("z", 2)],
        config=HybridConfig(rrf_k=10, prefetch=3, final_k=2),
        versions=[VERSION],
    )
    assert [item.evidence_id for item in result] == ["a", "z"]
    assert result[1].bm25_rank == 1


def test_scope_and_provenance_fail_closed() -> None:
    config = HybridConfig(prefetch=2, final_k=2)
    with pytest.raises(ValueError, match="scope"):
        fuse([hit("a", 1, version=OLD)], [], config=config, versions=[VERSION])
    with pytest.raises(ValueError, match="provenance"):
        fuse([hit("a", 1)], [hit("a", 1, version=OLD)], config=config, versions=[VERSION, OLD])


def test_empty_results() -> None:
    assert fuse([], [], config=HybridConfig(), versions=[VERSION]) == ()


@dataclass
class FakeBM25:
    index_id: str = "bm25"

    def search(self, query: str, *, k: int, versions: list[tuple[str, str]]) -> SearchResult:
        assert k == 2 and versions == [VERSION]
        return SearchResult((hit("a", 1),), 2.0, self.index_id)


@dataclass
class FakeDense:
    index_id: str = "dense"
    fail: bool = False

    def search(self, query: str, *, k: int, versions: list[tuple[str, str]]) -> DenseSearchResult:
        if self.fail:
            raise RuntimeError("dense unavailable")
        return DenseSearchResult((hit("a", 1, 0.8),), 3.0, 4.0, self.index_id)


def test_components_and_failed_component() -> None:
    from typing import cast

    from evidence_rag.retrieval.bm25 import BM25Index
    from evidence_rag.retrieval.dense import DenseIndex

    retriever = HybridRetriever(
        cast(BM25Index, FakeBM25()),
        cast(DenseIndex, FakeDense()),
        HybridConfig(prefetch=2, final_k=2),
    )
    result = retriever.search("question", versions=[VERSION])
    assert result.hits[0].evidence_id == "a"
    assert (result.bm25_ms, result.embedding_ms, result.vector_search_ms) == (2, 3, 4)
    assert retriever.search("question", versions=[]).hits == ()
    failed = HybridRetriever(
        cast(BM25Index, FakeBM25()),
        cast(DenseIndex, FakeDense(fail=True)),
        HybridConfig(prefetch=2, final_k=2),
    )
    with pytest.raises(RuntimeError, match="unavailable"):
        failed.search("question", versions=[VERSION])
