"""Typed evidence-provenance contract."""

from enum import StrEnum
from typing import Annotated, Literal, Self

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
    HEADING = "heading"
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


class SourceCoordinateSystem(StrEnum):
    """Parser-native coordinate systems retained for reproducibility."""

    PYMUPDF_POINTS_TOP_LEFT_UNROTATED = "pymupdf_points_top_left_unrotated"


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


class SourceBoundingBox(BaseModel):
    """A non-empty parser-native source region."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    x0: float = Field(ge=0.0)
    y0: float = Field(ge=0.0)
    x1: float = Field(gt=0.0)
    y1: float = Field(gt=0.0)

    @model_validator(mode="after")
    def validate_ordering(self) -> Self:
        if self.x0 >= self.x1:
            raise ValueError("x0 must be less than x1")
        if self.y0 >= self.y1:
            raise ValueError("y0 must be less than y1")
        return self


class SourceRegion(BaseModel):
    """Coordinates and page geometry exactly as interpreted by the parser."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bbox: SourceBoundingBox
    coordinate_system: SourceCoordinateSystem
    page_width: float = Field(gt=0.0)
    page_height: float = Field(gt=0.0)
    page_rotation: Literal[0, 90, 180, 270]

    @model_validator(mode="after")
    def validate_page_bounds(self) -> Self:
        if self.bbox.x1 > self.page_width or self.bbox.y1 > self.page_height:
            raise ValueError("source bounding box must stay within the unrotated page")
        return self


class TableStructure(BaseModel):
    """Page-local table rows and headers without semantic interpretation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    row_count: int = Field(gt=0)
    column_count: int = Field(gt=0)
    headers: list[str | None]
    rows: list[list[str | None]]
    caption: str | None = None
    header_external: bool = False

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        if len(self.headers) != self.column_count:
            raise ValueError("table headers must match column_count")
        if len(self.rows) != self.row_count:
            raise ValueError("table rows must match row_count")
        if any(len(row) != self.column_count for row in self.rows):
            raise ValueError("every table row must match column_count")
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
    source_region: SourceRegion | None = None
    parser_element_id: StableIdentifier | None = None
    reading_order: int | None = Field(default=None, ge=0)
    related_element_id: StableIdentifier | None = None
    table: TableStructure | None = None
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
        if self.table is not None and self.element_type is not ElementType.TABLE:
            raise ValueError("table structure requires table element type")
        return self
