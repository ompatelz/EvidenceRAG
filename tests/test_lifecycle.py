"""End-to-end tests for the reliable synchronous ingestion lifecycle."""

import io
import json
import logging
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pymupdf
import pytest
from fastapi.testclient import TestClient

from evidence_rag.api import create_app
from evidence_rag.config import AppSettings
from evidence_rag.documents.errors import IntakeError
from evidence_rag.documents.lifecycle import (
    IngestionMode,
    LifecycleTransitionError,
    assert_transition,
)
from evidence_rag.documents.models import (
    IngestionManifest,
    IngestionStage,
    IngestionState,
    PagePreviewManifest,
    ParserMetadata,
    RendererMetadata,
)
from evidence_rag.documents.orchestration import DocumentIngestionService
from evidence_rag.documents.parser import ParserError, ParseResult, PdfParser, PyMuPDFParser
from evidence_rag.documents.rendering import (
    PageRenderer,
    PyMuPDFPageRenderer,
    RenderError,
)
from evidence_rag.documents.storage import LocalArtifactStore, StorageError

FIXTURES = Path("datasets/fixtures")


@pytest.fixture
def lifecycle_client(tmp_path: Path) -> Iterator[TestClient]:
    settings = AppSettings(
        environment="test",
        artifact_root=tmp_path / "artifacts",
        max_upload_bytes=64 * 1024,
        multipart_overhead_bytes=64 * 1024,
        max_pdf_pages=10,
        render_dpi=72,
    )
    with TestClient(create_app(settings)) as client:
        yield client


def ingest_upload(client: TestClient, content: bytes, filename: str = "fixture.pdf") -> Any:
    return client.post(
        "/api/v1/ingestions",
        files={"file": (filename, content, "application/pdf")},
    )


def version_url(body: dict[str, Any]) -> str:
    return f"/api/v1/documents/{body['document_id']}/versions/{body['document_sha256']}"


def make_pdf(
    text: str | None = "Lifecycle evidence", *, rotation: int = 0, pages: int = 1
) -> bytes:
    document = pymupdf.open()  # type: ignore[no-untyped-call]
    for _ in range(pages):
        page = document.new_page(width=200, height=100)
        if text is not None:
            page.insert_text((20, 30), text)
        page.set_rotation(rotation)  # type: ignore[no-untyped-call]
    data: bytes = document.tobytes()  # type: ignore[no-untyped-call]
    document.close()  # type: ignore[no-untyped-call]
    return data


def persisted_manifest(store: LocalArtifactStore, content: bytes) -> IngestionManifest:
    manifest, duplicate = store.ingest(
        io.BytesIO(content),
        original_filename="fixture.pdf",
        sanitized_filename="fixture.pdf",
    )
    assert duplicate is False
    return manifest


def service(store: LocalArtifactStore) -> DocumentIngestionService:
    return DocumentIngestionService(
        store,
        PyMuPDFParser(max_pages=10),
        PyMuPDFPageRenderer(dpi=72, max_pages=10),
    )


def test_successful_owned_fixture_end_to_end(lifecycle_client: TestClient) -> None:
    response = ingest_upload(
        lifecycle_client,
        (FIXTURES / "retrieval-table.pdf").read_bytes(),
        "retrieval-table.pdf",
    )
    body = response.json()
    base = version_url(body)
    evidence = lifecycle_client.get(base + "/evidence")
    pages = lifecycle_client.get(base + "/pages")
    status = lifecycle_client.get(base + "/ingestion")

    assert response.status_code == 201
    assert response.headers["x-request-id"] == body["last_request_id"]
    assert body["state"] == "ready"
    assert body["attempt_count"] == 1
    assert body["evidence_count"] == len(evidence.json()["units"])
    assert body["page_count"] == len(pages.json()["pages"]) == 1
    assert [item["stage"] for item in body["stage_timings"]] == [
        "validation",
        "parsing",
        "rendering",
        "persistence",
        "total",
    ]
    assert all(item["duration_ms"] >= 0 for item in body["stage_timings"])
    assert body["ready_at"] is not None
    assert status.json() == {key: value for key, value in body.items() if key != "duplicate"}
    assert evidence.json()["document_version"] == pages.json()["document_version"]
    assert evidence.json()["page_count"] == len(pages.json()["pages"])


def test_duplicate_upload_is_idempotent_without_new_attempt(
    lifecycle_client: TestClient,
) -> None:
    content = (FIXTURES / "atlas-narrative.pdf").read_bytes()
    first = ingest_upload(lifecycle_client, content, "atlas.pdf")
    first_evidence = lifecycle_client.get(version_url(first.json()) + "/evidence").json()
    repeated = ingest_upload(lifecycle_client, content, "renamed.pdf")
    repeated_evidence = lifecycle_client.get(version_url(repeated.json()) + "/evidence").json()

    assert first.status_code == 201
    assert repeated.status_code == 200
    assert repeated.json()["duplicate"] is True
    assert repeated.json()["state"] == "ready"
    assert repeated.json()["attempt_count"] == 1
    assert [unit["evidence_id"] for unit in first_evidence["units"]] == [
        unit["evidence_id"] for unit in repeated_evidence["units"]
    ]


