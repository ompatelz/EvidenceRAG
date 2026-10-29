"""Tests for provenance-preserving PyMuPDF evidence extraction."""

import io
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pymupdf
import pytest
from fastapi.testclient import TestClient

from evidence_rag.api import create_app
from evidence_rag.config import AppSettings
from evidence_rag.documents.models import (
    IngestionManifest,
    IngestionState,
    ParseIssue,
    ParserMetadata,
)
from evidence_rag.documents.parser import (
    REPRESENTATION_VERSION,
    ParserError,
    ParseResult,
    PyMuPDFParser,
    _Candidate,
)
from evidence_rag.documents.service import DocumentParsingService
from evidence_rag.documents.storage import LocalArtifactStore
from evidence_rag.evidence import (
    AnchorPrecision,
    ElementType,
    EvidenceUnit,
    RepresentationVersions,
)

FIXTURES = Path("datasets/fixtures")


@pytest.fixture
def parsing_client(tmp_path: Path) -> Iterator[TestClient]:
    settings = AppSettings(
        environment="test",
        artifact_root=tmp_path / "artifacts",
        max_upload_bytes=64 * 1024,
        multipart_overhead_bytes=64 * 1024,
        max_pdf_pages=10,
    )
    with TestClient(create_app(settings)) as client:
        yield client


def upload(client: TestClient, content: bytes, filename: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/documents",
        files={"file": (filename, content, "application/pdf")},
    )
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def parse_url(uploaded: dict[str, object]) -> str:
    return (
        f"/api/v1/documents/{uploaded['document_id']}/versions/{uploaded['document_sha256']}/parse"
    )


def evidence_url(uploaded: dict[str, object]) -> str:
    return (
        f"/api/v1/documents/{uploaded['document_id']}/versions/"
        f"{uploaded['document_sha256']}/evidence"
    )


def make_pdf(*pages: tuple[str | None, int]) -> bytes:
    document = pymupdf.open()  # type: ignore[no-untyped-call]
    for text, rotation in pages:
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


def test_owned_fixture_extraction_is_deterministic_and_versioned(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path, max_upload_bytes=64 * 1024, chunk_bytes=4096)
    manifest = persisted_manifest(store, (FIXTURES / "atlas-narrative.pdf").read_bytes())
    parser = PyMuPDFParser(max_pages=10)

    first = parser.parse(store.source_path(manifest), manifest)
    second = parser.parse(store.source_path(manifest), manifest)

    assert first == second
    assert first.page_count == first.successful_pages == 1
    assert not first.issues
    assert all(unit.document_id == manifest.document_id for unit in first.units)
    assert all(unit.document_version == manifest.document_version for unit in first.units)
    assert all(unit.document_sha256 == manifest.document_sha256 for unit in first.units)
    assert [unit.reading_order for unit in first.units] == list(range(len(first.units)))
    assert any(unit.element_type is ElementType.HEADING for unit in first.units)
    assert any("20 hertz" in unit.text for unit in first.units)


def test_api_parses_and_persists_inspectable_evidence(
    parsing_client: TestClient,
) -> None:
    uploaded = upload(
        parsing_client,
        (FIXTURES / "atlas-narrative.pdf").read_bytes(),
        "atlas-narrative.pdf",
    )

    parsed = parsing_client.post(parse_url(uploaded))
    evidence = parsing_client.get(evidence_url(uploaded))
    status = parsing_client.get(parse_url(uploaded).removesuffix("/parse") + "/status")

    assert parsed.status_code == evidence.status_code == status.status_code == 200
    assert parsed.json()["state"] == "parsed"
    assert parsed.json()["parser"] == {
        "name": "pymupdf",
        "version": "1.28.2",
        "representation_version": REPRESENTATION_VERSION,
    }
    assert parsed.json()["evidence_count"] == len(evidence.json()["units"])
    assert evidence.json()["document_version"] == uploaded["document_version"]
    assert status.json()["state"] == "parsed"
    assert str(Path.cwd().resolve()) not in evidence.text


