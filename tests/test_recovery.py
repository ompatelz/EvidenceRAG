"""Recovery state transitions, actual SDK checks, scope isolation and failed attempts."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from evidence_rag.answers import DraftAnswer
from evidence_rag.recovery import SESSION_TTL_SECONDS, RecoveryError, RecoveryManager
from evidence_rag.sdk import DocumentRef, EvidenceRAG, SearchRequest


def ready_engine(tmp_path: Path) -> tuple[EvidenceRAG, DocumentRef]:
    engine = EvidenceRAG(tmp_path / "artifacts")
    result = engine.ingest("datasets/fixtures/atlas-narrative.pdf")
    return engine, DocumentRef(
        document_id=result.document_id, document_sha256=result.document_sha256
    )


def empty() -> DraftAnswer:
    return DraftAnswer(status="insufficient_evidence")


def checked_draft(item: Any) -> DraftAnswer:
    text = "Calibration sampling is 20 hertz."
    return DraftAnswer.model_validate(
        {
            "status": "answered",
            "answer": text,
            "claims": [
                {
                    "text": text,
                    "citations": [
                        {
                            key: getattr(item, key)
                            for key in (
                                "evidence_id",
                                "document_id",
                                "document_version",
                                "page_index",
                            )
                        }
                    ],
                }
            ],
        }
    )


def test_recovery_fixes_scope_and_closes_after_one_withheld_recheck(tmp_path: Path) -> None:
    engine, document = ready_engine(tmp_path)
    question = "What is the calibration sampling rate?"
    initial = engine.recovery.start(document, question, [], empty())
    assert initial.status == "active" and initial.budget.searches_used == 0
    searched, result = engine.recovery.search(initial.session_id, "calibration sampling")
    item = next(i for i in result.pack.items if "20 hertz" in i.text)
    final = engine.recovery.recheck(initial.session_id, [item.evidence_id], checked_draft(item))
    assert final.question == question and final.document_sha256 == document.document_sha256
    assert searched.budget.searches_used == 1 and final.budget.rechecks_used == 1
    assert final.status == "closed" and final.reason == "verifier_unavailable"
    assert final.last_check is not None and final.last_check.result.answer is None
    assert [event.operation for event in final.events] == ["initial_check", "search", "recheck"]
    with pytest.raises(RecoveryError, match="session_closed"):
        engine.recovery.recheck(initial.session_id, [item.evidence_id], checked_draft(item))
    with pytest.raises(RecoveryError, match="session_closed"):
        engine.recovery.search(initial.session_id, "other wording")


def test_restarting_question_does_not_reset_counters_or_run_another_check(tmp_path: Path) -> None:
    engine, document = ready_engine(tmp_path)
    initial = engine.recovery.start(document, "calibration sampling", [], empty())
    engine.recovery.search(initial.session_id, "calibration")
    again = engine.recovery.start(document, " calibration   sampling ", [], empty())
    assert again.session_id == initial.session_id and again.budget.searches_used == 1
    assert len(again.events) == 2


def test_search_execution_errors_consume_budget_and_have_redacted_receipts(tmp_path: Path) -> None:
    engine, document = ready_engine(tmp_path)
    initial = engine.recovery.start(document, "calibration", [], empty())
    for _ in range(2):
        with pytest.raises(RecoveryError, match="search_failed"):
            engine.recovery.search(initial.session_id, "private-query-" * 100)
    state = engine.recovery.status(initial.session_id)
    assert state.budget.searches_used == 2
    assert [e.outcome for e in state.events[1:]] == ["recovery_search_failed"] * 2
    assert "private-query" not in state.model_dump_json()
    with pytest.raises(RecoveryError, match="budget_exhausted"):
        engine.recovery.search(initial.session_id, "calibration")
    assert engine.recovery.status(initial.session_id).budget.searches_used == 2


def test_unobserved_ids_close_recheck_without_gaining_support(tmp_path: Path) -> None:
    engine, document = ready_engine(tmp_path)
    item = engine.search(SearchRequest(**document.model_dump(), question="calibration")).pack.items[
        0
    ]
    initial = engine.recovery.start(document, "calibration", [], empty())
    with pytest.raises(RecoveryError, match="not_observed"):
        engine.recovery.recheck(initial.session_id, [item.evidence_id], checked_draft(item))
    closed = engine.recovery.status(initial.session_id)
    assert closed.status == "closed" and closed.budget.rechecks_used == 1
    assert closed.last_check is None


def test_terminal_initial_verifier_failure_does_not_start_search_loop(tmp_path: Path) -> None:
    engine, document = ready_engine(tmp_path)
    item = engine.search(
        SearchRequest(**document.model_dump(), question="calibration sampling")
    ).pack.items[0]
    state = engine.recovery.start(document, "calibration", [item.evidence_id], checked_draft(item))
    assert state.status == "closed" and state.reason == "verifier_unavailable"
    assert state.budget.searches_used == 0 and state.budget.rechecks_used == 0


def test_capacity_expiry_and_process_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, document = ready_engine(tmp_path)
    now = [10.0]
    manager = RecoveryManager(engine, clock=lambda: now[0])
    monkeypatch.setattr("evidence_rag.recovery.MAX_SESSIONS", 1)
    first = manager.start(document, "first question", [], empty())
    with pytest.raises(RecoveryError, match="capacity_reached"):
        manager.start(document, "second question", [], empty())
    with pytest.raises(RecoveryError, match="not_found_or_expired"):
        RecoveryManager(engine).status(first.session_id)
    now[0] += SESSION_TTL_SECONDS
    with pytest.raises(RecoveryError, match="not_found_or_expired"):
        manager.status(first.session_id)
    second = manager.start(document, "first question", [], empty())
    assert second.session_id != first.session_id


def test_concurrent_searches_cannot_overspend(tmp_path: Path) -> None:
    engine, document = ready_engine(tmp_path)
    initial = engine.recovery.start(document, "calibration", [], empty())

    def attempt(_: int) -> str:
        try:
            engine.recovery.search(initial.session_id, "calibration")
            return "searched"
        except RecoveryError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(attempt, range(3)))
    assert results.count("searched") == 2
    assert results.count("recovery_search_budget_exhausted") == 1
    assert engine.recovery.status(initial.session_id).budget.searches_used == 2
