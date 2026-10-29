"""Application services for bounded PDF intake and explicit parsing."""

from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from evidence_rag.documents.identity import sanitize_filename
from evidence_rag.documents.models import (
    DocumentIntakeResponse,
    DocumentMetadataResponse,
    DocumentParseResponse,
    DocumentRenderResponse,
    DocumentStatusResponse,
    EvidenceAnchorResponse,
    EvidenceArtifact,
    IngestionManifest,
    IngestionState,
    PagePreviewArtifact,
    PagePreviewManifest,
    ParseIssue,
)
from evidence_rag.documents.parser import ParserError, PdfParser
from evidence_rag.documents.rendering import (
    PageRenderer,
    RenderError,
    normalized_to_pixels,
    rotate_normalized_bbox,
)
from evidence_rag.documents.storage import (
    ArtifactNotFoundError,
    LocalArtifactStore,
    StorageError,
    UploadTooLargeError,
)
from evidence_rag.evidence import AnchorPrecision


class IntakeError(RuntimeError):
    """Safe, client-facing intake failure."""

    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class DocumentIntakeService:
    """Coordinate validation and storage without parsing PDF content."""

    def __init__(self, store: LocalArtifactStore) -> None:
        self.store = store

    def accept(self, stream: BinaryIO, filename: str | None) -> DocumentIntakeResponse:
        sanitized_filename = sanitize_filename(filename)
        original_filename = (filename or "document.pdf").strip()[:128] or "document.pdf"
        try:
            manifest, duplicate = self.store.ingest(
                stream,
                original_filename=original_filename,
                sanitized_filename=sanitized_filename,
            )
        except UploadTooLargeError as exc:
            raise IntakeError(
                "upload_too_large",
                "The PDF exceeds the configured upload limit.",
                413,
            ) from exc
        except ValueError as exc:
            code = str(exc)
            messages = {
                "empty_pdf": "The uploaded PDF is empty.",
                "invalid_pdf_signature": "The upload does not have a valid PDF signature.",
                "truncated_pdf": "The uploaded PDF appears truncated or corrupted.",
            }
            raise IntakeError(code, messages.get(code, "The PDF is invalid."), 400) from exc
        except (OSError, StorageError) as exc:
            raise IntakeError(
                "storage_failure",
                "The PDF could not be stored safely; no successful intake was recorded.",
                500,
            ) from exc
        return DocumentIntakeResponse.from_manifest(manifest, duplicate=duplicate)

    def metadata(self, document_id: str, document_sha256: str) -> DocumentMetadataResponse:
        try:
            manifest = self.store.get_manifest(document_id, document_sha256)
        except ArtifactNotFoundError as exc:
            raise IntakeError("document_not_found", "Document version not found.", 404) from exc
        return DocumentMetadataResponse.from_manifest(manifest)

    def status(self, document_id: str, document_sha256: str) -> DocumentStatusResponse:
        try:
            manifest = self.store.get_manifest(document_id, document_sha256)
        except ArtifactNotFoundError as exc:
            raise IntakeError("document_not_found", "Document version not found.", 404) from exc
        return DocumentStatusResponse.from_manifest(manifest)


