"""Dense index invariants with a deterministic, download-free embedder."""

import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import ResponseHandlingException

from evidence_rag.documents.models import EvidenceArtifact
from evidence_rag.documents.parser import PyMuPDFParser
from evidence_rag.documents.storage import LocalArtifactStore
from evidence_rag.eval.dense_run import run
from evidence_rag.evidence import AnchorPrecision, ElementType, EvidenceUnit, RepresentationVersions
from evidence_rag.retrieval.dense import DenseIndex, normalized


class FakeEmbedder:
    model_name = "test/fixed"
    revision = "test-rev-1"
    dimension = 2

    def encode_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.encode_query(text) for text in texts]

    def encode_query(self, query: str) -> list[float]:
        return [2.0, 0.0] if "alpha" in query else [0.0, 3.0]


def unit(
    identifier: str, text: str, *, document: str = "doc_a", version: str = "a"
) -> EvidenceUnit:
    digest = version * 64
    return EvidenceUnit(
        evidence_id=identifier,
        document_id=document,
        document_sha256=digest,
        document_version="sha256:" + digest,
        page_index=0,
        element_type=ElementType.TEXT,
        text=text,
        anchor_precision=AnchorPrecision.PAGE,
        versions=RepresentationVersions(parser="test", representation="test"),
    )


def test_normalization_rejects_dimension_nonfinite_and_zero() -> None:
    assert normalized([3.0, 4.0], 2) == pytest.approx([0.6, 0.8])
    for vector in ([1.0], [float("nan"), 1.0], [0.0, 0.0]):
        with pytest.raises(ValueError):
            normalized(vector, 2)


def test_rebuild_scoping_upsert_and_stale_deletion() -> None:
    client = QdrantClient(":memory:")
    index = DenseIndex(client, FakeEmbedder())
    old = unit("ev_old", "alpha old", version="a")
    current = unit("ev_current", "alpha current", version="b")
    other = unit("ev_other", "beta", document="doc_b", version="c")
    index.rebuild([old, current, other])
    scope = [(current.document_id, current.document_version)]
    result = index.search("alpha", versions=scope)
    assert [hit.evidence_id for hit in result.hits] == ["ev_current"]
    assert result.embedding_ms >= 0 and result.vector_search_ms >= 0
    assert index.search(" ").hits == ()
    assert index.search("alpha", versions=[]).hits == ()
    index.upsert([current, current])
    assert index.size == 3
    index.delete_version(old.document_id, old.document_version)
    assert index.size == 2
    assert "ev_old" not in [hit.evidence_id for hit in index.search("alpha").hits]
    index.rebuild([current, other])
    assert index.size == 2
    assert "ev_old" not in [hit.evidence_id for hit in index.search("alpha").hits]
    client.close()


def test_collection_dimension_and_model_mismatch() -> None:
    client = QdrantClient(":memory:")
    client.create_collection(
        "wrong_dim", vectors_config=models.VectorParams(size=3, distance=models.Distance.COSINE)
    )
    with pytest.raises(ValueError, match="dimension"):
        DenseIndex(client, FakeEmbedder(), collection="wrong_dim")
    index = DenseIndex(client, FakeEmbedder(), collection="right_dim")
    index.rebuild([unit("ev_a", "alpha")])

    class OtherRevision(FakeEmbedder):
        revision = "test-rev-2"

    with pytest.raises(ValueError, match="model version"):
        DenseIndex(client, OtherRevision(), collection="right_dim")
    client.close()


def test_failed_embedding_does_not_replace_active_generation() -> None:
    client = QdrantClient(":memory:")
    embedder = FakeEmbedder()
    index = DenseIndex(client, embedder)
    good = unit("ev_a", "alpha")
    index.rebuild([good])
    generation = index.active_generation

    class Broken(FakeEmbedder):
        def encode_documents(self, texts: Sequence[str]) -> list[list[float]]:
            return [[0.0, 0.0] for _ in texts]

    index.embedder = Broken()
    with pytest.raises(ValueError, match="nonzero norm"):
        index.rebuild([unit("ev_b", "beta")])
    assert index.active_generation == generation
    index.embedder = embedder
    assert [hit.evidence_id for hit in index.search("alpha").hits] == ["ev_a"]
    client.close()


def test_dense_uses_same_canonical_evidence_contract(tmp_path: Path) -> None:
    import io

    source = Path("datasets/fixtures/atlas-narrative.pdf")
    store = LocalArtifactStore(tmp_path, max_upload_bytes=65536, chunk_bytes=4096)
    document, _ = store.ingest(
        io.BytesIO(source.read_bytes()),
        original_filename=source.name,
        sanitized_filename=source.name,
    )
    parser = PyMuPDFParser()
    parsed = parser.parse(source, document)
    store.write_evidence(
        EvidenceArtifact(
            document_id=document.document_id,
            document_version=document.document_version,
            document_sha256=document.document_sha256,
            parser=parser.metadata,
            page_count=parsed.page_count,
            units=list(parsed.units),
            issues=list(parsed.issues),
        )
    )
    canonical = store.get_evidence(document.document_id, document.document_sha256)
    client = QdrantClient(":memory:")
    index = DenseIndex(client, FakeEmbedder())
    index.rebuild(canonical.units)
    assert {hit.evidence_id for hit in index.search("alpha").hits} == {
        unit.evidence_id for unit in canonical.units
    }
    client.close()


def test_qdrant_outage_fails_closed() -> None:
    client = QdrantClient(url="http://127.0.0.1:1", timeout=1, check_compatibility=False)
    with pytest.raises(ResponseHandlingException):
        DenseIndex(client, FakeEmbedder())
    client.close()


def test_e1_runner_rejects_e0_contract_drift_without_model_download(tmp_path: Path) -> None:
    e0 = json.loads(Path("reports/runs/e0-phase2-pilot.json").read_text(encoding="utf-8"))
    e0["config"]["cutoffs"] = [1, 2, 5]
    incompatible = tmp_path / "incompatible-e0.json"
    incompatible.write_text(json.dumps(e0), encoding="utf-8")
    with pytest.raises(ValueError, match="incompatible"):
        run(
            Path("datasets/manifests/fixtures.json"),
            Path("datasets/eval/phase2_seed.jsonl"),
            incompatible,
            tmp_path / "e1.json",
            cache_dir=tmp_path / "cache",
        )


def test_saved_e0_e1_runs_share_evaluation_contract() -> None:
    e0 = json.loads(Path("reports/runs/e0-phase2-pilot.json").read_text(encoding="utf-8"))
    e1 = json.loads(Path("reports/runs/e1-phase2-pilot.json").read_text(encoding="utf-8"))
    assert e0["dataset_sha256"] == e1["dataset_sha256"]
    assert e0["corpus_versions"] == e1["corpus_versions"]
    assert e0["config"]["cutoffs"] == e1["config"]["cutoffs"]
    assert [row["query_id"] for row in e0["queries"]] == [row["query_id"] for row in e1["queries"]]
    assert all(row["split"] != "frozen_test" for row in e1["queries"])