def test_changed_content_creates_separate_ready_version(
    lifecycle_client: TestClient,
) -> None:
    first = ingest_upload(
        lifecycle_client,
        (FIXTURES / "atlas-narrative.pdf").read_bytes(),
        "report.pdf",
    )
    changed = ingest_upload(
        lifecycle_client,
        (FIXTURES / "retrieval-table.pdf").read_bytes(),
        "report.pdf",
    )

    assert first.status_code == changed.status_code == 201
    assert first.json()["state"] == changed.json()["state"] == "ready"
    assert first.json()["document_id"] == changed.json()["document_id"]
    assert first.json()["document_version"] != changed.json()["document_version"]


def test_reindex_replaces_stale_artifacts_without_duplicate_evidence(
    lifecycle_client: TestClient,
) -> None:
    first = ingest_upload(lifecycle_client, make_pdf(), "reindex.pdf")
    base = version_url(first.json())
    before = lifecycle_client.get(base + "/evidence").json()
    store = cast(Any, lifecycle_client.app).state.ingestion_service.store
    pages = store.get_page_manifest(first.json()["document_id"], first.json()["document_sha256"])
    preview = store.preview_path(first.json()["document_id"], first.json()["document_sha256"], 0)
    stale = preview.parent / "stale-page.png"
    stale.write_bytes(b"stale")

    reindexed = lifecycle_client.post(base + "/reindex")
    after = lifecycle_client.get(base + "/evidence").json()
    refreshed_pages = lifecycle_client.get(base + "/pages").json()

    assert reindexed.status_code == 200
    assert reindexed.json()["state"] == "ready"
    assert reindexed.json()["attempt_count"] == 2
    assert [unit["evidence_id"] for unit in before["units"]] == [
        unit["evidence_id"] for unit in after["units"]
    ]
    assert len({unit["evidence_id"] for unit in after["units"]}) == len(after["units"])
    assert len(refreshed_pages["pages"]) == len(pages.pages)
    assert not stale.exists()


class FlakyParser(PdfParser):
    def __init__(self, store: LocalArtifactStore) -> None:
        self.store = store
        self.delegate = PyMuPDFParser(max_pages=10)
        self.calls = 0
        self.observed_states: list[IngestionState] = []

    @property
    def metadata(self) -> ParserMetadata:
        return self.delegate.metadata

    def parse(self, path: Path, manifest: IngestionManifest) -> ParseResult:
        current = self.store.get_manifest(manifest.document_id, manifest.document_sha256)
        self.observed_states.append(current.state)
        self.calls += 1
        if self.calls == 1:
            raise ParserError("fixture_parser_failed", "Fixture parser failed safely.")
        return self.delegate.parse(path, manifest)


class FlakyRenderer(PageRenderer):
    def __init__(self) -> None:
        self.delegate = PyMuPDFPageRenderer(dpi=72, max_pages=10)
        self.calls = 0

    @property
    def metadata(self) -> RendererMetadata:
        return self.delegate.metadata

    def render(
        self, source: Path, manifest: IngestionManifest, destination: Path
    ) -> PagePreviewManifest:
        self.calls += 1
        if self.calls == 1:
            destination.mkdir(parents=True, exist_ok=False)
            (destination / "partial.png").write_bytes(b"partial")
            raise RenderError("fixture_renderer_failed", "Fixture renderer failed safely.")
        return self.delegate.render(source, manifest, destination)


def test_retry_after_parser_failure_reaches_ready_without_duplicates(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path, max_upload_bytes=64 * 1024, chunk_bytes=4096)
    manifest = persisted_manifest(store, make_pdf())
    parser = FlakyParser(store)
    ingestion = DocumentIngestionService(store, parser, PyMuPDFPageRenderer(dpi=72, max_pages=10))

    failed = ingestion.ingest(
        manifest.document_id, manifest.document_sha256, request_id="req_first"
    )
    ready = ingestion.ingest(
        manifest.document_id,
        manifest.document_sha256,
        request_id="req_retry",
        mode=IngestionMode.RETRY,
    )

    assert failed.state is IngestionState.FAILED
    assert failed.failure_reason == "fixture_parser_failed"
    assert ready.state is IngestionState.READY
    assert ready.attempt_count == 2
    assert parser.observed_states == [IngestionState.PARSING, IngestionState.PARSING]
    evidence = store.get_evidence(manifest.document_id, manifest.document_sha256)
    assert len({unit.evidence_id for unit in evidence.units}) == len(evidence.units)
    with pytest.raises(IntakeError, match="already ready"):
        ingestion.ingest(
            manifest.document_id,
            manifest.document_sha256,
            request_id="req_extra",
            mode=IngestionMode.RETRY,
        )