def test_table_structure_caption_and_coordinates_are_preserved(
    parsing_client: TestClient,
) -> None:
    uploaded = upload(
        parsing_client,
        (FIXTURES / "retrieval-table.pdf").read_bytes(),
        "retrieval-table.pdf",
    )
    assert parsing_client.post(parse_url(uploaded)).json()["state"] == "parsed"
    units = parsing_client.get(evidence_url(uploaded)).json()["units"]

    table = next(unit for unit in units if unit["element_type"] == "table")
    caption = next(unit for unit in units if unit["text"].startswith("Table 1."))
    assert table["table"]["headers"] == ["Method", "Precision", "Recall", "F1"]
    assert table["table"]["rows"][-1] == ["Hybrid", "0.88", "0.84", "0.86"]
    assert table["table"]["caption"] == "Table 1. Synthetic retrieval metrics."
    assert caption["related_element_id"] == table["parser_element_id"]
    assert table["anchor_precision"] == "region"
    assert table["source_region"]["coordinate_system"] == ("pymupdf_points_top_left_unrotated")
    assert table["source_region"]["bbox"] == {
        "x0": 72.0,
        "y0": 160.0,
        "x1": 532.0,
        "y1": 296.0,
    }
    assert table["bbox"]["x0"] == pytest.approx(72.0 / 612.0, abs=1e-8)
    assert table["bbox"]["y1"] == pytest.approx(296.0 / 792.0, abs=1e-8)


def test_multi_page_reading_order_and_zero_based_pages(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path, max_upload_bytes=64 * 1024, chunk_bytes=4096)
    manifest = persisted_manifest(store, make_pdf(("First page", 0), ("Second page", 0)))

    result = PyMuPDFParser(max_pages=10).parse(store.source_path(manifest), manifest)

    assert [unit.page_index for unit in result.units] == [0, 1]
    assert [unit.reading_order for unit in result.units] == [0, 0]
    assert [unit.text for unit in result.units] == ["First page", "Second page"]


def test_rotated_page_keeps_unrotated_source_geometry(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path, max_upload_bytes=64 * 1024, chunk_bytes=4096)
    manifest = persisted_manifest(store, make_pdf(("Rotated evidence", 90)))

    result = PyMuPDFParser(max_pages=10).parse(store.source_path(manifest), manifest)
    unit = result.units[0]

    assert unit.source_region is not None
    assert unit.source_region.page_width == 200
    assert unit.source_region.page_height == 100
    assert unit.source_region.page_rotation == 90
    assert unit.source_region.bbox.x1 <= 200
    assert unit.source_region.bbox.y1 <= 100
    assert unit.anchor_precision is AnchorPrecision.REGION


def test_missing_bbox_downgrades_to_honest_page_precision(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path, max_upload_bytes=64 * 1024, chunk_bytes=4096)
    manifest = persisted_manifest(store, make_pdf(("Evidence", 0)))
    parser = PyMuPDFParser()
    candidate = _Candidate(
        parser_element_id="p0-test-no-bbox",
        element_type=ElementType.TEXT,
        text="Evidence without reliable coordinates.",
        bbox=None,
    )

    unit = parser._candidate_to_unit(
        candidate,
        manifest=manifest,
        page_index=0,
        page_width=200,
        page_height=100,
        page_rotation=0,
        reading_order=0,
        section_title=None,
    )

    assert unit.anchor_precision is AnchorPrecision.PAGE
    assert unit.bbox is None
    assert unit.coordinate_system is None
    assert unit.source_region is None


def test_empty_page_is_partial_and_never_ready(parsing_client: TestClient) -> None:
    uploaded = upload(parsing_client, make_pdf((None, 0)), "blank.pdf")

    response = parsing_client.post(parse_url(uploaded))
    evidence = parsing_client.get(evidence_url(uploaded))

    assert response.status_code == 200
    assert response.json()["state"] == "partial"
    assert response.json()["evidence_count"] == 0
    assert response.json()["issues"][0]["code"] == "empty_extracted_page"
    assert evidence.json()["units"] == []


