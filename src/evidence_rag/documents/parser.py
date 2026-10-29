"""Bounded PyMuPDF adapter producing provenance-preserving evidence units."""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Literal, Protocol, cast

import pymupdf

from evidence_rag.documents.models import IngestionManifest, ParseIssue, ParserMetadata
from evidence_rag.evidence import (
    AnchorPrecision,
    CoordinateSystem,
    ElementType,
    EvidenceUnit,
    NormalizedBoundingBox,
    RepresentationVersions,
    SourceBoundingBox,
    SourceCoordinateSystem,
    SourceRegion,
    TableStructure,
)

REPRESENTATION_VERSION = "evidence-unit-v2"
_CAPTION = re.compile(r"^(?P<kind>table|figure)\s+\d+\s*[.:]", re.IGNORECASE)


class ParserError(RuntimeError):
    """Safe parser failure without source text or private paths."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ParseResult:
    """One deterministic parsing result before persistence."""

    units: tuple[EvidenceUnit, ...]
    issues: tuple[ParseIssue, ...]
    page_count: int
    successful_pages: int


class PdfParser(Protocol):
    """Narrow parser seam used by synchronous document parsing."""

    @property
    def metadata(self) -> ParserMetadata: ...

    def parse(self, path: Path, manifest: IngestionManifest) -> ParseResult: ...


@dataclass(frozen=True)
class _Candidate:
    parser_element_id: str
    element_type: ElementType
    text: str
    bbox: tuple[float, float, float, float] | None
    table: TableStructure | None = None
    related_element_id: str | None = None


class PyMuPDFParser:
    """Extract page-local text, headings, captions, images, and tables."""

    def __init__(self, *, max_pages: int = 200, max_units: int = 10_000) -> None:
        self.max_pages = max_pages
        self.max_units = max_units

    @property
    def metadata(self) -> ParserMetadata:
        return ParserMetadata(
            name="pymupdf",
            version=pymupdf.__version__,
            representation_version=REPRESENTATION_VERSION,
        )

    def parse(self, path: Path, manifest: IngestionManifest) -> ParseResult:
        issues: list[ParseIssue] = []
        units: list[EvidenceUnit] = []
        successful_pages = 0
        try:
            document = pymupdf.open(path)  # type: ignore[no-untyped-call]
        except Exception as exc:
            raise ParserError("pdf_open_failed", "PyMuPDF could not open the PDF.") from exc

        with document:
            if not document.is_pdf:
                raise ParserError("not_pdf", "The accepted artifact is not a PDF.")
            if document.needs_pass:
                raise ParserError(
                    "encrypted_pdf_unsupported",
                    "Encrypted PDFs are not supported in Phase 1.2.",
                )
            if document.page_count == 0:
                raise ParserError("no_pages", "The PDF contains no pages.")
            if document.page_count > self.max_pages:
                raise ParserError(
                    "page_limit_exceeded",
                    "The PDF exceeds the configured parser page limit.",
                )

            for page_index in range(document.page_count):
                page = document.load_page(page_index)  # type: ignore[no-untyped-call]
                try:
                    page_units, page_issues = self._parse_page(page, manifest)
                    successful_pages += 1
                    units.extend(page_units)
                    issues.extend(page_issues)
                    if not page_units:
                        issues.append(
                            ParseIssue(
                                code="empty_extracted_page",
                                message="No supported evidence was extracted from the page.",
                                page_index=page.number,
                            )
                        )
                    if len(units) > self.max_units:
                        raise ParserError(
                            "evidence_limit_exceeded",
                            "The PDF exceeds the configured evidence-unit limit.",
                        )
                except ParserError:
                    raise
                except Exception:
                    issues.append(
                        ParseIssue(
                            code="page_parse_failed",
                            message="The page could not be parsed.",
                            page_index=page.number,
                        )
                    )

            return ParseResult(
                units=tuple(units),
                issues=tuple(issues),
                page_count=document.page_count,
                successful_pages=successful_pages,
            )

    def _parse_page(
        self, page: pymupdf.Page, manifest: IngestionManifest
    ) -> tuple[list[EvidenceUnit], list[ParseIssue]]:
        issues: list[ParseIssue] = []
        flags = pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES
        page_dict: dict[str, Any] = page.get_text(  # type: ignore[no-untyped-call]
            "dict", flags=flags, sort=True
        )
        blocks = [block for block in page_dict["blocks"] if block.get("type") == 0]

        try:
            tables: list[Any] = list(page.find_tables().tables)  # type: ignore[no-untyped-call]
        except Exception:
            tables = []
            issues.append(
                ParseIssue(
                    code="table_detection_failed",
                    message="Table detection failed; text extraction continued.",
                    page_index=page.number,
                )
            )

        captions = self._caption_blocks(blocks)
        candidates: list[_Candidate] = []
        table_rects: list[tuple[float, float, float, float]] = []
        caption_relationships: dict[int, str] = {}
        for table_index, table in enumerate(tables):
            element_id = f"p{page.number}-table-{table_index}"
            bbox = self._bbox_tuple(table.bbox)
            table_rects.append(bbox)
            caption_index = self._nearest_caption(captions, blocks, "table", bbox)
            caption_text = None
            if caption_index is not None:
                caption_text = self._block_text(blocks[caption_index])
                caption_relationships[caption_index] = element_id
            rows = self._normalize_rows(table.extract(), table.row_count, table.col_count)
            headers = [self._clean_cell(value) for value in table.header.names]
            if len(headers) != table.col_count:
                headers = [None] * table.col_count
            structure = TableStructure(
                row_count=table.row_count,
                column_count=table.col_count,
                headers=headers,
                rows=rows,
                caption=caption_text,
                header_external=bool(table.header.external),
            )
            candidates.append(
                _Candidate(
                    parser_element_id=element_id,
                    element_type=ElementType.TABLE,
                    text=self._table_markdown(structure),
                    bbox=bbox,
                    table=structure,
                )
            )

        try:
            images: list[dict[str, Any]] = list(page.get_image_info(xrefs=True))
        except Exception:
            images = []
            issues.append(
                ParseIssue(
                    code="figure_detection_failed",
                    message="Image detection failed; text extraction continued.",
                    page_index=page.number,
                )
            )
        for image_index, image in enumerate(images):
            bbox = self._bbox_tuple(image["bbox"])
            caption_index = self._nearest_caption(captions, blocks, "figure", bbox)
            if caption_index is None:
                continue
            element_id = f"p{page.number}-image-{image_index}"
            caption_relationships[caption_index] = element_id
            candidates.append(
                _Candidate(
                    parser_element_id=element_id,
                    element_type=ElementType.FIGURE,
                    text=self._block_text(blocks[caption_index]),
                    bbox=bbox,
                )
            )

        heading_indexes = self._heading_indexes(blocks, table_rects)
        for block_index, block in enumerate(blocks):
            text = self._block_text(block)
            if not text or self._inside_table(self._bbox_tuple(block["bbox"]), table_rects):
                continue
            caption_match = _CAPTION.match(text)
            if caption_match:
                element_type = ElementType.CAPTION
            elif block_index in heading_indexes:
                element_type = ElementType.HEADING
            else:
                element_type = ElementType.TEXT
            candidates.append(
                _Candidate(
                    parser_element_id=f"p{page.number}-block-{block.get('number', block_index)}",
                    element_type=element_type,
                    text=text,
                    bbox=self._bbox_tuple(block["bbox"]),
                    related_element_id=caption_relationships.get(block_index),
                )
            )

        candidates.sort(
            key=lambda candidate: (
                float("inf") if candidate.bbox is None else candidate.bbox[1],
                float("inf") if candidate.bbox is None else candidate.bbox[0],
                candidate.parser_element_id,
            )
        )
        section_title: str | None = None
        result: list[EvidenceUnit] = []
        page_width = float(page.cropbox.width)
        page_height = float(page.cropbox.height)
        for reading_order, candidate in enumerate(candidates):
            if candidate.element_type is ElementType.HEADING:
                section_title = candidate.text
            result.append(
                self._candidate_to_unit(
                    candidate,
                    manifest=manifest,
                    page_index=page.number,
                    page_width=page_width,
                    page_height=page_height,
                    page_rotation=cast(Literal[0, 90, 180, 270], page.rotation),
                    reading_order=reading_order,
                    section_title=section_title,
                )
            )
        return result, issues

    def _candidate_to_unit(
        self,
        candidate: _Candidate,
        *,
        manifest: IngestionManifest,
        page_index: int,
        page_width: float,
        page_height: float,
        page_rotation: Literal[0, 90, 180, 270],
        reading_order: int,
        section_title: str | None,
    ) -> EvidenceUnit:
        bbox = candidate.bbox
        normalized: NormalizedBoundingBox | None = None
        source_region: SourceRegion | None = None
        precision = AnchorPrecision.PAGE
        if bbox is not None and self._bbox_within_page(bbox, page_width, page_height):
            source_bbox = SourceBoundingBox(x0=bbox[0], y0=bbox[1], x1=bbox[2], y1=bbox[3])
            source_region = SourceRegion(
                bbox=source_bbox,
                coordinate_system=SourceCoordinateSystem.PYMUPDF_POINTS_TOP_LEFT_UNROTATED,
                page_width=page_width,
                page_height=page_height,
                page_rotation=page_rotation,
            )
            normalized = NormalizedBoundingBox(
                x0=round(bbox[0] / page_width, 8),
                y0=round(bbox[1] / page_height, 8),
                x1=round(bbox[2] / page_width, 8),
                y1=round(bbox[3] / page_height, 8),
            )
            precision = AnchorPrecision.REGION
        identity = "|".join(
            (
                manifest.document_version,
                candidate.parser_element_id,
                REPRESENTATION_VERSION,
            )
        )
        evidence_id = f"ev_{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:32]}"
        return EvidenceUnit(
            evidence_id=evidence_id,
            document_id=manifest.document_id,
            document_sha256=manifest.document_sha256,
            document_version=manifest.document_version,
            page_index=page_index,
            element_type=candidate.element_type,
            section_title=section_title,
            text=candidate.text,
            anchor_precision=precision,
            bbox=normalized,
            coordinate_system=(
                CoordinateSystem.NORMALIZED_TOP_LEFT if normalized is not None else None
            ),
            source_region=source_region,
            parser_element_id=candidate.parser_element_id,
            reading_order=reading_order,
            related_element_id=candidate.related_element_id,
            table=candidate.table,
            versions=RepresentationVersions(
                parser=f"pymupdf:{pymupdf.__version__}",
                representation=REPRESENTATION_VERSION,
            ),
        )

    @staticmethod
    def _bbox_tuple(value: object) -> tuple[float, float, float, float]:
        rect = pymupdf.Rect(value)  # type: ignore[no-untyped-call]
        return float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)

    @staticmethod
    def _bbox_within_page(
        bbox: tuple[float, float, float, float], page_width: float, page_height: float
    ) -> bool:
        x0, y0, x1, y1 = bbox
        return 0 <= x0 < x1 <= page_width and 0 <= y0 < y1 <= page_height

    @staticmethod
    def _block_text(block: dict[str, Any]) -> str:
        lines = []
        for line in block.get("lines", []):
            text = "".join(str(span.get("text", "")) for span in line.get("spans", []))
            if text.strip():
                lines.append(text.strip())
        return "\n".join(lines).strip()

    @staticmethod
    def _caption_blocks(blocks: list[dict[str, Any]]) -> dict[int, str]:
        result: dict[int, str] = {}
        for index, block in enumerate(blocks):
            match = _CAPTION.match(PyMuPDFParser._block_text(block))
            if match:
                result[index] = match.group("kind").casefold()
        return result

    @staticmethod
    def _nearest_caption(
        captions: dict[int, str],
        blocks: list[dict[str, Any]],
        kind: str,
        bbox: tuple[float, float, float, float],
    ) -> int | None:
        x0, y0, x1, y1 = bbox
        candidates: list[tuple[float, int]] = []
        for index, caption_kind in captions.items():
            if caption_kind != kind:
                continue
            cx0, cy0, cx1, cy1 = PyMuPDFParser._bbox_tuple(blocks[index]["bbox"])
            horizontal_overlap = max(0.0, min(x1, cx1) - max(x0, cx0))
            if horizontal_overlap == 0:
                continue
            vertical_gap = min(abs(cy0 - y1), abs(y0 - cy1))
            if vertical_gap <= 72.0:
                candidates.append((vertical_gap, index))
        candidates.sort()
        if not candidates:
            return None
        if len(candidates) > 1 and abs(candidates[0][0] - candidates[1][0]) < 1.0:
            return None
        return candidates[0][1]

    @staticmethod
    def _inside_table(
        bbox: tuple[float, float, float, float],
        tables: list[tuple[float, float, float, float]],
    ) -> bool:
        block = pymupdf.Rect(bbox)  # type: ignore[no-untyped-call]
        if block.is_empty:
            return False
        for table_bbox in tables:
            table_rect = pymupdf.Rect(table_bbox)  # type: ignore[no-untyped-call]
            intersection = block & table_rect
            if not intersection.is_empty and intersection.get_area() / block.get_area() >= 0.5:
                return True
        return False

    @staticmethod
    def _heading_indexes(
        blocks: list[dict[str, Any]],
        table_rects: list[tuple[float, float, float, float]],
    ) -> set[int]:
        sizes: list[float] = []
        maxima: dict[int, float] = {}
        bold: dict[int, bool] = {}
        for index, block in enumerate(blocks):
            if PyMuPDFParser._inside_table(PyMuPDFParser._bbox_tuple(block["bbox"]), table_rects):
                continue
            spans = [span for line in block.get("lines", []) for span in line.get("spans", [])]
            block_sizes = [
                float(span.get("size", 0.0)) for span in spans if span.get("text", "").strip()
            ]
            if not block_sizes:
                continue
            sizes.extend(block_sizes)
            maxima[index] = max(block_sizes)
            bold[index] = any(int(span.get("flags", 0)) & (1 << 4) for span in spans)
        if not sizes:
            return set()
        body_size = median(sizes)
        headings: set[int] = set()
        for index, maximum in maxima.items():
            text = PyMuPDFParser._block_text(blocks[index])
            if len(text) <= 200 and (
                maximum >= body_size * 1.35 or (bold[index] and maximum >= body_size * 1.15)
            ):
                headings.add(index)
        return headings

    @staticmethod
    def _clean_cell(value: object) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @classmethod
    def _normalize_rows(
        cls, rows: object, row_count: int, column_count: int
    ) -> list[list[str | None]]:
        raw_rows = list(rows) if isinstance(rows, list) else []
        normalized: list[list[str | None]] = []
        for row_index in range(row_count):
            raw_row = raw_rows[row_index] if row_index < len(raw_rows) else []
            values = list(raw_row) if isinstance(raw_row, list) else []
            normalized.append(
                [
                    cls._clean_cell(values[column_index]) if column_index < len(values) else None
                    for column_index in range(column_count)
                ]
            )
        return normalized

    @staticmethod
    def _table_markdown(table: TableStructure) -> str:
        def escaped(value: str | None) -> str:
            return (value or "").replace("|", "\\|").replace("\n", "<br>")

        headers = table.headers
        rows = table.rows
        if not table.header_external and rows:
            headers = rows[0]
            rows = rows[1:]
        lines = [
            f"| {' | '.join(escaped(value) for value in headers)} |",
            f"| {' | '.join('---' for _ in range(table.column_count))} |",
        ]
        lines.extend(f"| {' | '.join(escaped(value) for value in row)} |" for row in rows)
        return "\n".join(lines)
