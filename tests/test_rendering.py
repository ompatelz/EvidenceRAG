"""Tests for bounded page previews and evidence-anchor resolution."""

import hashlib
import io
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pymupdf
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from evidence_rag.api import create_app
from evidence_rag.config import AppSettings
from evidence_rag.documents.errors import IntakeError
from evidence_rag.documents.models import (
    IngestionManifest,
    PagePreviewManifest,
    PixelBoundingBox,
    RendererMetadata,
)
from evidence_rag.documents.parser import PyMuPDFParser
from evidence_rag.documents.rendering import (
    RENDER_PROFILE,
    PageRenderer,
    PageRotation,
    PyMuPDFPageRenderer,
    RenderError,
    derotate_normalized_bbox,
    normalized_to_pixels,
    rotate_normalized_bbox,
)
from evidence_rag.documents.service import (
    DocumentParsingService,
    DocumentRenderingService,
)
from evidence_rag.documents.storage import LocalArtifactStore
from evidence_rag.evidence import AnchorPrecision, NormalizedBoundingBox

FIXTURES = Path("datasets/fixtures")


@pytest.fixture
def rendering_client(tmp_path: Path) -> Iterator[TestClient]:
    settings = AppSettings(
        environment="test",
        artifact_root=tmp_path / "artifacts",
        max_upload_bytes=64 * 1024,
        multipart_overhead_bytes=64 * 1024,
        max_pdf_pages=10,
        render_dpi=144,
    )
    with TestClient(create_app(settings)) as client:
        yield client


def upload(client: TestClient, content: bytes, filename: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/documents",
        files={"file": (filename, content, "application/pdf")},
    )
    assert response.status_code == 201
    return cast(dict[str, Any], response.json())


def version_url(uploaded: dict[str, Any]) -> str:
    return f"/api/v1/documents/{uploaded['document_id']}/versions/{uploaded['document_sha256']}"


