"""Regression cases for versioned abstention and calibration."""

from typing import Literal

import pytest

from evidence_rag.eval.policy_validation import Signals, run
from evidence_rag.policy import MIN_SUPPORT_MARGIN, AnswerPolicy
from evidence_rag.semantic import MODEL_NAME, MODEL_REVISION, SemanticResult


@pytest.mark.parametrize(
    ("margin", "expected"),
    [(0.999, "insufficient_claim_support"), (1.0, "answered"), (1.001, "answered")],
)
def test_support_margin_boundary(margin: float, expected: str) -> None:
    signal = Signals(
        rule_support="not_assessed",
        semantic_support=SemanticResult(
            support="supported",
            status="assessed",
            margin=margin,
            model=MODEL_NAME,
            revision=MODEL_REVISION,
        ),
    )
    assert AnswerPolicy(min_margin=1).decide([signal], evidence_available=True) == expected


@pytest.mark.parametrize(
    ("revision", "status", "support", "conflicting", "expected"),
    [
        ("old", "assessed", "supported", False, "policy_version_mismatch"),
        (MODEL_REVISION, "timeout", "insufficient", False, "verifier_unavailable"),
        (MODEL_REVISION, "assessed", "contradicted", True, "conflicting_evidence"),
        (MODEL_REVISION, "assessed", "contradicted", False, "contradicted_evidence"),
        (MODEL_REVISION, "truncated", "insufficient", False, "insufficient_claim_support"),
    ],
)
def test_verifier_disagreement_and_failures(
    revision: str,
    status: Literal["assessed", "timeout", "truncated"],
    support: Literal["supported", "insufficient", "contradicted"],
    conflicting: bool,
    expected: str,
) -> None:
    signal = Signals(
        rule_support="not_assessed",
        semantic_support=SemanticResult(
            support=support,
            status=status,
            margin=3.0,
            conflicting=conflicting,
            model=MODEL_NAME,
            revision=revision,
        ),
    )
    assert AnswerPolicy().decide([signal], evidence_available=True) == expected


def test_validation_selection_matches_shipped_policy() -> None:
    assert run()["selected_margin"] == MIN_SUPPORT_MARGIN
