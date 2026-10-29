"""Confined local artifact storage with atomic publication and cleanup."""

import hashlib
import json
import os
import re
import shutil
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, cast

from pydantic import ValidationError

from evidence_rag.documents.identity import logical_document_id
from evidence_rag.documents.models import IngestionManifest, IngestionState

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
        for manifest_path in documents_root.glob("doc_*/versions/*/manifest.json"):
            try:
                manifest = self._read_manifest(manifest_path)
            except (OSError, ValidationError, json.JSONDecodeError):
                continue
            if manifest.document_sha256 == document_sha256:
                return manifest
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
            self._atomic_write_manifest(version_dir / "manifest.json", manifest)
            return manifest
        except Exception as exc:
            shutil.rmtree(version_dir, ignore_errors=True)
            self._remove_empty_parents(version_dir.parent, stop=self._safe_path("documents"))
            if isinstance(exc, StorageError):
                raise
            raise StorageError("could not publish the document version") from exc

    def _atomic_write_manifest(self, destination: Path, manifest: IngestionManifest) -> None:
        payload = manifest.model_dump_json(indent=2).encode("utf-8") + b"\n"
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