def prepare(
    client: TestClient, content: bytes, filename: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    uploaded = upload(client, content, filename)
    parsed = client.post(version_url(uploaded) + "/parse")
    rendered = client.post(version_url(uploaded) + "/render")
    assert parsed.status_code == rendered.status_code == 200
    return (
        uploaded,
        cast(dict[str, Any], parsed.json()),
        cast(dict[str, Any], rendered.json()),
    )


def make_pdf(
    *,
    text: str = "Rendered evidence",
    width: float = 200,
    height: float = 100,
    rotation: int = 0,
    cropbox: tuple[float, float, float, float] | None = None,
    page_count: int = 1,
) -> bytes:
    document = pymupdf.open()  # type: ignore[no-untyped-call]
    for _ in range(page_count):
        page = document.new_page(width=width, height=height)
        page.insert_text((70, 50), text)
        if cropbox is not None:
            page.set_cropbox(  # type: ignore[no-untyped-call]
                pymupdf.Rect(cropbox)  # type: ignore[no-untyped-call]
            )
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


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_normalized_rotation_round_trip(rotation: int) -> None:
    source = NormalizedBoundingBox(x0=0.1, y0=0.2, x1=0.7, y1=0.8)

    page_rotation = cast(PageRotation, rotation)
    displayed = rotate_normalized_bbox(source, page_rotation)
    restored = derotate_normalized_bbox(displayed, page_rotation)

    assert restored == source


def test_boundary_and_invalid_pixel_boxes() -> None:
    full_page = NormalizedBoundingBox(x0=0.0, y0=0.0, x1=1.0, y1=1.0)
    assert normalized_to_pixels(full_page, width=612, height=792) == PixelBoundingBox(
        x0=0, y0=0, x1=612, y1=792
    )
    with pytest.raises(ValidationError):
        PixelBoundingBox(x0=10, y0=0, x1=10, y1=20)


def test_owned_table_preview_and_anchor_are_inspectable(
    rendering_client: TestClient,
) -> None:
    uploaded, _, rendered = prepare(
        rendering_client,
        (FIXTURES / "retrieval-table.pdf").read_bytes(),
        "retrieval-table.pdf",
    )
    base = version_url(uploaded)
    pages = rendering_client.get(base + "/pages")
    preview = rendering_client.get(base + "/pages/0/preview")
    evidence = rendering_client.get(base + "/evidence").json()["units"]
    table = next(unit for unit in evidence if unit["element_type"] == "table")
    anchor = rendering_client.get(base + f"/evidence/{table['evidence_id']}/anchor")
    repeated = rendering_client.post(base + "/render")

    assert pages.status_code == preview.status_code == anchor.status_code == 200
    assert repeated.status_code == 200
    assert rendered == repeated.json()
    assert rendered["renderer"] == {
        "name": "pymupdf",
        "version": "1.28.2",
        "profile": RENDER_PROFILE,
        "dpi": 144,
    }
    assert rendered["pages"][0]["width_pixels"] == 1224
    assert rendered["pages"][0]["height_pixels"] == 1584
    assert preview.headers["content-type"] == "image/png"
    assert preview.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert rendered["pages"][0]["content_sha256"] == hashlib.sha256(preview.content).hexdigest()
    assert preview.headers["etag"] == f'"sha256:{rendered["pages"][0]["content_sha256"]}"'
    assert str(Path.cwd().resolve()) not in pages.text
    assert anchor.json()["pixel_bbox"] == {"x0": 144, "y0": 319, "x1": 1065, "y1": 592}
    assert anchor.json()["source_bbox"] == table["bbox"]
    assert anchor.json()["display_bbox"] == table["bbox"]


def test_known_table_region_contains_rendered_grid_pixels(
    rendering_client: TestClient,
) -> None:
    uploaded, _, _ = prepare(
        rendering_client,
        (FIXTURES / "retrieval-table.pdf").read_bytes(),
        "retrieval-table.pdf",
    )
    preview = rendering_client.get(version_url(uploaded) + "/pages/0/preview")
    pixmap = pymupdf.Pixmap(preview.content)  # type: ignore[no-untyped-call]
    samples = pixmap.samples

    def is_dark(x: int, y: int) -> bool:
        offset = (y * pixmap.width + x) * pixmap.n
        return max(samples[offset : offset + 3]) < 220

    left_border_dark = sum(is_dark(x, y) for x in range(142, 147) for y in range(318, 595))
    top_border_dark = sum(is_dark(x, y) for x in range(142, 1067) for y in range(318, 323))
    assert left_border_dark > 200
    assert top_border_dark > 700


def test_rotated_page_maps_source_box_to_display_pixels(
    rendering_client: TestClient,
) -> None:
    uploaded, _, rendered = prepare(
        rendering_client,
        make_pdf(rotation=90),
        "rotated.pdf",
    )
    base = version_url(uploaded)
    unit = rendering_client.get(base + "/evidence").json()["units"][0]
    anchor = rendering_client.get(base + f"/evidence/{unit['evidence_id']}/anchor").json()

    assert rendered["pages"][0]["rotation"] == 90
    assert rendered["pages"][0]["width_pixels"] == 200
    assert rendered["pages"][0]["height_pixels"] == 400
    source = unit["bbox"]
    assert anchor["display_bbox"] == {
        "x0": pytest.approx(1 - source["y1"]),
        "y0": source["x0"],
        "x1": pytest.approx(1 - source["y0"]),
        "y1": source["x1"],
    }


def test_render_scale_changes_pixels_not_normalized_geometry(tmp_path: Path) -> None:
    content = make_pdf()
    store = LocalArtifactStore(tmp_path / "store", max_upload_bytes=64 * 1024, chunk_bytes=4096)
    manifest = persisted_manifest(store, content)
    first = PyMuPDFPageRenderer(dpi=72).render(
        store.source_path(manifest), manifest, tmp_path / "dpi-72"
    )
    second = PyMuPDFPageRenderer(dpi=144).render(
        store.source_path(manifest), manifest, tmp_path / "dpi-144"
    )
    bbox = NormalizedBoundingBox(x0=0.1, y0=0.2, x1=0.7, y1=0.8)

    assert second.pages[0].width_pixels == first.pages[0].width_pixels * 2
    assert second.pages[0].height_pixels == first.pages[0].height_pixels * 2
    first_pixels = normalized_to_pixels(
        bbox, width=first.pages[0].width_pixels, height=first.pages[0].height_pixels
    )
    second_pixels = normalized_to_pixels(
        bbox, width=second.pages[0].width_pixels, height=second.pages[0].height_pixels
    )
    assert second_pixels == PixelBoundingBox(
        x0=first_pixels.x0 * 2,
        y0=first_pixels.y0 * 2,
        x1=first_pixels.x1 * 2,
        y1=first_pixels.y1 * 2,
    )


def test_cropbox_and_mediabox_offsets_are_preserved(
    rendering_client: TestClient,
) -> None:
    uploaded, _, rendered = prepare(
        rendering_client,
        make_pdf(width=300, height=200, cropbox=(50, 25, 250, 125)),
        "cropped.pdf",
    )
    page = rendered["pages"][0]
    unit = rendering_client.get(version_url(uploaded) + "/evidence").json()["units"][0]
    anchor = rendering_client.get(version_url(uploaded) + f"/evidence/{unit['evidence_id']}/anchor")

    assert page["cropbox"] == {"x0": 50.0, "y0": 25.0, "x1": 250.0, "y1": 125.0}
    assert page["mediabox"] == {"x0": 0.0, "y0": 0.0, "x1": 300.0, "y1": 200.0}
    assert page["source_width"] == 200.0
    assert page["source_height"] == 100.0
    assert page["width_pixels"] == 400
    assert page["height_pixels"] == 200
    assert anchor.status_code == 200


def test_invalid_scopes_and_page_indexes_are_rejected(
    rendering_client: TestClient,
) -> None:
    uploaded, _, _ = prepare(rendering_client, make_pdf(), "scope.pdf")
    base = version_url(uploaded)

    assert rendering_client.get(base + "/pages/99/preview").status_code == 404
    assert rendering_client.get(base + "/pages/-1/preview").status_code == 404
    assert (
        rendering_client.get(
            base.replace(str(uploaded["document_id"]), "doc_000000000000000000000000")
            + "/pages/0/preview"
        ).status_code
        == 404
    )
    assert (
        rendering_client.get(
            base.replace(str(uploaded["document_sha256"]), "0" * 64) + "/pages/0/preview"
        ).status_code
        == 404
    )


def test_cross_document_and_stale_version_anchor_requests_fail(
    rendering_client: TestClient,
) -> None:
    first, _, _ = prepare(rendering_client, make_pdf(text="First"), "first.pdf")
    second, _, _ = prepare(rendering_client, make_pdf(text="Second"), "second.pdf")
    first_unit = rendering_client.get(version_url(first) + "/evidence").json()["units"][0]

    cross = rendering_client.get(
        version_url(second) + f"/evidence/{first_unit['evidence_id']}/anchor"
    )
    stale = rendering_client.get(
        f"/api/v1/documents/{first['document_id']}/versions/"
        f"{second['document_sha256']}/pages/0/preview"
    )

    assert cross.status_code == 404
    assert stale.status_code == 404


def test_missing_preview_and_missing_published_file_are_safe(
    rendering_client: TestClient,
) -> None:
    uploaded = upload(rendering_client, make_pdf(), "missing.pdf")
    base = version_url(uploaded)
    assert rendering_client.post(base + "/parse").status_code == 200
    assert rendering_client.get(base + "/pages").status_code == 404

    assert rendering_client.post(base + "/render").status_code == 200
    store = cast(Any, rendering_client.app).state.rendering_service.store
    store.preview_path(str(uploaded["document_id"]), str(uploaded["document_sha256"]), 0).unlink()
    response = rendering_client.get(base + "/pages/0/preview")
    assert response.status_code == 404
    assert str(Path.cwd().resolve()) not in response.text


def test_render_requires_completed_parse(rendering_client: TestClient) -> None:
    uploaded = upload(rendering_client, make_pdf(), "received-only.pdf")

    response = rendering_client.post(version_url(uploaded) + "/render")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "document_not_parsed"
    status = rendering_client.get(version_url(uploaded) + "/status")
    assert status.json()["state"] == "received"


def test_corrupt_preview_is_not_served(rendering_client: TestClient) -> None:
    uploaded, _, _ = prepare(rendering_client, make_pdf(), "corrupt-preview.pdf")
    store = cast(Any, rendering_client.app).state.rendering_service.store
    path = store.preview_path(str(uploaded["document_id"]), str(uploaded["document_sha256"]), 0)
    path.write_bytes(b"not the committed PNG")

    response = rendering_client.get(version_url(uploaded) + "/pages/0/preview")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "preview_not_found"


class FailingRenderer(PageRenderer):
    @property
    def metadata(self) -> RendererMetadata:
        return RendererMetadata(
            name="fixture-renderer",
            version="1.0",
            profile="fixture-profile",
            dpi=72,
        )

    def render(
        self, source: Path, manifest: IngestionManifest, destination: Path
    ) -> PagePreviewManifest:
        raise RenderError("fixture_render_failed", "Fixture rendering failed safely.")


def test_rendering_failure_is_explicit_and_leaves_no_page_manifest(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path, max_upload_bytes=64 * 1024, chunk_bytes=4096)
    manifest = persisted_manifest(store, make_pdf())
    parsed = DocumentParsingService(store, PyMuPDFParser()).parse(
        manifest.document_id, manifest.document_sha256
    )
    assert parsed.state.value == "parsed"
    service = DocumentRenderingService(store, cast(PageRenderer, FailingRenderer()))

    with pytest.raises(IntakeError) as error:
        service.render(manifest.document_id, manifest.document_sha256)

    assert error.value.code == "fixture_render_failed"
    with pytest.raises(LookupError):
        store.get_page_manifest(manifest.document_id, manifest.document_sha256)


def test_render_pixel_limit_fails_before_publication(tmp_path: Path) -> None:
    settings = AppSettings(
        environment="test",
        artifact_root=tmp_path / "artifacts",
        max_upload_bytes=64 * 1024,
        multipart_overhead_bytes=64 * 1024,
        max_render_pixels_per_page=100,
    )
    with TestClient(create_app(settings)) as client:
        uploaded = upload(client, make_pdf(), "limited.pdf")
        base = version_url(uploaded)
        assert client.post(base + "/parse").status_code == 200
        response = client.post(base + "/render")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "page_pixel_limit_exceeded"
        assert client.get(base + "/pages").status_code == 404


def test_render_total_pixel_limit_cleans_partial_stage(tmp_path: Path) -> None:
    settings = AppSettings(
        environment="test",
        artifact_root=tmp_path / "artifacts",
        max_upload_bytes=64 * 1024,
        multipart_overhead_bytes=64 * 1024,
        max_render_pixels_per_page=100_000,
        max_render_pixels_total=100_000,
    )
    with TestClient(create_app(settings)) as client:
        uploaded = upload(client, make_pdf(page_count=2), "total-limited.pdf")
        base = version_url(uploaded)
        assert client.post(base + "/parse").status_code == 200
        response = client.post(base + "/render")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "document_pixel_limit_exceeded"
        assert client.get(base + "/pages").status_code == 404
        version_dir = (
            tmp_path
            / "artifacts"
            / "documents"
            / str(uploaded["document_id"])
            / "versions"
            / str(uploaded["document_sha256"])
        )
        assert not list(version_dir.glob(".render-*"))


def test_page_precision_resolves_preview_without_inventing_box(
    rendering_client: TestClient,
) -> None:
    uploaded, _, _ = prepare(rendering_client, make_pdf(), "page-only.pdf")
    store = cast(Any, rendering_client.app).state.rendering_service.store
    evidence = store.get_evidence(str(uploaded["document_id"]), str(uploaded["document_sha256"]))
    original = evidence.units[0]
    page_only = original.model_copy(
        update={
            "anchor_precision": AnchorPrecision.PAGE,
            "bbox": None,
            "coordinate_system": None,
            "source_region": None,
        }
    )
    store.write_evidence(evidence.model_copy(update={"units": [page_only]}))

    response = rendering_client.get(
        version_url(uploaded) + f"/evidence/{page_only.evidence_id}/anchor"
    )

    assert response.status_code == 200
    assert response.json()["precision"] == "page"
    assert response.json()["preview_asset_id"].startswith("asset:page:")
    assert response.json()["source_bbox"] is None
    assert response.json()["display_bbox"] is None
    assert response.json()["pixel_bbox"] is None


def test_region_geometry_mismatch_is_rejected(rendering_client: TestClient) -> None:
    uploaded, _, _ = prepare(rendering_client, make_pdf(), "mismatch.pdf")
    store = cast(Any, rendering_client.app).state.rendering_service.store
    evidence = store.get_evidence(str(uploaded["document_id"]), str(uploaded["document_sha256"]))
    original = evidence.units[0]
    assert original.source_region is not None
    mismatched = original.model_copy(
        update={"source_region": original.source_region.model_copy(update={"page_rotation": 90})}
    )
    store.write_evidence(evidence.model_copy(update={"units": [mismatched]}))

    response = rendering_client.get(
        version_url(uploaded) + f"/evidence/{mismatched.evidence_id}/anchor"
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "anchor_geometry_mismatch"


def test_unavailable_precision_does_not_claim_page_or_region(
    rendering_client: TestClient,
) -> None:
    uploaded, _, _ = prepare(rendering_client, make_pdf(), "unavailable.pdf")
    store = cast(Any, rendering_client.app).state.rendering_service.store
    evidence = store.get_evidence(str(uploaded["document_id"]), str(uploaded["document_sha256"]))
    original = evidence.units[0]
    unavailable = original.model_copy(
        update={
            "anchor_precision": AnchorPrecision.UNAVAILABLE,
            "bbox": None,
            "coordinate_system": None,
            "source_region": None,
        }
    )
    store.write_evidence(evidence.model_copy(update={"units": [unavailable]}))

    response = rendering_client.get(
        version_url(uploaded) + f"/evidence/{unavailable.evidence_id}/anchor"
    )

    assert response.status_code == 200
    assert response.json()["precision"] == "unavailable"
    assert response.json()["preview_asset_id"] is None
    assert response.json()["source_bbox"] is None
    assert response.json()["display_bbox"] is None
    assert response.json()["pixel_bbox"] is None
