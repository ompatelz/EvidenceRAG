"""Process-local recovery sessions with fixed scope, bounded attempts and receipts."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from threading import RLock
from time import monotonic
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from evidence_rag.answers import DraftAnswer
from evidence_rag.assistance import CheckExplanation, RecoveryBudget
from evidence_rag.documents import IntakeError

if TYPE_CHECKING:
    from evidence_rag.sdk import DocumentRef, EvidenceRAG, RetrievalResponse

SESSION_TTL_SECONDS = 1800
MAX_SESSIONS = 64
RECOVERABLE = frozenset(
    {
        "no_relevant_evidence",
        "insufficient_claim_support",
        "missing_citation",
        "invalid_citation",
    }
)


class RecoveryError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class RecoveryEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    operation: Literal["initial_check", "search", "recheck"]
    outcome: str
    evidence_ids: tuple[str, ...] = ()


class RecoverySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    session_id: str
    document_id: str
    document_sha256: str
    question: str
    status: Literal["active", "closed"]
    reason: str
    budget: RecoveryBudget
    observed_evidence_ids: tuple[str, ...]
    initial_check: CheckExplanation
    last_check: CheckExplanation | None
    events: tuple[RecoveryEvent, ...]
    ttl_seconds: int = SESSION_TTL_SECONDS
    content_trust: Literal["untrusted_document_data"] = "untrusted_document_data"


@dataclass
class _Session:
    identifier: str
    document: DocumentRef
    question: str
    expires_at: float
    initial: CheckExplanation
    budget: RecoveryBudget = field(default_factory=RecoveryBudget)
    seen: set[str] = field(default_factory=set)
    events: list[RecoveryEvent] = field(default_factory=list)
    last: CheckExplanation | None = None
    closed: bool = False
    reason: str = "waiting_for_evidence"


class RecoveryManager:
    """One manager per trusted engine process; never serialize sessions as authority.

    Locks make concurrent calls consume the same budget. Failed search execution
    consumes an attempt. Any recheck attempt closes the session, including errors.
    Starting the same normalized question/version again returns the original
    session rather than rerunning its initial check or resetting its budget.
    """

    def __init__(self, engine: EvidenceRAG, *, clock: Callable[[], float] = monotonic) -> None:
        self.engine = engine
        self.clock = clock
        self._sessions: dict[str, _Session] = {}
        self._lock = RLock()

    def _prune(self) -> None:
        expired = [key for key, value in self._sessions.items() if value.expires_at <= self.clock()]
        for key in expired:
            del self._sessions[key]

    def _get(self, identifier: str) -> _Session:
        self._prune()
        if identifier not in self._sessions:
            raise RecoveryError("recovery_session_not_found_or_expired")
        return self._sessions[identifier]

    @staticmethod
    def _snapshot(session: _Session) -> RecoverySnapshot:
        return RecoverySnapshot(
            session_id=session.identifier,
            document_id=session.document.document_id,
            document_sha256=session.document.document_sha256,
            question=session.question,
            status="closed" if session.closed else "active",
            reason=session.reason,
            budget=session.budget,
            observed_evidence_ids=tuple(sorted(session.seen)),
            initial_check=session.initial,
            last_check=session.last,
            events=tuple(session.events),
        )

    def start(
        self,
        document: DocumentRef,
        question: str,
        evidence_ids: Sequence[str],
        draft: DraftAnswer,
    ) -> RecoverySnapshot:
        from evidence_rag.sdk import SearchRequest

        SearchRequest(**document.model_dump(), question=question)
        question = " ".join(question.split())
        if not question:
            raise RecoveryError("invalid_recovery_question")
        with self._lock:
            self._prune()
            for session in self._sessions.values():
                if session.document == document and session.question == question:
                    return self._snapshot(session)
            if len(self._sessions) >= MAX_SESSIONS:
                raise RecoveryError("recovery_capacity_reached")
            checked = self.engine.explain_check(document, question, evidence_ids, draft)
            session = _Session(
                identifier="rec_" + uuid4().hex,
                document=document,
                question=question,
                expires_at=self.clock() + SESSION_TTL_SECONDS,
                initial=checked,
                seen=set(checked.result.supplied_evidence_ids),
            )
            session.events.append(
                RecoveryEvent(
                    operation="initial_check",
                    outcome=checked.result.reason,
                    evidence_ids=checked.result.supplied_evidence_ids,
                )
            )
            if checked.result.reason not in RECOVERABLE:
                session.closed = True
                session.reason = checked.result.reason
            self._sessions[session.identifier] = session
            return self._snapshot(session)

    def status(self, identifier: str) -> RecoverySnapshot:
        with self._lock:
            return self._snapshot(self._get(identifier))

    def search(self, identifier: str, query: str) -> tuple[RecoverySnapshot, RetrievalResponse]:
        from evidence_rag.sdk import SearchRequest

        with self._lock:
            session = self._get(identifier)
            if session.closed:
                raise RecoveryError("recovery_session_closed")
            if session.budget.searches_used >= 2:
                raise RecoveryError("recovery_search_budget_exhausted")
            session.budget = session.budget.consume("search")
            try:
                result = self.engine.search(
                    SearchRequest(**session.document.model_dump(), question=query)
                )
            except Exception as exc:
                code = exc.code if isinstance(exc, IntakeError) else "recovery_search_failed"
                session.events.append(RecoveryEvent(operation="search", outcome=code))
                raise RecoveryError(code) from exc
            ids = tuple(item.evidence_id for item in result.pack.items)
            session.seen.update(ids)
            session.events.append(
                RecoveryEvent(operation="search", outcome=result.status, evidence_ids=ids)
            )
            return self._snapshot(session), result

    def recheck(
        self,
        identifier: str,
        evidence_ids: Sequence[str],
        draft: DraftAnswer,
    ) -> RecoverySnapshot:
        with self._lock:
            session = self._get(identifier)
            if session.closed:
                raise RecoveryError("recovery_session_closed")
            session.budget = session.budget.consume("recheck")
            session.closed = True
            try:
                if any(identifier not in session.seen for identifier in evidence_ids):
                    raise RecoveryError("recovery_evidence_not_observed")
                checked = self.engine.explain_check(
                    session.document, session.question, evidence_ids, draft
                )
            except Exception as exc:
                session.reason = (
                    exc.code if isinstance(exc, RecoveryError) else "recovery_recheck_failed"
                )
                session.events.append(RecoveryEvent(operation="recheck", outcome=session.reason))
                raise RecoveryError(session.reason) from exc
            session.last = checked
            session.reason = checked.result.reason
            session.events.append(
                RecoveryEvent(
                    operation="recheck",
                    outcome=checked.result.reason,
                    evidence_ids=checked.result.supplied_evidence_ids,
                )
            )
            return self._snapshot(session)
