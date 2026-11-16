"""Score final answers from explicit source-page judgments."""

from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil
from typing import NamedTuple

from pydantic import BaseModel, Field, model_validator


class CitationJudgment(BaseModel):
    """A reviewer checks support independently of page and region matching."""

    supports_claim: bool
    page_matches: bool | None
    region_matches: bool | None

    @model_validator(mode="after")
    def validate_region(self) -> "CitationJudgment":
        if self.region_matches is True and self.page_matches is not True:
            raise ValueError("a matching region requires a matching page")
        return self


class AnswerJudgment(BaseModel):
    """One final answer with one list of citation judgments per material claim."""

    query_id: str = Field(min_length=1)
    answerable: bool
    emitted: bool
    correct: bool | None
    claims: list[list[CitationJudgment]]
    latency_ms: float = Field(ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_outcome(self) -> "AnswerJudgment":
        if self.emitted:
            if self.correct is None or not self.claims:
                raise ValueError("an emitted answer requires correctness and material claims")
            if self.correct and not self.answerable:
                raise ValueError("a substantive answer to an unanswerable item cannot be correct")
        elif self.correct is not None or self.claims:
            raise ValueError("an abstention has no answer correctness or claims")
        return self


class Count(NamedTuple):
    numerator: int
    denominator: int


@dataclass(frozen=True)
class AnswerMetrics:
    answer_correctness: Count
    citation_precision: Count
    citation_coverage: Count
    page_grounding: Count
    region_grounding: Count
    unsupported_answer_rate: Count
    false_abstention: Count
    answer_coverage: Count
    latency_p50_ms: float | None
    latency_p95_ms: float | None


def score_answers(rows: Sequence[AnswerJudgment]) -> AnswerMetrics:
    """Score a fully judged arm. Empty denominators represent unmeasured rates."""
    if len({row.query_id for row in rows}) != len(rows):
        raise ValueError("duplicate answer judgment")
    emitted = [row for row in rows if row.emitted]
    claims = [claim for row in emitted for claim in row.claims]
    citations = [citation for claim in claims for citation in claim]
    pages = [citation.page_matches for citation in citations if citation.page_matches is not None]
    regions = [
        citation.region_matches for citation in citations if citation.region_matches is not None
    ]
    latencies = sorted(row.latency_ms for row in rows)

    def supported(claim: list[CitationJudgment]) -> bool:
        return any(citation.supports_claim for citation in claim)

    return AnswerMetrics(
        answer_correctness=Count(sum(row.correct is True for row in emitted), len(emitted)),
        citation_precision=Count(sum(c.supports_claim for c in citations), len(citations)),
        citation_coverage=Count(sum(supported(claim) for claim in claims), len(claims)),
        page_grounding=Count(sum(pages), len(pages)),
        region_grounding=Count(sum(regions), len(regions)),
        unsupported_answer_rate=Count(
            sum(not all(supported(claim) for claim in row.claims) for row in emitted),
            len(emitted),
        ),
        false_abstention=Count(
            sum(row.answerable and not row.emitted for row in rows),
            sum(row.answerable for row in rows),
        ),
        answer_coverage=Count(len(emitted), len(rows)),
        latency_p50_ms=latencies[ceil(len(latencies) * 0.50) - 1] if latencies else None,
        latency_p95_ms=latencies[ceil(len(latencies) * 0.95) - 1] if latencies else None,
    )
