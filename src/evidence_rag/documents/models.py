"""Typed contracts for safe PDF intake and version manifests."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from evidence_rag.evidence import (
    AnchorPrecision,
    AssetReference,
    EvidenceUnit,
    NormalizedBoundingBox,
    Sha256Hex,
    StableIdentifier,
)

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


class PageBox(BaseModel):
    """One non-empty PDF box in unrotated PyMuPDF coordinates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    x0: float
    y0: float
    x1: float
    y1: float

    @model_validator(mode="after")
    def validate_ordering(self) -> Self:
        if self.x0 >= self.x1 or self.y0 >= self.y1:
            raise ValueError("page box must be non-empty and ordered")
        return self


class RendererMetadata(BaseModel):
    """Pinned rendering implementation and stable output profile."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: SafeFilename
    version: SafeFilename
    profile: SafeFilename
    dpi: int = Field(ge=36, le=600)


class PagePreviewArtifact(BaseModel):
    """Client-safe metadata for one version-scoped PNG preview."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    page_index: int = Field(ge=0)
    asset_id: AssetReference
    media_type: Literal["image/png"] = "image/png"
    width_pixels: int = Field(gt=0)
    height_pixels: int = Field(gt=0)
    source_width: float = Field(gt=0.0)
    source_height: float = Field(gt=0.0)
    rotation: Literal[0, 90, 180, 270]
    cropbox: PageBox
    mediabox: PageBox
    content_sha256: Sha256Hex


class PagePreviewManifest(BaseModel):
    """Atomic index of every rendered page for one immutable PDF version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Annotated[int, Field(ge=1, le=1)] = 1
    document_id: StableIdentifier
    document_version: DocumentVersion
    document_sha256: Sha256Hex
    renderer: RendererMetadata
    pages: list[PagePreviewArtifact] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_page_order(self) -> Self:
        if self.document_version != f"sha256:{self.document_sha256}":
            raise ValueError("document_version must equal sha256:<document_sha256>")
        if [page.page_index for page in self.pages] != list(range(len(self.pages))):
            raise ValueError("preview pages must be contiguous and zero-based")
        return self


class DocumentRenderResponse(BaseModel):
    """Result of explicit idempotent page rendering."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: StableIdentifier
    document_version: DocumentVersion
    renderer: RendererMetadata
    page_count: int = Field(gt=0)
    pages: list[PagePreviewArtifact]

    @model_validator(mode="after")
    def validate_page_count(self) -> Self:
        if self.page_count != len(self.pages):
            raise ValueError("page_count must match the preview list")
        return self


class PixelBoundingBox(BaseModel):
    """Non-empty integer region in rendered preview pixels."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    x0: int = Field(ge=0)
    y0: int = Field(ge=0)
    x1: int = Field(gt=0)
    y1: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_ordering(self) -> Self:
        if self.x0 >= self.x1 or self.y0 >= self.y1:
            raise ValueError("pixel bounding box must be non-empty and ordered")
        return self


class EvidenceAnchorResponse(BaseModel):
    """Version-scoped mapping from evidence provenance to a rendered preview."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: StableIdentifier
    document_id: StableIdentifier
    document_version: DocumentVersion
    page_index: int = Field(ge=0)
    precision: AnchorPrecision
    preview_asset_id: AssetReference | None = None
    source_bbox: NormalizedBoundingBox | None = None
    display_bbox: NormalizedBoundingBox | None = None
    pixel_bbox: PixelBoundingBox | None = None

    @model_validator(mode="after")
    def validate_precision(self) -> Self:
        boxes = (self.source_bbox, self.display_bbox, self.pixel_bbox)
        if self.precision is AnchorPrecision.REGION:
            if self.preview_asset_id is None or any(value is None for value in boxes):
                raise ValueError("region anchors require a preview and all coordinate forms")
        elif any(value is not None for value in boxes):
            raise ValueError("page and unavailable anchors must not invent a region")
        if self.precision is AnchorPrecision.PAGE and self.preview_asset_id is None:
            raise ValueError("page anchors require a page preview")
        if self.precision is AnchorPrecision.UNAVAILABLE and self.preview_asset_id is not None:
            raise ValueError("unavailable anchors must not claim a page preview")
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
