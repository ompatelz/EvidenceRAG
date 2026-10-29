"""Typed contracts for safe PDF intake and version manifests."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from evidence_rag.evidence import AssetReference, EvidenceUnit, Sha256Hex, StableIdentifier

DocumentVersion = Annotated[
    str,
    StringConstraints(pattern=r"^sha256:[a-f0-9]{64}$"),
]
SafeFilename = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


class IngestionState(StrEnum):
    """Lifecycle states implemented by intake and explicit parsing."""

    RECEIVED = "received"
    PARSING = "parsing"
    PARSED = "parsed"
    PARTIAL = "partial"
    FAILED = "failed"


class ParserMetadata(BaseModel):
    """Pinned parser and representation versions used for one attempt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: SafeFilename
    version: SafeFilename
    representation_version: SafeFilename


class ParseIssue(BaseModel):
    """Bounded, source-text-free parser diagnostic."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: SafeFilename
    message: SafeFilename
    page_index: int | None = Field(default=None, ge=0)


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
    updated_at: datetime | None = None
    parser: ParserMetadata | None = None
    evidence_count: int = Field(default=0, ge=0)
    failure_reason: SafeFilename | None = None

    @model_validator(mode="after")
    def validate_version_identity(self) -> Self:
        """Keep version labels content-addressed and unambiguous."""
        if self.document_version != f"sha256:{self.document_sha256}":
            raise ValueError("document_version must equal sha256:<document_sha256>")
        if self.state is IngestionState.RECEIVED:
            if self.parser is not None or self.evidence_count or self.failure_reason is not None:
                raise ValueError("received state must not claim parser results")
        elif self.parser is None:
            raise ValueError("post-intake states require parser metadata")
        if self.state in {IngestionState.PARTIAL, IngestionState.FAILED}:
            if self.failure_reason is None:
                raise ValueError("partial and failed states require a failure reason")
        elif self.failure_reason is not None:
            raise ValueError("non-failure states must not include a failure reason")
        return self


class EvidenceArtifact(BaseModel):
    """Versioned, inspectable evidence produced by one parser attempt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Annotated[int, Field(ge=1, le=1)] = 1
    document_id: StableIdentifier
    document_version: DocumentVersion
    document_sha256: Sha256Hex
    parser: ParserMetadata
    page_count: int = Field(gt=0)
    units: list[EvidenceUnit]
    issues: list[ParseIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unit_provenance(self) -> Self:
        """Prevent a persisted artifact from mixing document versions."""
        for unit in self.units:
            if unit.document_id != self.document_id:
                raise ValueError("evidence document_id must match its artifact")
            if unit.document_version != self.document_version:
                raise ValueError("evidence document_version must match its artifact")
            if unit.document_sha256 != self.document_sha256:
                raise ValueError("evidence document_sha256 must match its artifact")
        return self


class DocumentParseResponse(BaseModel):
    """Client-safe result of one synchronous parsing attempt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: StableIdentifier
    document_version: DocumentVersion
    state: IngestionState
    parser: ParserMetadata
    evidence_count: int = Field(ge=0)
    issues: list[ParseIssue] = Field(default_factory=list)


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
