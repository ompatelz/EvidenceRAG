"""Deterministic semantic assessments with no model weights."""

import time
from collections.abc import Sequence
from pathlib import Path

import pytest

from evidence_rag.semantic import (
    EvidenceTooLongError,
    LocalDeberta,
    SemanticVerifier,
    VerifierUnavailableError,
)


class FixedScorer:
    model = "fixture"
    revision = "v1"

    def logits(self, premise: str, claim: str) -> Sequence[float]:
        if premise == "supports":
            return (0.0, 4.0, 1.0)
        if premise == "contradicts":
            return (4.0, 0.0, 1.0)
        if premise == "first\n\nsecond":
            return (0.0, 2.0, 1.0)
        if premise == "too long":
            raise EvidenceTooLongError
        if premise == "unavailable":
            raise VerifierUnavailableError("private path")
        if premise == "error":
            raise RuntimeError(f"private content: {claim}")
        if premise == "malformed":
            return (float("nan"), 0.0, 1.0)
        if premise == "slow":
            time.sleep(0.1)
        return (0.0, 1.0, 2.0)


def test_joint_evidence_and_conflict() -> None:
    verifier = SemanticVerifier(FixedScorer())
    joint, conflict = verifier.assess(
        [("claim", ("first", "second"), False), ("claim", ("supports", "contradicts"), False)]
    )
    assert (joint.status, joint.support, joint.margin) == ("assessed", "supported", 1.0)
    assert (conflict.support, conflict.conflicting) == ("contradicted", True)
    assert joint.model == "fixture" and joint.revision == "v1"


@pytest.mark.parametrize(
    ("premise", "truncated", "status"),
    [
        ("supports", True, "truncated"),
        ("too long", False, "truncated"),
        ("malformed", False, "failed"),
        ("error", False, "failed"),
        ("unavailable", False, "unavailable"),
    ],
)
def test_safe_fallback(
    premise: str, truncated: bool, status: str, caplog: pytest.LogCaptureFixture
) -> None:
    (result,) = SemanticVerifier(FixedScorer()).assess([("private claim", (premise,), truncated)])
    assert result.status == status and result.support == "insufficient"
    assert result.margin is None
    assert "private" not in result.model_dump_json()
    assert "private" not in caplog.text


def test_timeout_is_bounded_and_busy_worker_cannot_queue() -> None:
    verifier = SemanticVerifier(FixedScorer(), timeout_ms=1)
    (timeout,) = verifier.assess([("claim", ("slow",), False)])
    (busy,) = verifier.assess([("claim", ("supports",), False)])
    assert timeout.status == "timeout"
    assert busy.status == "busy"


def test_local_model_cache_miss_needs_no_credentials(tmp_path: Path) -> None:
    (result,) = SemanticVerifier(LocalDeberta(tmp_path)).assess([("claim", ("evidence",), False)])
    assert result.status == "unavailable"
