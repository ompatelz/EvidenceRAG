"""Application service for bounded, idempotent PDF intake."""

from typing import BinaryIO

from evidence_rag.documents.identity import sanitize_filename
from evidence_rag.documents.models import (
    DocumentIntakeResponse,
    DocumentMetadataResponse,
    DocumentStatusResponse,
)
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
