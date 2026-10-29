"""Bounded page rendering and reproducible evidence-anchor geometry."""

import hashlib
import math
from pathlib import Path
from typing import Literal, Protocol, cast

import pymupdf

from evidence_rag.documents.models import (
    IngestionManifest,
    PageBox,
    PagePreviewArtifact,
    PagePreviewManifest,
    PixelBoundingBox,
    RendererMetadata,
)
from evidence_rag.evidence import NormalizedBoundingBox

RENDER_PROFILE = "png-rgb-no-annotations-v1"
PageRotation = Literal[0, 90, 180, 270]


class RenderError(RuntimeError):
    """Bounded rendering failure without source text or private paths."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class PageRenderer(Protocol):
    """Narrow rendering seam used by the document service."""

    @property
    def metadata(self) -> RendererMetadata: ...

    def render(
        self, source: Path, manifest: IngestionManifest, destination: Path
    ) -> PagePreviewManifest: ...


def rotate_normalized_bbox(
    bbox: NormalizedBoundingBox, rotation: PageRotation
) -> NormalizedBoundingBox:
    """Map an unrotated source region into the displayed page orientation."""
    if rotation == 0:
        values = bbox.x0, bbox.y0, bbox.x1, bbox.y1
    elif rotation == 90:
        values = 1.0 - bbox.y1, bbox.x0, 1.0 - bbox.y0, bbox.x1
    elif rotation == 180:
        values = 1.0 - bbox.x1, 1.0 - bbox.y1, 1.0 - bbox.x0, 1.0 - bbox.y0
    else:
        values = bbox.y0, 1.0 - bbox.x1, bbox.y1, 1.0 - bbox.x0
    return NormalizedBoundingBox(
        x0=round(values[0], 8),
        y0=round(values[1], 8),
        x1=round(values[2], 8),
        y1=round(values[3], 8),
    )


def derotate_normalized_bbox(
    bbox: NormalizedBoundingBox, rotation: PageRotation
) -> NormalizedBoundingBox:
    """Map a displayed region back into unrotated source coordinates."""
    inverse: PageRotation = cast(PageRotation, (360 - rotation) % 360)
    return rotate_normalized_bbox(bbox, inverse)


def normalized_to_pixels(
    bbox: NormalizedBoundingBox, *, width: int, height: int
) -> PixelBoundingBox:
    """Create a containing integer pixel box without shrinking the source region."""
    if width <= 0 or height <= 0:
        raise ValueError("preview dimensions must be positive")
    return PixelBoundingBox(
        x0=max(0, min(width - 1, math.floor(bbox.x0 * width))),
        y0=max(0, min(height - 1, math.floor(bbox.y0 * height))),
        x1=max(1, min(width, math.ceil(bbox.x1 * width))),
        y1=max(1, min(height, math.ceil(bbox.y1 * height))),
    )


class PyMuPDFPageRenderer:
    """Render the visible crop box to deterministic RGB PNG previews."""

    def __init__(
        self,
        *,
        dpi: int = 144,
        max_pages: int = 200,
        max_page_pixels: int = 20_000_000,
        max_total_pixels: int = 100_000_000,
    ) -> None:
        self.dpi = dpi
        self.max_pages = max_pages
        self.max_page_pixels = max_page_pixels
        self.max_total_pixels = max_total_pixels

    @property
    def metadata(self) -> RendererMetadata:
        return RendererMetadata(
            name="pymupdf",
            version=pymupdf.__version__,
            profile=RENDER_PROFILE,
            dpi=self.dpi,
        )

    def render(
        self, source: Path, manifest: IngestionManifest, destination: Path
    ) -> PagePreviewManifest:
        try:
            document = pymupdf.open(source)  # type: ignore[no-untyped-call]
        except Exception as exc:
            raise RenderError("pdf_open_failed", "PyMuPDF could not open the PDF.") from exc

        pages: list[PagePreviewArtifact] = []
        try:
            with document:
                if not document.is_pdf:
                    raise RenderError("not_pdf", "The accepted artifact is not a PDF.")
                if document.needs_pass:
                    raise RenderError(
                        "encrypted_pdf_unsupported",
                        "Encrypted PDFs cannot be rendered in Phase 1.3.",
                    )
                if document.page_count == 0:
                    raise RenderError("no_pages", "The PDF contains no pages.")
                if document.page_count > self.max_pages:
                    raise RenderError(
                        "page_limit_exceeded",
                        "The PDF exceeds the configured rendering page limit.",
                    )

                destination.mkdir(parents=True, exist_ok=False)
                total_pixels = 0
                for page_index in range(document.page_count):
                    page = document.load_page(page_index)  # type: ignore[no-untyped-call]
                    source_width = float(page.cropbox.width)
                    source_height = float(page.cropbox.height)
                    scale = self.dpi / 72.0
                    expected_pixels = math.ceil(source_width * scale) * math.ceil(
                        source_height * scale
                    )
                    if expected_pixels > self.max_page_pixels:
                        raise RenderError(
                            "page_pixel_limit_exceeded",
                            "A rendered page would exceed the configured pixel limit.",
                        )
                    total_pixels += expected_pixels
                    if total_pixels > self.max_total_pixels:
                        raise RenderError(
                            "document_pixel_limit_exceeded",
                            "The rendered document would exceed the configured pixel limit.",
                        )
                    pixmap = page.get_pixmap(
                        dpi=self.dpi,
                        colorspace=pymupdf.csRGB,
                        alpha=False,
                        annots=False,
                    )
                    if pixmap.width * pixmap.height > self.max_page_pixels:
                        raise RenderError(
                            "page_pixel_limit_exceeded",
                            "A rendered page exceeded the configured pixel limit.",
                        )
                    page_path = destination / f"page-{page_index}.png"
                    pixmap.save(page_path)
                    rotation = cast(PageRotation, page.rotation)
                    pages.append(
                        PagePreviewArtifact(
                            page_index=page_index,
                            asset_id=(
                                f"asset:page:{manifest.document_id}:"
                                f"{manifest.document_sha256[:24]}:{page_index}"
                            ),
                            width_pixels=pixmap.width,
                            height_pixels=pixmap.height,
                            source_width=source_width,
                            source_height=source_height,
                            rotation=rotation,
                            cropbox=self._page_box(page.cropbox),
                            mediabox=self._page_box(page.mediabox),
                            content_sha256=self._sha256(page_path),
                        )
                    )
        except RenderError:
            raise
        except Exception as exc:
            raise RenderError(
                "page_render_failed",
                "A page preview could not be rendered safely.",
            ) from exc

        return PagePreviewManifest(
            document_id=manifest.document_id,
            document_version=manifest.document_version,
            document_sha256=manifest.document_sha256,
            renderer=self.metadata,
            pages=pages,
        )

    @staticmethod
    def _page_box(rect: pymupdf.Rect) -> PageBox:
        return PageBox(x0=rect.x0, y0=rect.y0, x1=rect.x1, y1=rect.y1)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            while chunk := source.read(64 * 1024):
                digest.update(chunk)
        return digest.hexdigest()
