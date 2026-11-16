"""Versioned selective answering policy."""

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Final, Literal, Protocol

from evidence_rag.grounding import RuleSupport
from evidence_rag.semantic import MODEL_NAME, MODEL_REVISION, PREPROCESSING, SemanticResult

POLICY_VERSION: Final = "grounding-v1"
# Selected on the synthetic policy validation set. See docs/abstention.md.
MIN_SUPPORT_MARGIN = 1.0

PolicyReason = Literal[
    "answered",
    "no_relevant_evidence",
    "insufficient_claim_support",
    "contradicted_evidence",
    "conflicting_evidence",
    "parsing_failed",
    "indexing_failed",
    "unsupported_modality",
    "verifier_unavailable",
    "policy_version_mismatch",
]


class ClaimSignals(Protocol):
    @property
    def rule_support(self) -> RuleSupport: ...

    @property
    def semantic_support(self) -> SemanticResult | None: ...


@dataclass(frozen=True)
class AnswerPolicy:
    min_margin: float = MIN_SUPPORT_MARGIN
    model: str = MODEL_NAME
    revision: str = MODEL_REVISION
    version: Literal["grounding-v1"] = POLICY_VERSION

    def __post_init__(self) -> None:
        if self.version != POLICY_VERSION:
            raise ValueError("unknown policy version")
        if not isfinite(self.min_margin) or self.min_margin < 0:
            raise ValueError("support margin must be finite and nonnegative")

    def decide(
        self,
        claims: Sequence[ClaimSignals],
        *,
        evidence_available: bool,
        requires_visual: bool = False,
        failure: Literal["parsing_failed", "indexing_failed"] | None = None,
    ) -> PolicyReason:
        if failure is not None:
            return failure
        if requires_visual:
            return "unsupported_modality"
        if not evidence_available:
            return "no_relevant_evidence"
        if any(claim.rule_support == "contradicted" for claim in claims):
            return "contradicted_evidence"
        assessed = [
            claim.semantic_support for claim in claims if claim.rule_support == "not_assessed"
        ]
        if any(
            result is not None
            and (result.model, result.revision, result.preprocessing)
            != (self.model, self.revision, PREPROCESSING)
            for result in assessed
        ):
            return "policy_version_mismatch"
        if any(result is not None and result.conflicting for result in assessed):
            return "conflicting_evidence"
        if any(result is not None and result.support == "contradicted" for result in assessed):
            return "contradicted_evidence"
        if any(
            result is None or result.status in ("timeout", "failed", "unavailable", "busy")
            for result in assessed
        ):
            return "verifier_unavailable"
        if not claims or any(claim.rule_support == "insufficient" for claim in claims):
            return "insufficient_claim_support"
        if any(
            result is not None
            and (
                result.status != "assessed"
                or result.support != "supported"
                or result.margin is None
                or result.margin < self.min_margin
            )
            for result in assessed
        ):
            return "insufficient_claim_support"
        return "answered"
