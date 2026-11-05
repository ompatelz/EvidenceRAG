"""Deterministic full inspector flow with local pages and fake model adapters."""

from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from evidence_rag.api import create_app
from evidence_rag.config import AppSettings
from evidence_rag.documents.models import EvidenceArtifact
from evidence_rag.documents.storage import LocalArtifactStore
from evidence_rag.evidence import AnchorPrecision
from evidence_rag.retrieval import dense, rerank

QUESTION = "What is the calibration sampling rate of the Atlas sensor?"


@pytest.fixture
def workspace(tmp_path: Path) -> Iterator[tuple[TestClient, dict[str, Any], Path]]:
    settings = AppSettings(
        environment="test",
        artifact_root=tmp_path / "artifacts",
        model_cache_dir=tmp_path / "models",
        demo_answers=True,
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/v1/ingestions",
            files={
                "file": (
                    "atlas-narrative.pdf",
                    Path("datasets/fixtures/atlas-narrative.pdf").read_bytes(),
                    "application/pdf",
                )
            },
        )
        assert response.status_code == 201
        yield client, response.json(), tmp_path


def query_payload(
    document: dict[str, Any], *, question: str = QUESTION, mode: str = "bm25"
) -> dict[str, str]:
    return {
        "question": question,
        "mode": mode,
        "document_id": document["document_id"],
        "document_sha256": document["document_sha256"],
    }


def test_inspector_assets_and_citation_navigation(
    workspace: tuple[TestClient, dict[str, Any], Path],
) -> None:
    client, document, _ = workspace
    assert client.get("/inspector").status_code == 200
    html = client.get("/inspector").text
    assert 'id="question"' in html and 'id="region-overlay"' in html
    assert client.get("/inspector/app.css").status_code == 200
    script = client.get("/inspector/app.js")
    assert script.status_code == 200
    assert "Page-level citation" in script.text
    assert "image content not interpreted" in script.text
    assert client.get("/api/v1/capabilities").json()["fixture_demo_answers"] is True

    response = client.post("/api/v1/query", json=query_payload(document))
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["status"] == "answered"
    assert body["mode"] == "bm25" and body["timings_ms"]["total"] >= 0
    citation = body["result"]["claims"][0]["citations"][0]
    base = f"/api/v1/documents/{document['document_id']}/versions/{document['document_sha256']}"
    anchor = client.get(f"{base}/evidence/{citation['evidence_id']}/anchor").json()
    assert anchor["page_index"] == citation["page_index"]
    assert anchor["preview_asset_id"] == citation["preview_asset_id"]
    page = client.get(f"{base}/pages/{anchor['page_index']}/preview")
    assert page.status_code == 200 and page.content.startswith(b"\x89PNG")


class FakeEmbedder:
    model_name = "test/cpu"
    revision = "fixed"
    dimension = 2

    def __init__(self, path: str) -> None:
        self.path = path

    def encode_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0, 0.0] if "20 hertz" in text else [0.0, 1.0] for text in texts]

    def encode_query(self, query: str) -> list[float]:
        return [1.0, 0.0]


class FakeCrossEncoder:
    model_name = rerank.MODEL_NAME
    revision = rerank.MODEL_REVISION

    def __init__(self, path: str) -> None:
        self.path = path

    def score(self, query: str, passages: Sequence[str], *, batch_size: int) -> list[float]:
        return [1.0 if "20 hertz" in text else 0.0 for text in passages]


@pytest.mark.parametrize("mode", ["dense", "hybrid", "reranked"])
def test_search_modes_with_deterministic_model_doubles(
    workspace: tuple[TestClient, dict[str, Any], Path],
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    client, document, _ = workspace
    monkeypatch.setattr("huggingface_hub.snapshot_download", lambda **kwargs: "cached-model")
    monkeypatch.setattr(dense, "FastEmbedder", FakeEmbedder)
    monkeypatch.setattr(rerank, "FastEmbedCrossEncoder", FakeCrossEncoder)
    response = client.post("/api/v1/query", json=query_payload(document, mode=mode))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == mode
    assert body["retrieval"]
    assert all(hit["document_version"] == document["document_version"] for hit in body["retrieval"])
    assert body["timings_ms"]["embedding"] >= 0
    if mode != "dense":
        assert "fusion" in body["timings_ms"]
    if mode == "reranked":
        assert body["retrieval_status"] == "reranked"
        assert "rerank" in body["timings_ms"]
        assert "rerank_model_load" in body["timings_ms"]


def test_unavailable_model_stale_version_and_wrong_document(
    workspace: tuple[TestClient, dict[str, Any], Path],
) -> None:
    client, document, _ = workspace
    missing = client.post("/api/v1/query", json=query_payload(document, mode="dense"))
    assert missing.status_code == 503
    assert missing.json()["error"]["code"] == "model_unavailable"
    stale = query_payload(document)
    stale["document_sha256"] = "b" * 64
    assert client.post("/api/v1/query", json=stale).status_code == 404
    wrong = query_payload(document)
    wrong["document_id"] = "doc_other"
    assert client.post("/api/v1/query", json=wrong).status_code == 404


def test_page_only_anchor_and_unsupported_caption_question(
    workspace: tuple[TestClient, dict[str, Any], Path],
) -> None:
    client, document, root = workspace
    store = LocalArtifactStore(
        root / "artifacts", max_upload_bytes=64 * 1024 * 1024, chunk_bytes=64 * 1024
    )
    artifact = store.get_evidence(document["document_id"], document["document_sha256"])
    first = artifact.units[0]
    page_only = first.model_copy(
        update={
            "anchor_precision": AnchorPrecision.PAGE,
            "bbox": None,
            "coordinate_system": None,
            "source_region": None,
        }
    )
    store.write_evidence(
        EvidenceArtifact.model_validate(
            artifact.model_copy(update={"units": [page_only, *artifact.units[1:]]}).model_dump()
        )
    )
    base = f"/api/v1/documents/{document['document_id']}/versions/{document['document_sha256']}"
    anchor = client.get(f"{base}/evidence/{first.evidence_id}/anchor")
    assert anchor.status_code == 200
    assert anchor.json()["precision"] == "page"
    assert anchor.json()["display_bbox"] is None
    question = client.post(
        "/api/v1/query",
        json=query_payload(document, question="What do the Atlas diagram shapes visually prove?"),
    )
    assert question.status_code == 200
    assert question.json()["result"]["status"] == "insufficient_evidence"
    assert "visual" not in str(question.json()["result"]["answer"] or "").lower()
    caption = client.post(
        "/api/v1/query",
        json=query_payload(
            document, question="What does Figure 1 caption say about the data flow?"
        ),
    )
    assert caption.status_code == 200
    units = store.get_evidence(document["document_id"], document["document_sha256"])
    by_id = {unit.evidence_id: unit for unit in units.units}
    assert any(
        by_id[hit["evidence_id"]].element_type == "caption" for hit in caption.json()["retrieval"]
    )
    assert caption.json()["result"]["status"] == "insufficient_evidence"
