"""Application services for bounded PDF intake and explicit parsing."""

from contextlib import suppress
from datetime import UTC, datetime
from typing import BinaryIO

from evidence_rag.documents.identity import sanitize_filename
from evidence_rag.documents.models import (
    DocumentIntakeResponse,
    DocumentMetadataResponse,
    DocumentParseResponse,
    DocumentStatusResponse,
    EvidenceArtifact,
    IngestionManifest,
    IngestionState,
    ParseIssue,
)
from evidence_rag.documents.parser import ParserError, PdfParser
from evidence_rag.documents.storage import (
    ArtifactNotFoundError,
    LocalArtifactStore,
    StorageError,
    UploadTooLargeError,
)


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
