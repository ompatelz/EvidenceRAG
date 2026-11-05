"""Optional bounded CPU cross-encoder reranking of hybrid evidence candidates."""

import math
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol, cast

from evidence_rag.evidence import EvidenceUnit
from evidence_rag.retrieval.hybrid import HybridHit

MODEL_NAME = "Xenova/ms-marco-MiniLM-L-6-v2"
MODEL_REVISION = "a09144355adeed5f58c8ed011d209bf8ee5a1fec"
RERANK_VERSION = "cross-encoder-rerank-v1"


class PairScorer(Protocol):
    model_name: str
    revision: str

    def score(self, query: str, passages: Sequence[str], *, batch_size: int) -> list[float]: ...


class FastEmbedCrossEncoder:
    """Pinned ONNX model from an explicitly populated local Hugging Face snapshot."""

    model_name = MODEL_NAME
    revision = MODEL_REVISION

    def __init__(self, model_path: str, *, max_tokens: int = 256, threads: int = 2) -> None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        self.model = TextCrossEncoder(
            model_name=self.model_name,
            specific_model_path=model_path,
            local_files_only=True,
            providers=["CPUExecutionProvider"],
            threads=threads,
        )
        # The model permits 512 positions; a smaller explicit right-side limit bounds CPU work.
        cast(Any, self.model.model).tokenizer.enable_truncation(
            max_length=max_tokens, stride=0, strategy="longest_first", direction="right"
        )
        self.max_tokens = max_tokens
        self.threads = threads

    def score(self, query: str, passages: Sequence[str], *, batch_size: int) -> list[float]:
        return [float(value) for value in self.model.rerank(query, passages, batch_size=batch_size)]


@dataclass(frozen=True)
class RerankConfig:
    enabled: bool = False
    top_n: int = 5
    batch_size: int = 4
    timeout_ms: int = 2000
    max_query_chars: int = 512
    max_passage_chars: int = 2048
    max_pair_tokens: int = 256

    def __post_init__(self) -> None:
        if not (1 <= self.top_n <= 20 and 1 <= self.batch_size <= 20):
            raise ValueError("rerank top N and batch size must be bounded")
        if self.timeout_ms < 1 or self.max_query_chars < 1 or self.max_passage_chars < 1:
            raise ValueError("rerank timeout and character limits must be positive")
        if not 8 <= self.max_pair_tokens <= 512:
            raise ValueError("pair token limit must fit the model")


@dataclass(frozen=True)
class RerankedHit:
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
    fusion_rank: int
    fusion_score: float
    rerank_score: float | None


@dataclass(frozen=True)
class RerankResult:
    hits: tuple[RerankedHit, ...]
    status: str
    rerank_ms: float


def _original(hits: Sequence[HybridHit]) -> tuple[RerankedHit, ...]:
    return tuple(
        RerankedHit(
            hit.evidence_id,
            hit.document_id,
            hit.document_version,
            hit.page_index,
            hit.rank,
            hit.score,
            hit.anchor_precision,
            hit.bbox,
            hit.bm25_rank,
            hit.bm25_score,
            hit.dense_rank,
            hit.dense_score,
            hit.rank,
            hit.score,
            None,
        )
        for hit in hits
    )


class OptionalReranker:
    """Return original hybrid ordering on a scorer failure or soft timeout."""

    def __init__(self, scorer: PairScorer | None, config: RerankConfig) -> None:
        if config.enabled and scorer is None:
            raise ValueError("enabled reranking requires a scorer")
        if scorer is not None and (scorer.model_name, scorer.revision) != (
            MODEL_NAME,
            MODEL_REVISION,
        ):
            raise ValueError("reranker model revision mismatch")
        self.scorer = scorer
        self.config = config
        self._timed_out = False
        self._pool = (
            ThreadPoolExecutor(max_workers=1, thread_name_prefix="rerank")
            if config.enabled
            else None
        )

    def close(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)

    def rerank(
        self,
        query: str,
        hits: Sequence[HybridHit],
        units: Mapping[str, EvidenceUnit],
        *,
        versions: Sequence[tuple[str, str]],
    ) -> RerankResult:
        if not self.config.enabled or not hits:
            return RerankResult(
                _original(hits), "disabled" if not self.config.enabled else "empty", 0.0
            )
        if self._timed_out:
            return RerankResult(_original(hits), "timeout_fallback", 0.0)
        selected = hits[: self.config.top_n]
        passages = []
        allowed = set(versions)
        for hit in selected:
            unit = units.get(hit.evidence_id)
            if unit is None or (unit.document_id, unit.document_version) not in allowed:
                raise ValueError("candidate evidence is missing or outside scope")
            if (unit.document_id, unit.document_version, unit.page_index) != (
                hit.document_id,
                hit.document_version,
                hit.page_index,
            ):
                raise ValueError("candidate evidence version or page mismatch")
            passages.append(unit.text[: self.config.max_passage_chars])
        assert self.scorer is not None and self._pool is not None
        started = perf_counter()
        future = self._pool.submit(
            self.scorer.score,
            query[: self.config.max_query_chars],
            passages,
            batch_size=self.config.batch_size,
        )
        try:
            scores = future.result(timeout=self.config.timeout_ms / 1000)
            if len(scores) != len(selected) or not all(math.isfinite(score) for score in scores):
                raise ValueError("reranker returned invalid scores")
        except FutureTimeout:
            self._timed_out = True
            future.cancel()
            return RerankResult(
                _original(hits), "timeout_fallback", (perf_counter() - started) * 1000
            )
        except Exception:
            return RerankResult(
                _original(hits), "failure_fallback", (perf_counter() - started) * 1000
            )
        ordered = sorted(
            zip(selected, scores, strict=True), key=lambda pair: (-pair[1], pair[0].evidence_id)
        )
        reranked = []
        for rank, (hit, score) in enumerate(ordered, 1):
            reranked.append(
                RerankedHit(
                    hit.evidence_id,
                    hit.document_id,
                    hit.document_version,
                    hit.page_index,
                    rank,
                    score,
                    hit.anchor_precision,
                    hit.bbox,
                    hit.bm25_rank,
                    hit.bm25_score,
                    hit.dense_rank,
                    hit.dense_score,
                    hit.rank,
                    hit.score,
                    score,
                )
            )
        for rank, hit in enumerate(hits[self.config.top_n :], len(reranked) + 1):
            reranked.append(
                RerankedHit(
                    hit.evidence_id,
                    hit.document_id,
                    hit.document_version,
                    hit.page_index,
                    rank,
                    hit.score,
                    hit.anchor_precision,
                    hit.bbox,
                    hit.bm25_rank,
                    hit.bm25_score,
                    hit.dense_rank,
                    hit.dense_score,
                    hit.rank,
                    hit.score,
                    None,
                )
            )
        return RerankResult(tuple(reranked), "reranked", (perf_counter() - started) * 1000)
