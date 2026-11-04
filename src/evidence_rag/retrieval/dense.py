"""Versioned dense evidence search with Qdrant and explicit embedding timing."""

import hashlib
import json
import math
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol, cast

from qdrant_client import QdrantClient, models

from evidence_rag.evidence import EvidenceUnit
from evidence_rag.retrieval.bm25 import RankedEvidence

INDEX_VERSION = "dense-evidence-v1"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REPOSITORY = "Qdrant/all-MiniLM-L6-v2-onnx"
MODEL_REVISION = "d13954661f83248295ba75c1ed411eef3b7b936e"
MODEL_DIMENSION = 384
_POINT_NAMESPACE = uuid.UUID("2130dfce-4a71-5d42-9d06-57432de87119")


class Embedder(Protocol):
    """Stable query/document encoding seam for real and test models."""

    model_name: str
    revision: str
    dimension: int

    def encode_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def encode_query(self, query: str) -> list[float]: ...


def normalized(vector: Sequence[float], dimension: int) -> list[float]:
    """Require a finite nonzero vector with the declared model dimension."""
    if len(vector) != dimension or not all(math.isfinite(value) for value in vector):
        raise ValueError("embedding dimension or values are invalid")
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude <= 0 or not math.isfinite(magnitude):
        raise ValueError("embedding vector must have finite nonzero norm")
    return [value / magnitude for value in vector]