class DocumentParsingService:
    """Parse accepted versions and persist evidence without claiming readiness."""

    def __init__(self, store: LocalArtifactStore, parser: PdfParser) -> None:
        self.store = store
        self.parser = parser

    def parse(self, document_id: str, document_sha256: str) -> DocumentParseResponse:
        try:
            manifest = self.store.get_manifest(document_id, document_sha256)
        except ArtifactNotFoundError as exc:
            raise IntakeError("document_not_found", "Document version not found.", 404) from exc

        if manifest.state in {IngestionState.PARSED, IngestionState.PARTIAL}:
            try:
                artifact = self.store.get_evidence(document_id, document_sha256)
            except ArtifactNotFoundError as exc:
                raise IntakeError(
                    "evidence_not_found",
                    "Parsed evidence is missing for this document version.",
                    409,
                ) from exc
            return self._response(manifest, artifact.issues)
        if manifest.state in {IngestionState.PARSING, IngestionState.FAILED}:
            issue = ParseIssue(
                code=manifest.failure_reason or "parsing_incomplete",
                message="The prior parsing attempt did not complete successfully.",
            )
            return self._response(manifest, [issue])

        parsing_manifest = manifest.model_copy(
            update={
                "state": IngestionState.PARSING,
                "parser": self.parser.metadata,
                "updated_at": datetime.now(UTC),
            }
        )
        self._update_manifest(parsing_manifest)
        try:
            result = self.parser.parse(self.store.source_path(parsing_manifest), parsing_manifest)
        except ParserError as exc:
            failed = parsing_manifest.model_copy(
                update={
                    "state": IngestionState.FAILED,
                    "failure_reason": exc.code,
                    "updated_at": datetime.now(UTC),
                }
            )
            self._update_manifest(failed)
            return self._response(
                failed,
                [ParseIssue(code=exc.code, message=exc.message)],
            )
        except Exception:
            failed = parsing_manifest.model_copy(
                update={
                    "state": IngestionState.FAILED,
                    "failure_reason": "parser_unexpected_failure",
                    "updated_at": datetime.now(UTC),
                }
            )
            self._update_manifest(failed)
            return self._response(
                failed,
                [
                    ParseIssue(
                        code="parser_unexpected_failure",
                        message="The parser failed unexpectedly without exposing source data.",
                    )
                ],
            )

        issues = list(result.issues)
        if result.successful_pages == 0:
            issues.append(
                ParseIssue(
                    code="all_pages_failed",
                    message="No PDF page could be parsed successfully.",
                )
            )
            state = IngestionState.FAILED
        elif issues or not result.units:
            if not result.units and not issues:
                issues.append(
                    ParseIssue(
                        code="empty_extraction",
                        message="The PDF produced no supported evidence units.",
                    )
                )
            state = IngestionState.PARTIAL
        else:
            state = IngestionState.PARSED

        failure_reason = (
            issues[0].code if state in {IngestionState.PARTIAL, IngestionState.FAILED} else None
        )
        artifact = EvidenceArtifact(
            document_id=manifest.document_id,
            document_version=manifest.document_version,
            document_sha256=manifest.document_sha256,
            parser=self.parser.metadata,
            page_count=result.page_count,
            units=list(result.units),
            issues=issues,
        )
        try:
            self.store.write_evidence(artifact)
            final_manifest = parsing_manifest.model_copy(
                update={
                    "state": state,
                    "evidence_count": len(result.units),
                    "failure_reason": failure_reason,
                    "updated_at": datetime.now(UTC),
                }
            )
            self.store.update_manifest(final_manifest)
        except (ArtifactNotFoundError, OSError, StorageError) as exc:
            failed = parsing_manifest.model_copy(
                update={
                    "state": IngestionState.FAILED,
                    "failure_reason": "evidence_persistence_failed",
                    "updated_at": datetime.now(UTC),
                }
            )
            with suppress(ArtifactNotFoundError, OSError, StorageError):
                self.store.update_manifest(failed)
            raise IntakeError(
                "evidence_persistence_failed",
                "Extracted evidence could not be persisted safely.",
                500,
            ) from exc
        return self._response(final_manifest, issues)

    def evidence(self, document_id: str, document_sha256: str) -> EvidenceArtifact:
        try:
            return self.store.get_evidence(document_id, document_sha256)
        except ArtifactNotFoundError as exc:
            raise IntakeError("evidence_not_found", "Evidence artifact not found.", 404) from exc

    def _update_manifest(self, manifest: IngestionManifest) -> None:
        try:
            self.store.update_manifest(manifest)
        except (ArtifactNotFoundError, OSError, StorageError) as exc:
            raise IntakeError(
                "manifest_update_failed",
                "The parsing lifecycle could not be recorded safely.",
                500,
            ) from exc

    @staticmethod
    def _response(manifest: IngestionManifest, issues: list[ParseIssue]) -> DocumentParseResponse:
        if manifest.parser is None:
            raise RuntimeError("post-intake response requires parser metadata")
        return DocumentParseResponse(
            document_id=manifest.document_id,
            document_version=manifest.document_version,
            state=manifest.state,
            parser=manifest.parser,
            evidence_count=manifest.evidence_count,
            issues=issues,
        )


