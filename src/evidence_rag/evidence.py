"""Typed evidence-provenance contract."""

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

StableIdentifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]
Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
VersionLabel = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
]
AssetReference = Annotated[
    str,
    StringConstraints(pattern=r"^asset:[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"),
]


class ElementType(StrEnum):
    """Semantic type of an extracted evidence element."""

    TEXT = "text"
    TABLE = "table"
    FIGURE = "figure"
    EQUATION = "equation"
    CAPTION = "caption"
    OTHER = "other"


class AnchorPrecision(StrEnum):
    """How precisely the evidence can be located in its source."""

    REGION = "region"
    PAGE = "page"
    UNAVAILABLE = "unavailable"


class CoordinateSystem(StrEnum):
    """Supported bounding-box coordinate systems."""

    NORMALIZED_TOP_LEFT = "normalized_top_left"


class NormalizedBoundingBox(BaseModel):
    """A non-empty region in normalized top-left page coordinates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    x0: float = Field(ge=0.0, le=1.0)
    y0: float = Field(ge=0.0, le=1.0)
    x1: float = Field(ge=0.0, le=1.0)
    y1: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_ordering(self) -> Self:
        """Reject empty or inverted regions."""
        if self.x0 >= self.x1:
            raise ValueError("x0 must be less than x1")
        if self.y0 >= self.y1:
            raise ValueError("y0 must be less than y1")
        return self


class RepresentationVersions(BaseModel):
    """Versions required to reproduce the evidence representation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    parser: VersionLabel
    representation: VersionLabel


class EvidenceUnit(BaseModel):
    """One immutable, client-safe unit of source evidence.

    ``page_index`` is zero-based. Region precision is valid only when a normalized
    bounding box and its coordinate system are present. Page and unavailable precision
    must not carry invented coordinates.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: StableIdentifier
    document_id: StableIdentifier
    document_sha256: Sha256Hex
    document_version: VersionLabel
    page_index: int = Field(ge=0, description="Zero-based source page index")
    element_type: ElementType
    section_title: str | None = Field(default=None, max_length=500)
    text: str = Field(min_length=1)
    anchor_precision: AnchorPrecision
    bbox: NormalizedBoundingBox | None = None
    coordinate_system: CoordinateSystem | None = None
    versions: RepresentationVersions
    asset_ref: AssetReference | None = None

    @model_validator(mode="after")
    def validate_anchor_consistency(self) -> Self:
        """Ensure precision claims match the coordinates actually retained."""
        if self.anchor_precision is AnchorPrecision.REGION:
            if self.bbox is None:
                raise ValueError("region precision requires a bounding box")
            if self.coordinate_system is None:
                raise ValueError("region precision requires a coordinate system")
        elif self.bbox is not None or self.coordinate_system is not None:
            raise ValueError("page or unavailable precision must not include region coordinates")
        return self
