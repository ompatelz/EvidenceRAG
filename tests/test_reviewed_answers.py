import pytest

from evidence_rag.eval.answer_scoring import AnswerJudgment, CitationJudgment, score_answers
from evidence_rag.eval.owner_review import SEED, SNAPSHOT, OwnerDecision, apply_decisions
from evidence_rag.eval.validate import load_evaluation_jsonl


def test_owner_correction_changes_label_and_cannot_move_it() -> None:
    [item] = load_evaluation_jsonl(SEED)[:1]
    correction = OwnerDecision(
        query_id=item.query_id,
        owner_reply="Use the explicit sampling unit",
        reason="Clarify units",
        changes={"gold_answers": ["20 Hz"]},
    )
    [corrected] = apply_decisions([item], [correction])
    assert corrected.gold_answers == ["20 Hz"]
    assert corrected.review_status.value == "verified"
    assert item.review_status.value == "needs_review"
    illegal = correction.model_copy(update={"changes": {"split": "frozen_test"}})
    with pytest.raises(ValueError, match="immutable fields"):
        apply_decisions([item], [illegal])


def test_citation_support_differs_from_correctness_and_page_match() -> None:
    rows = [
        AnswerJudgment(
            query_id="supported-and-unsupported",
            emitted=True,
            answerable=True,
            correct=True,
            claims=[
                [CitationJudgment(supports_claim=True, page_matches=True, region_matches=True)],
                [CitationJudgment(supports_claim=False, page_matches=True, region_matches=False)],
                [],
            ],
            latency_ms=100,
        ),
        AnswerJudgment(
            query_id="withheld",
            emitted=False,
            answerable=True,
            correct=None,
            claims=[],
            latency_ms=200,
        ),
    ]
    result = score_answers(rows)
    assert result.answer_correctness == (1, 1)
    assert result.citation_precision == (1, 2)
    assert result.citation_coverage == (1, 3)
    assert result.page_grounding == (2, 2)
    assert result.region_grounding == (1, 2)
    assert result.unsupported_answer_rate == (1, 1)
    assert result.false_abstention == (1, 2)
    assert result.answer_coverage == (1, 2)
    assert result.latency_p95_ms == 200


def test_approved_scale_and_worked_result_are_applied() -> None:
    items = {item.query_id: item for item in load_evaluation_jsonl(SNAPSHOT)}
    gap = items["p2_table_f1_gap"]
    assert "0\N{EN DASH}1 scale" in gap.question
    assert gap.gold_answers == ["0.11"]
    assert gap.numeric_tolerance is None
    ratio = items["p2_cache_ratio"]
    assert [anchor.evidence_id for anchor in ratio.gold_evidence][-1] == (
        "ev_15cc234bb2d5b403549b3314becf1a4b"
    )
    assert len(ratio.gold_evidence) == 3
    assert gap.review_status.value == ratio.review_status.value == "verified"
