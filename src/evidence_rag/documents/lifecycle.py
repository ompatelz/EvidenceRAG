"""Explicit synchronous ingestion-state transitions."""

from enum import StrEnum

from evidence_rag.documents.models import IngestionState


class IngestionMode(StrEnum):
    """Caller intent for an existing immutable document version."""

    INGEST = "ingest"
    RETRY = "retry"
    REINDEX = "reindex"


class LifecycleTransitionError(ValueError):
    """An attempted state transition is not part of the Phase 1 machine."""


_ALLOWED_TRANSITIONS: dict[IngestionState, frozenset[IngestionState]] = {
    IngestionState.RECEIVED: frozenset({IngestionState.VALIDATING, IngestionState.PARSING}),
    IngestionState.VALIDATING: frozenset({IngestionState.PARSING, IngestionState.FAILED}),
    IngestionState.PARSING: frozenset(
        {
            IngestionState.PARSED,
            IngestionState.RENDERING,
            IngestionState.PARTIAL,
            IngestionState.FAILED,
        }
    ),
    IngestionState.PARSED: frozenset({IngestionState.RENDERING, IngestionState.VALIDATING}),
    IngestionState.RENDERING: frozenset({IngestionState.PERSISTING, IngestionState.FAILED}),
    IngestionState.PERSISTING: frozenset(
        {IngestionState.READY, IngestionState.PARTIAL, IngestionState.FAILED}
    ),
    IngestionState.READY: frozenset({IngestionState.VALIDATING, IngestionState.FAILED}),
    IngestionState.PARTIAL: frozenset({IngestionState.VALIDATING, IngestionState.RENDERING}),
    IngestionState.FAILED: frozenset({IngestionState.VALIDATING}),
}


def assert_transition(current: IngestionState, target: IngestionState) -> None:
    """Reject implicit or impossible lifecycle movement."""
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise LifecycleTransitionError(f"invalid ingestion transition: {current} -> {target}")
