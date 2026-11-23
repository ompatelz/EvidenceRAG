"""Bounded recovery guidance and source-context selection; no generated explanations."""

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from evidence_rag.answers import AnswerResult, DraftAnswer
from evidence_rag.evidence import ElementType, EvidenceUnit
from evidence_rag.policy import AnswerPolicy


class ClaimDiagnostic(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    claim_index: int
    text: str
    evidence_ids: tuple[str, ...]
    reason: str
    next_action: str


class CheckExplanation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    result: AnswerResult
    diagnostics: tuple[ClaimDiagnostic, ...]
    max_additional_searches: int = 2
    max_rechecks: int = 1
    notice: str = "Guidance describes observed signals; it does not infer missing source facts."
    content_trust: Literal["untrusted_document_data"] = "untrusted_document_data"


def explain(result: AnswerResult, draft: DraftAnswer) -> CheckExplanation:
    """Preserve decisions and identify each claim's actual assessed signal."""
    diagnostics = []
    for index, claim in enumerate(draft.claims):
        checked = result.claims[index] if index < len(result.claims) else None
        if not claim.citations:
            reason = "missing_citation"
        elif checked is None:
            reason = result.reason
        elif (
            checked.semantic_support is None
            and checked.rule_support == "not_assessed"
            and (result.reason not in ("answered", "verifier_unavailable"))
        ):
            reason = "not_assessed_after_earlier_failure"
        else:
            reason = AnswerPolicy().decide([checked], evidence_available=True)
        action = {
            "answered": "Retain the checked claim and its citations.",
            "verifier_unavailable": "Run doctor; restore the verifier before rechecking.",
            "policy_version_mismatch": "Restore the pinned verifier; do not change thresholds.",
            "contradicted_evidence": "Inspect context; correct or remove the contradicted claim.",
            "conflicting_evidence": "Report conflicting sources; do not pick a winner silently.",
            "invalid_citation": "Select only supplied IDs from the exact document version.",
            "missing_citation": "Cite each material claim and exactly join claim texts.",
        }.get(
            reason, "Inspect neighboring context and search for the missing premise or qualifier."
        )
        diagnostics.append(
            ClaimDiagnostic(
                claim_index=index,
                text=claim.text,
                evidence_ids=tuple(ref.evidence_id for ref in claim.citations),
                reason=reason,
                next_action=action,
            )
        )
    return CheckExplanation(result=result, diagnostics=tuple(diagnostics))


class RecoveryBudget(BaseModel):
    """Caller-owned immutable ledger shared across retrieval and recovery calls."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    searches_used: int = Field(default=0, ge=0, le=2)
    rechecks_used: int = Field(default=0, ge=0, le=1)

    def consume(self, action: Literal["search", "recheck"]) -> "RecoveryBudget":
        if action not in ("search", "recheck"):
            raise ValueError("unknown recovery action")
        field = "searches_used" if action == "search" else "rechecks_used"
        values = self.model_dump()
        values[field] += 1
        return RecoveryBudget.model_validate(values)


def connected_units(
    units: Sequence[EvidenceUnit],
    evidence_id: str,
    radius: int = 1,
) -> tuple[EvidenceUnit, ...]:
    """Seed first, then explicit relationships, heading and reading-order neighbors."""
    if not 0 <= radius <= 2:
        raise ValueError("context radius must be between zero and two")
    ordered = sorted(units, key=lambda u: (u.page_index, u.reading_order or 0, u.evidence_id))
    position = next((i for i, u in enumerate(ordered) if u.evidence_id == evidence_id), None)
    if position is None:
        raise ValueError("evidence not in selected version")
    seed = ordered[position]
    related = [
        u
        for u in ordered
        if (
            (seed.related_element_id is not None and u.parser_element_id == seed.related_element_id)
            or (
                seed.parser_element_id is not None
                and u.related_element_id == seed.parser_element_id
            )
        )
    ]
    heading = next(
        (u for u in reversed(ordered[:position]) if u.element_type is ElementType.HEADING), None
    )
    candidates = [
        seed,
        *related,
        *([heading] if heading else []),
        *ordered[max(0, position - radius) : position],
        *ordered[position + 1 : position + radius + 1],
    ]
    return tuple({u.evidence_id: u for u in candidates}.values())