def test_retry_after_renderer_failure_cleans_partial_stage(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path, max_upload_bytes=64 * 1024, chunk_bytes=4096)
    manifest = persisted_manifest(store, make_pdf())
    renderer = FlakyRenderer()
    ingestion = DocumentIngestionService(store, PyMuPDFParser(max_pages=10), renderer)

    failed = ingestion.ingest(
        manifest.document_id, manifest.document_sha256, request_id="req_first"
    )
    version_dir = (
        tmp_path / "documents" / manifest.document_id / "versions" / (manifest.document_sha256)
    )
    assert failed.state is IngestionState.FAILED
    assert failed.failure_reason == "fixture_renderer_failed"
    assert not (version_dir / "evidence.json").exists()
    assert not (version_dir / "pages").exists()
    assert not list(version_dir.glob(".render-*"))

    ready = ingestion.ingest(
        manifest.document_id,
        manifest.document_sha256,
        request_id="req_retry",
        mode=IngestionMode.RETRY,
    )
    assert ready.state is IngestionState.READY
    assert ready.attempt_count == 2


class EvidenceFailingStore(LocalArtifactStore):
    def write_evidence(self, artifact: Any) -> None:
        raise StorageError("simulated evidence failure")


def test_evidence_persistence_failure_never_becomes_ready(tmp_path: Path) -> None:
    store = EvidenceFailingStore(tmp_path, max_upload_bytes=64 * 1024, chunk_bytes=4096)
    manifest = persisted_manifest(store, make_pdf())
    ingestion = service(store)

    with pytest.raises(IntakeError) as error:
        ingestion.ingest(manifest.document_id, manifest.document_sha256, request_id="req_persist")

    assert error.value.code == "artifact_persistence_failed"
    current = store.get_manifest(manifest.document_id, manifest.document_sha256)
    assert current.state is IngestionState.FAILED
    assert current.failure_stage is IngestionStage.PERSISTENCE
    with pytest.raises(LookupError):
        store.get_evidence(manifest.document_id, manifest.document_sha256)
    with pytest.raises(LookupError):
        store.get_page_manifest(manifest.document_id, manifest.document_sha256)


class ManifestFailingStore(LocalArtifactStore):
    failed_once = False

    def update_manifest(self, manifest: IngestionManifest) -> None:
        if manifest.state is IngestionState.PERSISTING and not self.failed_once:
            self.failed_once = True
            raise StorageError("simulated persisting manifest failure")
        super().update_manifest(manifest)


def test_persisting_manifest_failure_is_recorded_without_false_ready(tmp_path: Path) -> None:
    store = ManifestFailingStore(tmp_path, max_upload_bytes=64 * 1024, chunk_bytes=4096)
    manifest = persisted_manifest(store, make_pdf())

    with pytest.raises(IntakeError) as error:
        service(store).ingest(
            manifest.document_id,
            manifest.document_sha256,
            request_id="req_manifest",
        )

    assert error.value.code == "artifact_persistence_failed"
    current = store.get_manifest(manifest.document_id, manifest.document_sha256)
    assert current.state is IngestionState.FAILED
    assert current.failure_stage is IngestionStage.PERSISTENCE
    with pytest.raises(LookupError):
        store.get_evidence(manifest.document_id, manifest.document_sha256)
    with pytest.raises(LookupError):
        store.get_page_manifest(manifest.document_id, manifest.document_sha256)


def test_final_manifest_failure_cleans_committed_derived_artifacts(tmp_path: Path) -> None:
    failed_once = False

    def fail_ready_manifest(source: Path, destination: Path) -> None:
        nonlocal failed_once
        if destination.name == "manifest.json" and not failed_once:
            payload = source.read_text(encoding="utf-8")
            if '"state": "ready"' in payload:
                failed_once = True
                raise OSError("simulated final manifest failure")
        os.replace(source, destination)

    store = LocalArtifactStore(
        tmp_path,
        max_upload_bytes=64 * 1024,
        chunk_bytes=4096,
        replace=fail_ready_manifest,
    )
    manifest = persisted_manifest(store, make_pdf())

    with pytest.raises(IntakeError) as error:
        service(store).ingest(
            manifest.document_id, manifest.document_sha256, request_id="req_final"
        )

    assert error.value.code == "final_manifest_failed"
    current = store.get_manifest(manifest.document_id, manifest.document_sha256)
    assert current.state is IngestionState.FAILED
    assert not (
        tmp_path
        / "documents"
        / manifest.document_id
        / "versions"
        / (manifest.document_sha256)
        / "evidence.json"
    ).exists()
    with pytest.raises(LookupError):
        store.get_page_manifest(manifest.document_id, manifest.document_sha256)


