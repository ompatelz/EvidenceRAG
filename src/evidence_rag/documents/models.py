"""Typed contracts for safe PDF intake and version manifests."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from evidence_rag.evidence import AssetReference, Sha256Hex, StableIdentifier

DocumentVersion = Annotated[
    str,
    StringConstraints(pattern=r"^sha256:[a-f0-9]{64}$"),
]
SafeFilename = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


class IngestionState(StrEnum):
    """Lifecycle states implemented by the intake-only slice."""

    RECEIVED = "received"


class IngestionManifest(BaseModel):
    """Atomic record of one accepted immutable PDF version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Annotated[int, Field(ge=1, le=1)] = 1
    document_id: StableIdentifier
    document_version: DocumentVersion
    document_sha256: Sha256Hex
    original_filename: SafeFilename
    sanitized_filename: SafeFilename
    size_bytes: int = Field(gt=0)
    state: IngestionState
    source_asset_id: AssetReference
    created_at: datetime

    @model_validator(mode="after")
    def validate_version_identity(self) -> Self:
        """Keep version labels content-addressed and unambiguous."""
        if self.document_version != f"sha256:{self.document_sha256}":
            raise ValueError("document_version must equal sha256:<document_sha256>")
        return self


class DocumentIntakeResponse(BaseModel):
    """Client-safe result for a new or idempotent upload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: StableIdentifier
    document_version: DocumentVersion
    document_sha256: Sha256Hex
    state: IngestionState
    sanitized_filename: SafeFilename
    size_bytes: int = Field(gt=0)
    source_asset_id: AssetReference
    duplicate: bool

    @classmethod
    def from_manifest(
        cls, manifest: IngestionManifest, *, duplicate: bool
    ) -> "DocumentIntakeResponse":
        """Project a private storage manifest into the public intake contract."""
        return cls(
            document_id=manifest.document_id,
            document_version=manifest.document_version,
            document_sha256=manifest.document_sha256,
            state=manifest.state,
            sanitized_filename=manifest.sanitized_filename,
            size_bytes=manifest.size_bytes,
            source_asset_id=manifest.source_asset_id,
            duplicate=duplicate,
        )


class DocumentMetadataResponse(BaseModel):
    """Client-safe metadata for one immutable version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: StableIdentifier
    document_version: DocumentVersion
    document_sha256: Sha256Hex
    sanitized_filename: SafeFilename
    size_bytes: int = Field(gt=0)
    source_asset_id: AssetReference
    created_at: datetime

    @classmethod
    def from_manifest(cls, manifest: IngestionManifest) -> "DocumentMetadataResponse":
        return cls(
            document_id=manifest.document_id,
            document_version=manifest.document_version,
            document_sha256=manifest.document_sha256,
            sanitized_filename=manifest.sanitized_filename,
            size_bytes=manifest.size_bytes,
            source_asset_id=manifest.source_asset_id,
            created_at=manifest.created_at,
        )


class DocumentStatusResponse(BaseModel):
    """Truthful lifecycle status for one immutable version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: StableIdentifier
    document_version: DocumentVersion
    state: IngestionState

    @classmethod
    def from_manifest(cls, manifest: IngestionManifest) -> "DocumentStatusResponse":
        return cls(
            document_id=manifest.document_id,
            document_version=manifest.document_version,
            state=manifest.state,
        )