class FastEmbedder:
    """CPU-only pinned ONNX MiniLM encoder; model files are downloaded explicitly."""

    model_name = MODEL_NAME
    revision = MODEL_REVISION
    dimension = MODEL_DIMENSION

    def __init__(self, model_path: str, *, batch_size: int = 32, threads: int = 2) -> None:
        from fastembed import TextEmbedding

        self.batch_size = batch_size
        self._model = TextEmbedding(
            model_name=self.model_name,
            specific_model_path=model_path,
            local_files_only=True,
            providers=["CPUExecutionProvider"],
            threads=threads,
        )

    def encode_documents(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._model.embed(list(texts), batch_size=self.batch_size, parallel=None)
        return [normalized(vector.tolist(), self.dimension) for vector in vectors]

    def encode_query(self, query: str) -> list[float]:
        vectors = list(self._model.query_embed(query))
        if len(vectors) != 1:
            raise ValueError("query encoder returned the wrong number of vectors")
        return normalized(vectors[0].tolist(), self.dimension)


@dataclass(frozen=True)
class DenseSearchResult:
    """Ranked evidence plus separate query-embedding and vector-search time."""

    hits: tuple[RankedEvidence, ...]
    embedding_ms: float
    vector_search_ms: float
    index_id: str


class DenseIndex:
    """One model-versioned Qdrant collection with generation-filtered publication."""

    def __init__(
        self, client: QdrantClient, embedder: Embedder, *, collection: str = "evidencerag_dense_v1"
    ) -> None:
        if embedder.dimension <= 0 or not embedder.revision or not embedder.model_name:
            raise ValueError("embedding identity is incomplete")
        self.client = client
        self.embedder = embedder
        self.collection = collection
        self.active_generation: str | None = None
        self.index_id: str | None = None
        self.size = 0
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                self.collection,
                vectors_config=models.VectorParams(
                    size=self.embedder.dimension, distance=models.Distance.COSINE
                ),
            )
            return
        info = self.client.get_collection(self.collection)
        vectors = info.config.params.vectors
        if not isinstance(vectors, models.VectorParams):
            raise ValueError("collection vector schema is incompatible")
        if vectors.size != self.embedder.dimension or vectors.distance != models.Distance.COSINE:
            raise ValueError("collection vector dimension or distance mismatch")
        points, _ = self.client.scroll(self.collection, limit=1, with_payload=True)
        if points:
            payload = points[0].payload or {}
            if (payload.get("model_name"), payload.get("model_revision")) != (
                self.embedder.model_name,
                self.embedder.revision,
            ):
                raise ValueError("collection model version mismatch")

    def rebuild(self, units: Iterable[EvidenceUnit]) -> None:
        """Publish a complete new generation, then remove older generations."""
        by_id: dict[str, EvidenceUnit] = {}
        for unit in units:
            prior = by_id.get(unit.evidence_id)
            if prior is not None and prior != unit:
                raise ValueError("conflicting evidence ID")
            by_id[unit.evidence_id] = unit
        ordered = sorted(by_id.values(), key=lambda unit: unit.evidence_id)
        identity = hashlib.sha256(
            json.dumps(
                {
                    "version": INDEX_VERSION,
                    "model": self.embedder.model_name,
                    "revision": self.embedder.revision,
                    "dimension": self.embedder.dimension,
                    "units": [unit.model_dump(mode="json") for unit in ordered],
                },
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        generation = identity[:32]
        vectors = self.embedder.encode_documents([unit.text for unit in ordered])
        if len(vectors) != len(ordered):
            raise ValueError("document encoder returned the wrong number of vectors")
        points = [
            models.PointStruct(
                id=str(uuid.uuid5(_POINT_NAMESPACE, generation + unit.evidence_id)),
                vector=normalized(vector, self.embedder.dimension),
                payload=self._payload(unit, generation),
            )
            for unit, vector in zip(ordered, vectors, strict=True)
        ]
        if points:
            self.client.upsert(self.collection, points=points, wait=True)
        self.active_generation = generation
        self.index_id = "sha256:" + identity
        self.size = len(points)
        self.client.delete(
            self.collection,
            points_selector=models.Filter(
                must_not=[
                    models.FieldCondition(
                        key="generation", match=models.MatchValue(value=generation)
                    )
                ]
            ),
            wait=True,
        )

    def upsert(self, units: Iterable[EvidenceUnit]) -> None:
        """Idempotently replace points in the active generation."""
        if self.active_generation is None:
            raise ValueError("index must be rebuilt before upsert")
        ordered = list({unit.evidence_id: unit for unit in units}.values())
        vectors = self.embedder.encode_documents([unit.text for unit in ordered])
        if len(vectors) != len(ordered):
            raise ValueError("document encoder returned the wrong number of vectors")
        points = [
            models.PointStruct(
                id=str(uuid.uuid5(_POINT_NAMESPACE, self.active_generation + unit.evidence_id)),
                vector=normalized(vector, self.embedder.dimension),
                payload=self._payload(unit, self.active_generation),
            )
            for unit, vector in zip(ordered, vectors, strict=True)
        ]
        if points:
            self.client.upsert(self.collection, points=points, wait=True)
        self.size = self.client.count(
            self.collection, count_filter=self._active_filter(), exact=True
        ).count
        self.index_id = None  # incremental changes have no complete-corpus identity

    def delete_version(self, document_id: str, document_version: str) -> None:
        """Remove one exact document/version from the active generation."""
        if self.active_generation is None:
            return
        active_conditions = self._active_filter().must
        assert isinstance(active_conditions, list)
        self.client.delete(
            self.collection,
            points_selector=models.Filter(
                must=[
                    *active_conditions,
                    models.FieldCondition(
                        key="document_id", match=models.MatchValue(value=document_id)
                    ),
                    models.FieldCondition(
                        key="document_version", match=models.MatchValue(value=document_version)
                    ),
                ]
            ),
            wait=True,
        )
        self.size = self.client.count(
            self.collection, count_filter=self._active_filter(), exact=True
        ).count
        self.index_id = None

    def search(
        self,
        query: str,
        *,
        k: int = 10,
        versions: Sequence[tuple[str, str]] | None = None,
    ) -> DenseSearchResult:
        """Filter inside Qdrant before returning model-version-checked evidence."""
        if k < 0:
            raise ValueError("k must be non-negative")
        if (
            self.active_generation is None
            or self.size == 0
            or k == 0
            or not query.strip()
            or versions == []
        ):
            return DenseSearchResult((), 0.0, 0.0, self.index_id or "unbuilt")
        started = perf_counter()
        vector = normalized(self.embedder.encode_query(query), self.embedder.dimension)
        embedding_ms = (perf_counter() - started) * 1000
        query_filter = self._active_filter(versions)
        started = perf_counter()
        points = self.client.query_points(
            self.collection,
            query=vector,
            query_filter=query_filter,
            limit=k,
            with_payload=True,
        ).points
        vector_search_ms = (perf_counter() - started) * 1000
        hits = []
        for rank, point in enumerate(points, 1):
            payload = point.payload or {}
            if (
                payload.get("model_name"),
                payload.get("model_revision"),
                payload.get("generation"),
            ) != (self.embedder.model_name, self.embedder.revision, self.active_generation):
                raise ValueError("returned vector has incompatible model provenance")
            hits.append(
                RankedEvidence(
                    evidence_id=str(payload["evidence_id"]),
                    document_id=str(payload["document_id"]),
                    document_version=str(payload["document_version"]),
                    page_index=int(payload["page_index"]),
                    rank=rank,
                    score=point.score,
                    anchor_precision=str(payload["anchor_precision"]),
                    bbox=payload.get("bbox"),
                )
            )
        return DenseSearchResult(
            tuple(hits), embedding_ms, vector_search_ms, self.index_id or "incremental"
        )

    def _active_filter(self, versions: Sequence[tuple[str, str]] | None = None) -> models.Filter:
        if self.active_generation is None:
            raise ValueError("no active index generation")
        must = [
            models.FieldCondition(
                key="generation", match=models.MatchValue(value=self.active_generation)
            ),
            models.FieldCondition(
                key="model_revision", match=models.MatchValue(value=self.embedder.revision)
            ),
        ]
        should = (
            None
            if versions is None
            else [
                models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id", match=models.MatchValue(value=document_id)
                        ),
                        models.FieldCondition(
                            key="document_version", match=models.MatchValue(value=document_version)
                        ),
                    ]
                )
                for document_id, document_version in versions
            ]
        )
        return models.Filter(must=cast(Any, must), should=cast(Any, should))

    def _payload(self, unit: EvidenceUnit, generation: str) -> dict[str, object]:
        return {
            "evidence_id": unit.evidence_id,
            "document_id": unit.document_id,
            "document_version": unit.document_version,
            "page_index": unit.page_index,
            "anchor_precision": unit.anchor_precision.value,
            "bbox": unit.bbox.model_dump() if unit.bbox else None,
            "model_name": self.embedder.model_name,
            "model_revision": self.embedder.revision,
            "index_version": INDEX_VERSION,
            "generation": generation,
        }
