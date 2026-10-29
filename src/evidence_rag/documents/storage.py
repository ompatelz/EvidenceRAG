"""Confined local artifact storage with atomic publication and cleanup."""

import hashlib
import json
import os
import re
import shutil
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, cast

from pydantic import BaseModel, ValidationError

from evidence_rag.documents.identity import logical_document_id
from evidence_rag.documents.models import (
    EvidenceArtifact,
    IngestionManifest,
    IngestionState,
    PagePreviewManifest,
)

_DOCUMENT_ID = re.compile(r"^doc_[a-f0-9]{24}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
ReplaceFunction = Callable[[Path, Path], None]


class StorageError(RuntimeError):
    """Safe storage failure that does not reveal private paths."""


class ArtifactNotFoundError(LookupError):
    """Requested document/version does not exist."""


class UploadTooLargeError(ValueError):
    """The streamed file exceeded the configured byte limit."""


class LocalArtifactStore:
    """Store immutable PDF versions under generated allowlisted identifiers."""

    def __init__(
        self,
        root: Path,
        *,
        max_upload_bytes: int,
        chunk_bytes: int,
        replace: ReplaceFunction = os.replace,
    ) -> None:
        self.root = root.resolve()
        self.max_upload_bytes = max_upload_bytes
        self.chunk_bytes = chunk_bytes
        self._replace = replace

    def ingest(
        self,
        stream: BinaryIO,
        *,
        original_filename: str,
        sanitized_filename: str,
    ) -> tuple[IngestionManifest, bool]:
        """Stream, hash, validate, and atomically publish one PDF version."""
        self.root.mkdir(parents=True, exist_ok=True)
        staging_dir = self._safe_path(".staging")
        staging_dir.mkdir(parents=True, exist_ok=True)
        descriptor, raw_staging_path = tempfile.mkstemp(prefix="upload-", dir=staging_dir)
        staging_path = Path(raw_staging_path)
        digest = hashlib.sha256()
        size_bytes = 0
        try:
            with os.fdopen(descriptor, "wb") as target:
                while chunk := stream.read(self.chunk_bytes):
                    size_bytes += len(chunk)
                    if size_bytes > self.max_upload_bytes:
                        raise UploadTooLargeError
                    digest.update(chunk)
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())

            if size_bytes == 0:
                raise ValueError("empty_pdf")
            self._validate_pdf_markers(staging_path, size_bytes)
            document_sha256 = digest.hexdigest()

            duplicate = self.find_by_hash(document_sha256)
            if duplicate is not None:
                return duplicate, True

            document_id = logical_document_id(sanitized_filename)
            manifest = IngestionManifest(
                document_id=document_id,
                document_version=f"sha256:{document_sha256}",
                document_sha256=document_sha256,
                original_filename=original_filename,
                sanitized_filename=sanitized_filename,
                size_bytes=size_bytes,
                state=IngestionState.RECEIVED,
                source_asset_id=(f"asset:pdf:{document_id}:{document_sha256[:24]}"),
                created_at=datetime.now(UTC),
            )
            return self._publish(staging_path, manifest), False
        finally:
            staging_path.unlink(missing_ok=True)

    def find_by_hash(self, document_sha256: str) -> IngestionManifest | None:
        """Find an already-published version for global content idempotency."""
        if not _SHA256.fullmatch(document_sha256):
            return None
        documents_root = self._safe_path("documents")
        if not documents_root.is_dir():
            return None
        candidates = list(documents_root.glob("doc_*/versions/*/manifest.json"))
        candidates.extend(documents_root.glob("doc_*/versions/*/intake.json"))
        visited: set[tuple[str, str]] = set()
        for manifest_path in candidates:
            try:
                manifest = self._read_manifest(manifest_path)
            except (OSError, ValidationError, json.JSONDecodeError):
                continue
            identity = manifest.document_id, manifest.document_sha256
            if identity in visited:
                continue
            visited.add(identity)
            if manifest.document_sha256 == document_sha256:
                try:
                    return self.get_manifest_or_recover(*identity)
                except ArtifactNotFoundError:
                    continue
        return None

    def get_manifest(self, document_id: str, document_sha256: str) -> IngestionManifest:
        """Load one allowlisted version without accepting arbitrary path segments."""
        if not _DOCUMENT_ID.fullmatch(document_id) or not _SHA256.fullmatch(document_sha256):
            raise ArtifactNotFoundError
        manifest_path = self._version_path(document_id, document_sha256) / "manifest.json"
        try:
            return self._read_manifest(manifest_path)
        except (OSError, ValidationError, json.JSONDecodeError) as exc:
            raise ArtifactNotFoundError from exc

    def get_manifest_or_recover(self, document_id: str, document_sha256: str) -> IngestionManifest:
        """Recover a missing mutable manifest from its immutable intake snapshot."""
        try:
            return self.get_manifest(document_id, document_sha256)
        except ArtifactNotFoundError:
            pass
        version_dir = self._version_path(document_id, document_sha256)
        source = version_dir / "source.pdf"
        try:
            intake = self._read_manifest(version_dir / "intake.json")
        except (OSError, ValidationError, json.JSONDecodeError) as exc:
            raise ArtifactNotFoundError from exc
        if (
            intake.state is not IngestionState.RECEIVED
            or intake.document_id != document_id
            or intake.document_sha256 != document_sha256
            or not source.is_file()
        ):
            raise ArtifactNotFoundError
        self._atomic_write_model(version_dir / "manifest.json", intake)
        return intake

    def source_path(self, manifest: IngestionManifest) -> Path:
        """Resolve the private source path for an already-validated manifest."""
        path = self._version_path(manifest.document_id, manifest.document_sha256) / "source.pdf"
        if not path.is_file():
            raise ArtifactNotFoundError
        return path

    def validate_source_integrity(self, manifest: IngestionManifest) -> None:
        """Recheck immutable source size and hash before a new ingestion attempt."""
        path = self.source_path(manifest)
        try:
            if path.stat().st_size != manifest.size_bytes:
                raise StorageError("source artifact size no longer matches its manifest")
            if self._file_sha256(path) != manifest.document_sha256:
                raise StorageError("source artifact hash no longer matches its manifest")
        except OSError as exc:
            raise StorageError("source artifact could not be validated") from exc

    def update_manifest(self, manifest: IngestionManifest) -> None:
        """Atomically replace the lifecycle record for one existing version."""
        version_dir = self._version_path(manifest.document_id, manifest.document_sha256)
        if not (version_dir / "source.pdf").is_file():
            raise ArtifactNotFoundError
        self._atomic_write_model(version_dir / "manifest.json", manifest)

    def write_evidence(self, artifact: EvidenceArtifact) -> None:
        """Atomically persist evidence beside its immutable document version."""
        version_dir = self._version_path(artifact.document_id, artifact.document_sha256)
        if not (version_dir / "source.pdf").is_file():
            raise ArtifactNotFoundError
        self._atomic_write_model(version_dir / "evidence.json", artifact)

    def get_evidence(self, document_id: str, document_sha256: str) -> EvidenceArtifact:
        """Load persisted evidence using allowlisted path components only."""
        if not _DOCUMENT_ID.fullmatch(document_id) or not _SHA256.fullmatch(document_sha256):
            raise ArtifactNotFoundError
        path = self._version_path(document_id, document_sha256) / "evidence.json"
        try:
            return EvidenceArtifact.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as exc:
            raise ArtifactNotFoundError from exc

    @contextmanager
    def stage_page_previews(self, document_id: str, document_sha256: str) -> Iterator[Path]:
        """Allocate and clean one private same-filesystem rendering stage."""
        version_dir = self._version_path(document_id, document_sha256)
        if not (version_dir / "source.pdf").is_file():
            raise ArtifactNotFoundError
        staging_root = Path(tempfile.mkdtemp(prefix=".render-", dir=version_dir))
        try:
            yield staging_root / "pages"
        finally:
            shutil.rmtree(staging_root, ignore_errors=True)

    def publish_page_previews(
        self, artifact: PagePreviewManifest, staged_pages: Path
    ) -> PagePreviewManifest:
        """Publish a complete preview directory with its manifest as one rename."""
        version_dir = self._version_path(artifact.document_id, artifact.document_sha256)
        if not (version_dir / "source.pdf").is_file() or not staged_pages.is_dir():
            raise ArtifactNotFoundError
        for page in artifact.pages:
            if not (staged_pages / f"page-{page.page_index}.png").is_file():
                raise StorageError("rendered page set is incomplete")
        self._atomic_write_model(staged_pages / "manifest.json", artifact)
        destination = version_dir / "pages"
        try:
            self._replace(staged_pages, destination)
        except FileExistsError:
            existing = self.get_page_manifest(artifact.document_id, artifact.document_sha256)
            if existing != artifact:
                raise StorageError("another rendering profile is already published") from None
            return existing
        except OSError as exc:
            raise StorageError("could not publish rendered page previews") from exc
        return artifact

    def get_page_manifest(self, document_id: str, document_sha256: str) -> PagePreviewManifest:
        """Load the version-scoped page-preview index."""
        if not _DOCUMENT_ID.fullmatch(document_id) or not _SHA256.fullmatch(document_sha256):
            raise ArtifactNotFoundError
        path = self._version_path(document_id, document_sha256) / "pages" / "manifest.json"
        try:
            return PagePreviewManifest.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as exc:
            raise ArtifactNotFoundError from exc

    def preview_path(self, document_id: str, document_sha256: str, page_index: int) -> Path:
        """Resolve one manifest-backed PNG without accepting path fragments."""
        manifest = self.get_page_manifest(document_id, document_sha256)
        if page_index < 0 or page_index >= len(manifest.pages):
            raise ArtifactNotFoundError
        path = (
            self._version_path(document_id, document_sha256) / "pages" / (f"page-{page_index}.png")
        )
        if not path.is_file():
            raise ArtifactNotFoundError
        try:
            digest = self._file_sha256(path)
        except OSError as exc:
            raise ArtifactNotFoundError from exc
        if digest != manifest.pages[page_index].content_sha256:
            raise ArtifactNotFoundError
        return path

    def remove_derived_artifacts(self, document_id: str, document_sha256: str) -> None:
        """Remove only regenerable evidence, previews, and abandoned rendering stages."""
        version_dir = self._version_path(document_id, document_sha256)
        if not (version_dir / "source.pdf").is_file():
            raise ArtifactNotFoundError
        (version_dir / "evidence.json").unlink(missing_ok=True)
        shutil.rmtree(version_dir / "pages", ignore_errors=True)
        for staging in version_dir.glob(".render-*"):
            if staging.is_dir():
                shutil.rmtree(staging, ignore_errors=True)

    def _publish(self, staging_path: Path, manifest: IngestionManifest) -> IngestionManifest:
        version_dir = self._version_path(manifest.document_id, manifest.document_sha256)
        try:
            version_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            try:
                return self._read_manifest(version_dir / "manifest.json")
            except (OSError, ValidationError, json.JSONDecodeError) as exc:
                raise StorageError("artifact version exists without a valid manifest") from exc

        try:
            self._replace(staging_path, version_dir / "source.pdf")
            self._atomic_write_model(version_dir / "intake.json", manifest)
            self._atomic_write_model(version_dir / "manifest.json", manifest)
            return manifest
        except Exception as exc:
            shutil.rmtree(version_dir, ignore_errors=True)
            self._remove_empty_parents(version_dir.parent, stop=self._safe_path("documents"))
            if isinstance(exc, StorageError):
                raise
            raise StorageError("could not publish the document version") from exc

    def _atomic_write_model(self, destination: Path, model: BaseModel) -> None:
        payload = model.model_dump_json(indent=2).encode("utf-8") + b"\n"
        descriptor, raw_temporary_path = tempfile.mkstemp(
            prefix=".manifest-", suffix=".tmp", dir=destination.parent
        )
        temporary_path = Path(raw_temporary_path)
        try:
            with os.fdopen(descriptor, "wb") as target:
                target.write(payload)
                target.flush()
                os.fsync(target.fileno())
            self._replace(temporary_path, destination)
        finally:
            temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _read_manifest(path: Path) -> IngestionManifest:
        raw = cast(object, json.loads(path.read_text(encoding="utf-8")))
        return IngestionManifest.model_validate(raw)

    @staticmethod
    def _file_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            while chunk := source.read(64 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _validate_pdf_markers(path: Path, size_bytes: int) -> None:
        with path.open("rb") as source:
            header = source.read(8)
            if not re.match(rb"^%PDF-[12]\.[0-9]", header):
                raise ValueError("invalid_pdf_signature")
            source.seek(max(0, size_bytes - 1024))
            trailer = source.read(1024)
            if b"%%EOF" not in trailer:
                raise ValueError("truncated_pdf")

    def _version_path(self, document_id: str, document_sha256: str) -> Path:
        if not _DOCUMENT_ID.fullmatch(document_id) or not _SHA256.fullmatch(document_sha256):
            raise StorageError("invalid generated artifact identifier")
        return self._safe_path("documents", document_id, "versions", document_sha256)

    def _safe_path(self, *parts: str) -> Path:
        candidate = self.root.joinpath(*parts).resolve()
        if not candidate.is_relative_to(self.root):
            raise StorageError("artifact path escaped the configured storage root")
        return candidate

    @staticmethod
    def _remove_empty_parents(start: Path, *, stop: Path) -> None:
        current = start
        while current != stop and current.is_relative_to(stop):
            try:
                current.rmdir()
            except OSError:
                return
            current = current.parent
