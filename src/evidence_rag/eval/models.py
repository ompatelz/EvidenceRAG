"""Versioned evaluation-item and document-manifest models."""

from datetime import date
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from evidence_rag.evidence import AnchorPrecision, NormalizedBoundingBox, Sha256Hex

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class EvaluationSplit(StrEnum):
    """Permitted evaluation boundaries."""

    DEVELOPMENT = "development"
    VALIDATION = "validation"
    FROZEN_TEST = "frozen_test"


class ReviewStatus(StrEnum):
    """Human-review state for an evaluation label."""

    VERIFIED = "verified"
    NEEDS_REVIEW = "needs_review"
    UNCERTAIN = "uncertain"


class Difficulty(StrEnum):
    """Coarse human-assigned item difficulty."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class DocumentReference(BaseModel):
    """Reference to one immutable document version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: NonEmptyText
    document_version: NonEmptyText


class GoldEvidenceReference(DocumentReference):
    """Human-verified evidence anchor for an evaluation item."""

    evidence_id: NonEmptyText
    page_index: int = Field(ge=0)
    anchor_precision: AnchorPrecision
    bbox: NormalizedBoundingBox | None = None

    @model_validator(mode="after")
    def validate_anchor(self) -> Self:
        if self.anchor_precision is AnchorPrecision.REGION and self.bbox is None:
            raise ValueError("region evidence requires a bounding box")
        if self.anchor_precision is not AnchorPrecision.REGION and self.bbox is not None:
            raise ValueError("non-region evidence must not include a bounding box")
        return self


class EvaluationItem(BaseModel):
    """Version 1 evaluation item serialized as one JSONL record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Annotated[int, Field(ge=1, le=1)] = 1
    query_id: NonEmptyText
    question: NonEmptyText
    category: NonEmptyText
    documents: Annotated[list[DocumentReference], Field(min_length=1)]
    answerable: bool
    gold_answers: list[NonEmptyText] = Field(default_factory=list)
    numeric_tolerance: float | None = Field(default=None, gt=0)
    gold_evidence: list[GoldEvidenceReference] = Field(default_factory=list)
    requires_visual_evidence: bool
    difficulty: Difficulty
    annotator_notes: NonEmptyText
    ambiguity: NonEmptyText
    review_status: ReviewStatus
    split: EvaluationSplit

    @model_validator(mode="after")
    def validate_answerability(self) -> Self:
        if self.answerable:
            if not self.gold_answers:
                raise ValueError("answerable items require at least one gold answer")
            if not self.gold_evidence:
                raise ValueError("answerable items require gold evidence")
        elif self.gold_answers or self.gold_evidence or self.numeric_tolerance is not None:
            raise ValueError("unanswerable items must not contain contradictory gold fields")
        return self


class DocumentManifestEntry(BaseModel):
    """Provenance and redistribution record for one fixture version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: NonEmptyText
    document_version: NonEmptyText
    source_url: NonEmptyText
    title: NonEmptyText
    license_or_permission: NonEmptyText
    acquisition_date: date
    sha256: Sha256Hex
    redistribution_policy: NonEmptyText
    local_fixture_path: NonEmptyText

    @model_validator(mode="after")
    def validate_content_version(self) -> Self:
        expected = f"sha256:{self.sha256}"
        if self.document_version != expected:
            raise ValueError("document_version must equal sha256:<sha256>")
        return self


class DocumentManifest(BaseModel):
    """Versioned collection of fixture provenance entries."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Annotated[int, Field(ge=1, le=1)] = 1
    documents: Annotated[list[DocumentManifestEntry], Field(min_length=1)]