def test_missing_manifest_recovers_from_intake_snapshot(
    lifecycle_client: TestClient, tmp_path: Path
) -> None:
    content = make_pdf("Recover manifest")
    first = ingest_upload(lifecycle_client, content, "recover.pdf")
    body = first.json()
    version_dir = (
        tmp_path
        / "artifacts"
        / "documents"
        / body["document_id"]
        / "versions"
        / (body["document_sha256"])
    )
    (version_dir / "manifest.json").unlink()

    recovered = ingest_upload(lifecycle_client, content, "recover.pdf")

    assert recovered.status_code == 200
    assert recovered.json()["duplicate"] is True
    assert recovered.json()["state"] == "ready"
    assert (version_dir / "manifest.json").is_file()
    assert (version_dir / "intake.json").is_file()


def test_missing_ready_page_is_rebuilt_on_duplicate_upload(
    lifecycle_client: TestClient,
) -> None:
    content = make_pdf("Recover preview")
    first = ingest_upload(lifecycle_client, content, "recover-page.pdf")
    body = first.json()
    store = cast(Any, lifecycle_client.app).state.ingestion_service.store
    store.preview_path(body["document_id"], body["document_sha256"], 0).unlink()

    recovered = ingest_upload(lifecycle_client, content, "recover-page.pdf")

    assert recovered.status_code == 200
    assert recovered.json()["state"] == "ready"
    assert recovered.json()["attempt_count"] == 2
    assert store.preview_path(body["document_id"], body["document_sha256"], 0).is_file()


def test_corrupt_pdf_and_empty_page_never_become_ready(
    lifecycle_client: TestClient,
) -> None:
    corrupt = ingest_upload(
        lifecycle_client,
        b"%PDF-1.7\nnot structurally valid\n%%EOF",
        "corrupt.pdf",
    )
    blank = ingest_upload(lifecycle_client, make_pdf(None), "blank.pdf")

    assert corrupt.status_code == blank.status_code == 422
    assert corrupt.json()["state"] == "failed"
    assert corrupt.json()["failure_reason"] == "pdf_open_failed"
    assert blank.json()["state"] == "partial"
    assert blank.json()["failure_reason"] == "empty_extracted_page"
    assert blank.json()["ready_at"] is None


def test_rotated_document_reaches_ready_with_matching_page_identity(
    lifecycle_client: TestClient,
) -> None:
    response = ingest_upload(lifecycle_client, make_pdf(rotation=90), "rotated.pdf")
    body = response.json()
    evidence = lifecycle_client.get(version_url(body) + "/evidence").json()
    pages = lifecycle_client.get(version_url(body) + "/pages").json()

    assert body["state"] == "ready"
    assert pages["pages"][0]["rotation"] == 90
    assert evidence["document_version"] == pages["document_version"]
    assert all(unit["page_index"] == 0 for unit in evidence["units"])


def test_interrupted_parsing_state_can_be_retried(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path, max_upload_bytes=64 * 1024, chunk_bytes=4096)
    manifest = persisted_manifest(store, make_pdf())
    interrupted = IngestionManifest.model_validate(
        {
            **manifest.model_dump(mode="python"),
            "state": IngestionState.PARSING,
            "parser": PyMuPDFParser().metadata,
            "attempt_count": 1,
            "last_request_id": "req_interrupted",
        }
    )
    store.update_manifest(interrupted)

    ready = service(store).ingest(
        manifest.document_id,
        manifest.document_sha256,
        request_id="req_retry",
        mode=IngestionMode.RETRY,
    )

    assert ready.state is IngestionState.READY
    assert ready.attempt_count == 2


def test_structured_logs_exclude_source_text_filename_and_paths(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store = LocalArtifactStore(tmp_path, max_upload_bytes=64 * 1024, chunk_bytes=4096)
    secret_text = "DO-NOT-LOG-SOURCE-TEXT"
    manifest = persisted_manifest(store, make_pdf(secret_text))

    with caplog.at_level(logging.INFO, logger="evidence_rag.ingestion"):
        ready = service(store).ingest(
            manifest.document_id,
            manifest.document_sha256,
            request_id="req_logging",
        )

    assert ready.state is IngestionState.READY
    assert caplog.messages
    for message in caplog.messages:
        payload = json.loads(message)
        assert payload["request_id"] == "req_logging"
        assert secret_text not in message
        assert manifest.original_filename not in message
        assert str(tmp_path) not in message


def test_invalid_lifecycle_transition_is_rejected() -> None:
    with pytest.raises(LifecycleTransitionError):
        assert_transition(IngestionState.RECEIVED, IngestionState.READY)
