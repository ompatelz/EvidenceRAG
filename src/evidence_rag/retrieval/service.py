"""Shared retrieval implementation for HTTP and embedded agent clients."""

from __future__ import annotations

from collections.abc import Sequence
from time import perf_counter
from typing import TYPE_CHECKING, Literal

from evidence_rag.config import AppSettings
from evidence_rag.documents import IntakeError
from evidence_rag.documents.models import IngestionManifest
from evidence_rag.evidence import EvidenceUnit
from evidence_rag.retrieval.bm25 import BM25Index, RankedEvidence

if TYPE_CHECKING:
    from evidence_rag.retrieval.hybrid import HybridHit
    from evidence_rag.retrieval.rerank import RerankedHit

RetrievalMode = Literal["bm25", "dense", "hybrid", "reranked"]


def retrieve(
    question: str,
    mode: RetrievalMode,
    units: Sequence[EvidenceUnit],
    manifest: IngestionManifest,
    settings: AppSettings,
    lexical_index: BM25Index | None = None,
) -> tuple[Sequence[RankedEvidence | HybridHit | RerankedHit], dict[str, float], str]:
    """Retrieve five canonical units with offline-only model loading."""
    scope = [(manifest.document_id, manifest.document_version)]
    timings: dict[str, float] = {}
    retrieval_status = "ok"
    hits: Sequence[RankedEvidence | HybridHit | RerankedHit]
    if mode == "bm25":
        started = perf_counter()
        index = lexical_index or BM25Index()
        try:
            if lexical_index is None:
                index.rebuild(units)
            timings["index_build"] = (perf_counter() - started) * 1000
            ranking = index.search(question, k=5, versions=scope)
        except Exception as exc:
            raise IntakeError("retrieval_failed", "Local retrieval failed.", 503) from exc
        hits = ranking.hits
        timings["bm25"] = ranking.search_ms
    else:
        try:
            from huggingface_hub import snapshot_download
            from qdrant_client import QdrantClient

            from evidence_rag.retrieval.dense import (
                MODEL_REPOSITORY,
                MODEL_REVISION,
                DenseIndex,
                FastEmbedder,
            )
            from evidence_rag.retrieval.hybrid import HybridConfig, HybridRetriever
        except ImportError as exc:
            raise IntakeError(
                "model_unavailable", "Install the optional local dense dependencies.", 503
            ) from exc
        started = perf_counter()
        try:
            embedding_path = snapshot_download(
                repo_id=MODEL_REPOSITORY,
                revision=MODEL_REVISION,
                cache_dir=str(settings.model_cache_dir),
                local_files_only=True,
                allow_patterns=["*.json", "*.onnx", "vocab.txt"],
            )
        except Exception as exc:
            raise IntakeError(
                "model_unavailable", "The pinned embedding model is not cached locally.", 503
            ) from exc
        try:
            embedder = FastEmbedder(embedding_path)
        except Exception as exc:
            raise IntakeError(
                "model_load_failed", "The local embedding model could not load.", 503
            ) from exc
        timings["model_load"] = (perf_counter() - started) * 1000
        try:
            client = QdrantClient(":memory:")
        except Exception as exc:
            raise IntakeError("retrieval_failed", "Local retrieval failed.", 503) from exc
        try:
            started = perf_counter()
            dense = DenseIndex(client, embedder)
            dense.rebuild(units)
            timings["index_build"] = (perf_counter() - started) * 1000
            if mode == "dense":
                result = dense.search(question, k=5, versions=scope)
                hits = result.hits
                timings["embedding"] = result.embedding_ms
                timings["vector_search"] = result.vector_search_ms
            else:
                lexical = BM25Index()
                lexical.rebuild(units)
                hybrid = HybridRetriever(
                    lexical, dense, HybridConfig(rrf_k=60, prefetch=10, final_k=5)
                ).search(question, versions=scope)
                hits = hybrid.hits
                timings.update(
                    {
                        "bm25": hybrid.bm25_ms,
                        "embedding": hybrid.embedding_ms,
                        "vector_search": hybrid.vector_search_ms,
                        "fusion": hybrid.fusion_ms,
                    }
                )
                if mode == "reranked":
                    from evidence_rag.retrieval.rerank import (
                        MODEL_NAME as RERANK_MODEL_NAME,
                    )
                    from evidence_rag.retrieval.rerank import (
                        MODEL_REVISION as RERANK_MODEL_REVISION,
                    )
                    from evidence_rag.retrieval.rerank import (
                        FastEmbedCrossEncoder,
                        OptionalReranker,
                        RerankConfig,
                    )

                    started = perf_counter()
                    try:
                        rerank_path = snapshot_download(
                            repo_id=RERANK_MODEL_NAME,
                            revision=RERANK_MODEL_REVISION,
                            cache_dir=str(settings.model_cache_dir),
                            local_files_only=True,
                            allow_patterns=[
                                "config.json",
                                "tokenizer.json",
                                "tokenizer_config.json",
                                "special_tokens_map.json",
                                "vocab.txt",
                                "onnx/model.onnx",
                            ],
                        )
                        scorer = FastEmbedCrossEncoder(rerank_path)
                    except Exception as exc:
                        raise IntakeError(
                            "model_unavailable",
                            "The pinned reranker is not cached locally.",
                            503,
                        ) from exc
                    timings["rerank_model_load"] = (perf_counter() - started) * 1000
                    reranker = OptionalReranker(scorer, RerankConfig(enabled=True))
                    try:
                        reranked = reranker.rerank(
                            question,
                            hits,
                            {unit.evidence_id: unit for unit in units},
                            versions=scope,
                        )
                    finally:
                        reranker.close()
                    hits = reranked.hits
                    retrieval_status = reranked.status
                    timings["rerank"] = reranked.rerank_ms
        except IntakeError:
            raise
        except Exception as exc:
            raise IntakeError("retrieval_failed", "Local retrieval failed.", 503) from exc
        finally:
            client.close()
    return hits, timings, retrieval_status