def test_structurally_invalid_pdf_records_failed_state(
    parsing_client: TestClient,
) -> None:
    uploaded = upload(
        parsing_client,
        b"%PDF-1.7\nnot structurally valid\n%%EOF",
        "broken.pdf",
    )

    response = parsing_client.post(parse_url(uploaded))
    status = parsing_client.get(parse_url(uploaded).removesuffix("/parse") + "/status")

    assert response.status_code == 200
    assert response.json()["state"] == "failed"
    assert response.json()["issues"][0]["code"] == "pdf_open_failed"
    assert status.json()["state"] == "failed"
    assert parsing_client.get(evidence_url(uploaded)).status_code == 404


class PartialParser:
    @property
    def metadata(self) -> ParserMetadata:
        return ParserMetadata(
            name="fixture-parser",
            version="1.0",
            representation_version=REPRESENTATION_VERSION,
        )

    def parse(self, path: Path, manifest: IngestionManifest) -> ParseResult:
        assert path.is_file()
        unit = EvidenceUnit(
            evidence_id="ev_partial_fixture",
            document_id=manifest.document_id,
            document_sha256=manifest.document_sha256,
            document_version=manifest.document_version,
            page_index=0,
            element_type=ElementType.TEXT,
            text="Recovered page evidence.",
            anchor_precision=AnchorPrecision.PAGE,
            versions=RepresentationVersions(parser="fixture:1.0", representation="test"),
        )
        return ParseResult(
            units=(unit,),
            issues=(
                ParseIssue(
                    code="page_parse_failed",
                    message="A later page failed.",
                    page_index=1,
                ),
            ),
            page_count=2,
            successful_pages=1,
        )


class UnexpectedFailureParser(PartialParser):
    def parse(self, path: Path, manifest: IngestionManifest) -> ParseResult:
        raise RuntimeError(f"private parser detail: {path}")


def test_partial_extraction_persists_units_and_truthful_state(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path, max_upload_bytes=64 * 1024, chunk_bytes=4096)
    manifest = persisted_manifest(store, make_pdf(("One", 0), ("Two", 0)))
    service = DocumentParsingService(store, PartialParser())

    response = service.parse(manifest.document_id, manifest.document_sha256)
    artifact = service.evidence(manifest.document_id, manifest.document_sha256)
    updated = store.get_manifest(manifest.document_id, manifest.document_sha256)

    assert response.state is IngestionState.PARTIAL
    assert response.evidence_count == 1
    assert artifact.units[0].text == "Recovered page evidence."
    assert updated.state is IngestionState.PARTIAL
    assert updated.failure_reason == "page_parse_failed"


def test_unexpected_parser_exception_records_safe_failed_state(tmp_path: Path) -> None:
    content = make_pdf(("One", 0))
    store = LocalArtifactStore(tmp_path, max_upload_bytes=64 * 1024, chunk_bytes=4096)
    manifest = persisted_manifest(store, content)
    service = DocumentParsingService(store, UnexpectedFailureParser())

    response = service.parse(manifest.document_id, manifest.document_sha256)
    updated = store.get_manifest(manifest.document_id, manifest.document_sha256)

    assert response.state is IngestionState.FAILED
    assert response.issues[0].code == "parser_unexpected_failure"
    assert str(tmp_path) not in response.model_dump_json()
    assert updated.failure_reason == "parser_unexpected_failure"


def test_page_limit_failure_is_explicit(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path, max_upload_bytes=64 * 1024, chunk_bytes=4096)
    manifest = persisted_manifest(store, make_pdf(("One", 0), ("Two", 0)))

    with pytest.raises(ParserError, match="page limit") as error:
        PyMuPDFParser(max_pages=1).parse(store.source_path(manifest), manifest)

    assert error.value.code == "page_limit_exceeded"
