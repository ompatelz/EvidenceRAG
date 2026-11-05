"""Offline deterministic reranking behavior, including provenance and fallback."""

import time
from collections.abc import Sequence
from types import SimpleNamespace

import pytest

from evidence_rag.evidence import AnchorPrecision, ElementType, EvidenceUnit, RepresentationVersions
from evidence_rag.retrieval.hybrid import HybridHit
from evidence_rag.retrieval.rerank import (
    MODEL_NAME,
    MODEL_REVISION,
    FastEmbedCrossEncoder,
    OptionalReranker,
    RerankConfig,
)

VERSION = "sha256:" + "a" * 64
SCOPE = [("doc_a", VERSION)]


def unit(identifier: str, text: str, *, version: str = VERSION) -> EvidenceUnit:
    return EvidenceUnit(
        evidence_id=identifier,
        document_id="doc_a",
        document_sha256=version[7:],
        document_version=version,
        page_index=0,
        element_type=ElementType.TEXT,
        text=text,
        anchor_precision=AnchorPrecision.PAGE,
        versions=RepresentationVersions(parser="test", representation="test"),
    )


def hit(identifier: str, rank: int, *, version: str = VERSION) -> HybridHit:
    return HybridHit(
        identifier,
        "doc_a",
        version,
        0,
        rank,
        1 / (60 + rank),
        "page",
        None,
        rank,
        float(rank),
        rank,
        float(rank),
    )


class FakeScorer:
    model_name = MODEL_NAME
    revision = MODEL_REVISION

    def __init__(self, scores: list[float], *, delay: float = 0, fail: bool = False) -> None:
        self.scores = scores
        self.delay = delay
        self.fail = fail
        self.calls: list[tuple[str, list[str], int]] = []

    def score(self, query: str, passages: Sequence[str], *, batch_size: int) -> list[float]:
        self.calls.append((query, list(passages), batch_size))
        if self.delay:
            time.sleep(self.delay)
        if self.fail:
            raise RuntimeError("scorer unavailable")
        return self.scores


def test_candidate_mapping_top_n_and_ties() -> None:
    scorer = FakeScorer([0.8, 0.8])
    reranker = OptionalReranker(scorer, RerankConfig(enabled=True, top_n=2, batch_size=2))
    try:
        result = reranker.rerank(
            "question",
            [hit("ev_b", 1), hit("ev_a", 2), hit("ev_c", 3)],
            {"ev_a": unit("ev_a", "A"), "ev_b": unit("ev_b", "B"), "ev_c": unit("ev_c", "C")},
            versions=SCOPE,
        )
    finally:
        reranker.close()
    assert scorer.calls == [("question", ["B", "A"], 2)]
    assert [item.evidence_id for item in result.hits] == ["ev_a", "ev_b", "ev_c"]
    assert [item.fusion_rank for item in result.hits] == [2, 1, 3]
    assert result.hits[2].rerank_score is None


def test_bounded_text_and_disabled_mode() -> None:
    scorer = FakeScorer([2.0])
    off = OptionalReranker(None, RerankConfig())
    assert off.rerank("ignored", [hit("ev_a", 1)], {}, versions=SCOPE).status == "disabled"
    reranker = OptionalReranker(
        scorer, RerankConfig(enabled=True, top_n=1, max_query_chars=4, max_passage_chars=5)
    )
    try:
        result = reranker.rerank(
            "question", [hit("ev_a", 1)], {"ev_a": unit("ev_a", "abcdefgh")}, versions=SCOPE
        )
    finally:
        reranker.close()
    assert result.status == "reranked"
    assert scorer.calls[0][:2] == ("ques", ["abcde"])


def test_timeout_and_failure_fallback() -> None:
    slow = FakeScorer([1.0], delay=0.05)
    reranker = OptionalReranker(slow, RerankConfig(enabled=True, timeout_ms=1))
    try:
        first = reranker.rerank("q", [hit("ev_a", 1)], {"ev_a": unit("ev_a", "A")}, versions=SCOPE)
        second = reranker.rerank("q", [hit("ev_a", 1)], {"ev_a": unit("ev_a", "A")}, versions=SCOPE)
    finally:
        reranker.close()
    assert first.status == second.status == "timeout_fallback"
    assert first.hits[0].rerank_score is None
    assert len(slow.calls) == 1
    failed = OptionalReranker(FakeScorer([1.0], fail=True), RerankConfig(enabled=True))
    try:
        result = failed.rerank("q", [hit("ev_a", 1)], {"ev_a": unit("ev_a", "A")}, versions=SCOPE)
    finally:
        failed.close()
    assert result.status == "failure_fallback"


def test_unknown_stale_and_out_of_scope_evidence_rejected() -> None:
    reranker = OptionalReranker(FakeScorer([1.0]), RerankConfig(enabled=True))
    try:
        with pytest.raises(ValueError, match="missing"):
            reranker.rerank("q", [hit("ev_a", 1)], {}, versions=SCOPE)
        stale = "sha256:" + "b" * 64
        with pytest.raises(ValueError, match="version"):
            reranker.rerank(
                "q",
                [hit("ev_a", 1)],
                {"ev_a": unit("ev_a", "A", version=stale)},
                versions=[SCOPE[0], ("doc_a", stale)],
            )
        with pytest.raises(ValueError, match="scope"):
            reranker.rerank(
                "q",
                [hit("ev_a", 1, version=stale)],
                {"ev_a": unit("ev_a", "A", version=stale)},
                versions=SCOPE,
            )
    finally:
        reranker.close()


def test_model_revision_and_invalid_scores() -> None:
    scorer = FakeScorer([float("nan")])
    scorer.revision = "wrong"
    with pytest.raises(ValueError, match="revision"):
        OptionalReranker(scorer, RerankConfig(enabled=True))
    scorer.revision = MODEL_REVISION
    reranker = OptionalReranker(scorer, RerankConfig(enabled=True))
    try:
        result = reranker.rerank("q", [hit("ev_a", 1)], {"ev_a": unit("ev_a", "A")}, versions=SCOPE)
    finally:
        reranker.close()
    assert result.status == "failure_fallback"


def test_adapter_sets_explicit_right_side_token_truncation(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastembed.rerank import cross_encoder

    settings: list[dict[str, object]] = []

    class Tokenizer:
        def enable_truncation(self, **kwargs: object) -> None:
            settings.append(kwargs)

    class Model:
        def __init__(self, **kwargs: object) -> None:
            self.model = SimpleNamespace(tokenizer=Tokenizer())

        def rerank(self, query: str, passages: Sequence[str], *, batch_size: int) -> list[float]:
            return [1.0] * len(passages)

    monkeypatch.setattr(cross_encoder, "TextCrossEncoder", Model)
    adapter = FastEmbedCrossEncoder("local", max_tokens=256)
    assert settings == [
        {"max_length": 256, "stride": 0, "strategy": "longest_first", "direction": "right"}
    ]
    assert adapter.score("q", ["passage"], batch_size=1) == [1.0]