class DocumentRenderingService:
    """Render version-scoped previews and resolve honest evidence anchors."""

    def __init__(self, store: LocalArtifactStore, renderer: PageRenderer) -> None:
        self.store = store
        self.renderer = renderer

    def render(self, document_id: str, document_sha256: str) -> DocumentRenderResponse:
        manifest = self._manifest(document_id, document_sha256)
        if manifest.state not in {IngestionState.PARSED, IngestionState.PARTIAL}:
            raise IntakeError(
                "document_not_parsed",
                "Document evidence must be parsed before page previews are rendered.",
                409,
            )
        try:
            existing = self.store.get_page_manifest(document_id, document_sha256)
        except ArtifactNotFoundError:
            existing = None
        if existing is not None:
            if existing.renderer != self.renderer.metadata:
                raise IntakeError(
                    "render_profile_conflict",
                    "This version already has previews from another rendering profile.",
                    409,
                )
            return self._response(existing)

        try:
            with self.store.stage_page_previews(document_id, document_sha256) as staging:
                artifact = self.renderer.render(self.store.source_path(manifest), manifest, staging)
                published = self.store.publish_page_previews(artifact, staging)
        except RenderError as exc:
            raise IntakeError(exc.code, exc.message, 422) from exc
        except (ArtifactNotFoundError, OSError, StorageError) as exc:
            raise IntakeError(
                "preview_persistence_failed",
                "Page previews could not be persisted safely.",
                500,
            ) from exc
        except Exception as exc:
            raise IntakeError(
                "renderer_unexpected_failure",
                "Page rendering failed unexpectedly without exposing source data.",
                500,
            ) from exc
        return self._response(published)

    def pages(self, document_id: str, document_sha256: str) -> PagePreviewManifest:
        try:
            return self.store.get_page_manifest(document_id, document_sha256)
        except ArtifactNotFoundError as exc:
            raise IntakeError("previews_not_found", "Page previews were not found.", 404) from exc

    def preview(
        self, document_id: str, document_sha256: str, page_index: int
    ) -> tuple[PagePreviewArtifact, Path]:
        artifact = self.pages(document_id, document_sha256)
        if page_index < 0 or page_index >= len(artifact.pages):
            raise IntakeError("page_not_found", "Page preview was not found.", 404)
        try:
            path = self.store.preview_path(document_id, document_sha256, page_index)
        except ArtifactNotFoundError as exc:
            raise IntakeError("preview_not_found", "Page preview was not found.", 404) from exc
        return artifact.pages[page_index], path

    def anchor(
        self,
        document_id: str,
        document_sha256: str,
        evidence_id: str,
    ) -> EvidenceAnchorResponse:
        try:
            evidence = self.store.get_evidence(document_id, document_sha256)
        except ArtifactNotFoundError as exc:
            raise IntakeError("evidence_not_found", "Evidence artifact not found.", 404) from exc
        pages = self.pages(document_id, document_sha256)
        unit = next((item for item in evidence.units if item.evidence_id == evidence_id), None)
        if unit is None:
            raise IntakeError("evidence_not_found", "Evidence unit not found.", 404)
        if unit.page_index >= len(pages.pages):
            raise IntakeError(
                "anchor_page_mismatch",
                "Evidence page does not exist in the rendered preview set.",
                409,
            )
        page = pages.pages[unit.page_index]
        if unit.anchor_precision is AnchorPrecision.UNAVAILABLE:
            return EvidenceAnchorResponse(
                evidence_id=unit.evidence_id,
                document_id=unit.document_id,
                document_version=unit.document_version,
                page_index=unit.page_index,
                precision=unit.anchor_precision,
            )
        if unit.anchor_precision is AnchorPrecision.PAGE:
            return EvidenceAnchorResponse(
                evidence_id=unit.evidence_id,
                document_id=unit.document_id,
                document_version=unit.document_version,
                page_index=unit.page_index,
                precision=unit.anchor_precision,
                preview_asset_id=page.asset_id,
            )
        if unit.bbox is None or unit.source_region is None:
            raise IntakeError(
                "anchor_geometry_missing",
                "Region evidence is missing reproducible source geometry.",
                409,
            )
        source = unit.source_region
        if (
            abs(source.page_width - page.source_width) > 0.01
            or abs(source.page_height - page.source_height) > 0.01
            or source.page_rotation != page.rotation
        ):
            raise IntakeError(
                "anchor_geometry_mismatch",
                "Evidence geometry does not match the rendered source page.",
                409,
            )
        display_bbox = rotate_normalized_bbox(unit.bbox, page.rotation)
        return EvidenceAnchorResponse(
            evidence_id=unit.evidence_id,
            document_id=unit.document_id,
            document_version=unit.document_version,
            page_index=unit.page_index,
            precision=unit.anchor_precision,
            preview_asset_id=page.asset_id,
            source_bbox=unit.bbox,
            display_bbox=display_bbox,
            pixel_bbox=normalized_to_pixels(
                display_bbox,
                width=page.width_pixels,
                height=page.height_pixels,
            ),
        )

    def _manifest(self, document_id: str, document_sha256: str) -> IngestionManifest:
        try:
            return self.store.get_manifest(document_id, document_sha256)
        except ArtifactNotFoundError as exc:
            raise IntakeError("document_not_found", "Document version not found.", 404) from exc

    @staticmethod
    def _response(artifact: PagePreviewManifest) -> DocumentRenderResponse:
        return DocumentRenderResponse(
            document_id=artifact.document_id,
            document_version=artifact.document_version,
            renderer=artifact.renderer,
            page_count=len(artifact.pages),
            pages=artifact.pages,
        )
