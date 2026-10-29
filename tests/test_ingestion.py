"""Tests for bounded, idempotent, and failure-safe PDF intake."""

import io
import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from evidence_rag.api import create_app
from evidence_rag.config import AppSettings
from evidence_rag.documents.models import IngestionManifest
from evidence_rag.documents.storage import LocalArtifactStore, StorageError

FIXTURES = Path("datasets/fixtures")


@pytest.fixture
def atlas_pdf() -> bytes:
    return (FIXTURES / "atlas-narrative.pdf").read_bytes()


@pytest.fixture
def table_pdf() -> bytes:
    return (FIXTURES / "retrieval-table.pdf").read_bytes()


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = AppSettings(
        environment="test",
        artifact_root=tmp_path / "artifacts",
        max_upload_bytes=8 * 1024,
        multipart_overhead_bytes=64 * 1024,
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def upload(client: TestClient, content: bytes, filename: str = "atlas.pdf") -> Any:
    return client.post(
        "/api/v1/documents",
        files={"file": (filename, content, "application/pdf")},
    )


def manifests(root: Path) -> list[Path]:
    return list(root.glob("documents/doc_*/versions/*/manifest.json"))


def test_valid_owned_fixture_upload_and_safe_metadata(
    client: TestClient, atlas_pdf: bytes, tmp_path: Path
) -> None:
    response = upload(client, atlas_pdf)

    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "received"
    assert body["duplicate"] is False
    assert body["document_version"] == f"sha256:{body['document_sha256']}"
    assert body["source_asset_id"].startswith("asset:pdf:doc_")
    assert str(tmp_path.resolve()) not in response.text
    assert ":\\" not in response.text

    metadata = client.get(
        f"/api/v1/documents/{body['document_id']}/versions/{body['document_sha256']}"
    )
    status = client.get(
        f"/api/v1/documents/{body['document_id']}/versions/{body['document_sha256']}/status"
    )
    assert metadata.status_code == 200
    assert metadata.json()["document_version"] == body["document_version"]
    assert status.json() == {
        "document_id": body["document_id"],
        "document_version": body["document_version"],
        "state": "received",
    }


@pytest.mark.parametrize(
    ("content", "expected_code"),
    [
        (b"", "empty_pdf"),
        (b"%PDF-1.7\nplainly truncated", "truncated_pdf"),
        (b"this is not a PDF", "invalid_pdf_signature"),
    ],
)
def test_invalid_files_are_rejected_without_success_manifest(
    client: TestClient,
    content: bytes,
    expected_code: str,
    tmp_path: Path,
) -> None:
    response = upload(client, content, "looks-valid.pdf")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == expected_code
    assert manifests(tmp_path / "artifacts") == []


def test_unusual_and_traversal_filenames_are_sanitized_and_confined(
    client: TestClient, atlas_pdf: bytes, tmp_path: Path
) -> None:
    unusual = upload(client, atlas_pdf, r"..\..\résumé (final) #1.PDF")

    assert unusual.status_code == 201
    assert unusual.json()["sanitized_filename"] == "resume_final_1.PDF"
    root = (tmp_path / "artifacts").resolve()
    assert all(path.resolve().is_relative_to(root) for path in root.rglob("*"))
    assert not (tmp_path / "resume_final_1.PDF").exists()


def test_oversized_upload_is_rejected_and_cleaned_up(tmp_path: Path) -> None:
    settings = AppSettings(
        environment="test",
        artifact_root=tmp_path / "artifacts",
        max_upload_bytes=32,
        upload_chunk_bytes=4096,
        multipart_overhead_bytes=64 * 1024,
    )
    content = b"%PDF-1.7\n" + b"x" * 64 + b"\n%%EOF"
    with TestClient(create_app(settings)) as local_client:
        response = upload(local_client, content)

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "upload_too_large"
    assert manifests(tmp_path / "artifacts") == []
    assert list((tmp_path / "artifacts" / ".staging").glob("*")) == []


def test_raw_request_body_limit_rejects_large_multipart_before_intake(tmp_path: Path) -> None:
    settings = AppSettings(
        environment="test",
        artifact_root=tmp_path / "artifacts",
        max_upload_bytes=32,
        upload_chunk_bytes=4096,
        multipart_overhead_bytes=64 * 1024,
    )
    content = b"%PDF-1.7\n" + b"x" * (70 * 1024) + b"\n%%EOF"
    with TestClient(create_app(settings)) as local_client:
        response = upload(local_client, content)

    assert response.status_code == 413
    assert manifests(tmp_path / "artifacts") == []


def test_repeated_bytes_and_different_filenames_return_existing_version(
    client: TestClient, atlas_pdf: bytes, tmp_path: Path
) -> None:
    first = upload(client, atlas_pdf, "atlas.pdf")
    repeated = upload(client, atlas_pdf, "atlas.pdf")
    renamed = upload(client, atlas_pdf, "renamed-copy.pdf")

    assert first.status_code == 201
    assert repeated.status_code == 200
    assert renamed.status_code == 200
    assert repeated.json()["duplicate"] is True
    assert renamed.json()["duplicate"] is True
    assert {item.json()["document_id"] for item in (first, repeated, renamed)} == {
        first.json()["document_id"]
    }
    assert {item.json()["document_version"] for item in (first, repeated, renamed)} == {
        first.json()["document_version"]
    }
    assert len(manifests(tmp_path / "artifacts")) == 1


def test_changed_content_under_same_logical_name_creates_new_version(
    client: TestClient, atlas_pdf: bytes, table_pdf: bytes, tmp_path: Path
) -> None:
    first = upload(client, atlas_pdf, "report.pdf")
    changed = upload(client, table_pdf, "report.pdf")

    assert first.status_code == changed.status_code == 201
    assert first.json()["document_id"] == changed.json()["document_id"]
    assert first.json()["document_version"] != changed.json()["document_version"]
    assert len(manifests(tmp_path / "artifacts")) == 2


class InterruptedStream(io.BytesIO):
    """Test stream that simulates an interrupted client read."""

    def __init__(self, content: bytes) -> None:
        super().__init__(content)
        self._reads = 0

    def read(self, size: int | None = -1) -> bytes:
        self._reads += 1
        if self._reads > 1:
            raise OSError("simulated interruption")
        requested = -1 if size is None else size
        return super().read(16 if requested < 0 else min(requested, 16))


def test_interrupted_stream_leaves_no_manifest_or_staging_file(
    tmp_path: Path, atlas_pdf: bytes
) -> None:
    store = LocalArtifactStore(tmp_path, max_upload_bytes=8192, chunk_bytes=4096)

    with pytest.raises(OSError, match="simulated interruption"):
        store.ingest(
            InterruptedStream(atlas_pdf),
            original_filename="atlas.pdf",
            sanitized_filename="atlas.pdf",
        )

    assert manifests(tmp_path) == []
    assert list((tmp_path / ".staging").glob("*")) == []


@pytest.mark.parametrize("failed_destination", ["source.pdf", "manifest.json"])
def test_failed_artifact_or_manifest_publication_cleans_partial_version(
    tmp_path: Path, atlas_pdf: bytes, failed_destination: str
) -> None:
    def failing_replace(source: Path, destination: Path) -> None:
        if destination.name == failed_destination:
            raise OSError("simulated publication failure")
        os.replace(source, destination)

    store = LocalArtifactStore(
        tmp_path,
        max_upload_bytes=8192,
        chunk_bytes=4096,
        replace=failing_replace,
    )

    with pytest.raises(StorageError, match="could not publish"):
        store.ingest(
            io.BytesIO(atlas_pdf),
            original_filename="atlas.pdf",
            sanitized_filename="atlas.pdf",
        )

    assert manifests(tmp_path) == []
    assert list(tmp_path.glob("documents/doc_*/versions/*/source.pdf")) == []


def test_manifest_is_valid_and_published_by_atomic_replace(
    tmp_path: Path, atlas_pdf: bytes
) -> None:
    replacements: list[tuple[str, str, bool]] = []

    def recording_replace(source: Path, destination: Path) -> None:
        replacements.append((source.name, destination.name, destination.exists()))
        os.replace(source, destination)

    store = LocalArtifactStore(
        tmp_path,
        max_upload_bytes=8192,
        chunk_bytes=4096,
        replace=recording_replace,
    )
    manifest, duplicate = store.ingest(
        io.BytesIO(atlas_pdf),
        original_filename="atlas.pdf",
        sanitized_filename="atlas.pdf",
    )

    manifest_path = manifests(tmp_path)[0]
    parsed = IngestionManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert duplicate is False
    assert parsed == manifest
    assert raw["schema_version"] == 1
    manifest_replacement = next(item for item in replacements if item[1] == "manifest.json")
    assert manifest_replacement[0].startswith(".manifest-")
    assert manifest_replacement[2] is False


def test_unknown_or_path_like_identifiers_return_safe_not_found(
    client: TestClient, tmp_path: Path
) -> None:
    response = client.get("/api/v1/documents/not-valid/versions/not-a-hash")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"
    assert str(tmp_path.resolve()) not in response.text
