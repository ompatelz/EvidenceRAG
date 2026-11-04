"""Bounded live Qdrant server smoke test; enabled only with QDRANT_URL."""

import os
import uuid
from collections.abc import Sequence

import pytest
from qdrant_client import QdrantClient

from evidence_rag.evidence import AnchorPrecision, ElementType, EvidenceUnit, RepresentationVersions
from evidence_rag.retrieval.dense import DenseIndex


class FixedEmbedding:
    model_name = "test/fixed-server"
    revision = "v1"
    dimension = 2

    def encode_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.encode_query(text) for text in texts]

    def encode_query(self, query: str) -> list[float]:
        return [1.0, 0.0] if "alpha" in query else [0.0, 1.0]


@pytest.mark.skipif(not os.getenv("QDRANT_URL"), reason="live Qdrant URL is not configured")
def test_live_qdrant_scope_upsert_rebuild_and_delete() -> None:
    url = os.environ["QDRANT_URL"]
    client = QdrantClient(url=url, timeout=3)
    collection = "evidencerag_ci_" + uuid.uuid4().hex[:12]
    try:
        index = DenseIndex(client, FixedEmbedding(), collection=collection)
        units = [
            EvidenceUnit(
                evidence_id="ev_alpha",
                document_id="doc_a",
                document_sha256="a" * 64,
                document_version="sha256:" + "a" * 64,
                page_index=0,
                element_type=ElementType.TEXT,
                text="alpha",
                anchor_precision=AnchorPrecision.PAGE,
                versions=RepresentationVersions(parser="test", representation="test"),
            ),
            EvidenceUnit(
                evidence_id="ev_beta",
                document_id="doc_b",
                document_sha256="b" * 64,
                document_version="sha256:" + "b" * 64,
                page_index=0,
                element_type=ElementType.TEXT,
                text="beta",
                anchor_precision=AnchorPrecision.PAGE,
                versions=RepresentationVersions(parser="test", representation="test"),
            ),
        ]
        index.rebuild(units)
        index.upsert([units[0], units[0]])
        assert index.size == 2
        assert [
            hit.evidence_id
            for hit in index.search("alpha", versions=[("doc_a", units[0].document_version)]).hits
        ] == ["ev_alpha"]
        index.delete_version("doc_a", units[0].document_version)
        assert "ev_alpha" not in [hit.evidence_id for hit in index.search("alpha").hits]
        index.rebuild([units[1]])
        assert index.size == 1
    finally:
        if client.collection_exists(collection):
            client.delete_collection(collection)
        client.close()
