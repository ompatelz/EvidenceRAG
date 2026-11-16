"""Exercise paired retrieval, generation, support rules, and policy in CI."""

from pathlib import Path

from evidence_rag.eval.claim_comparison import run


def test_paired_claim_support_smoke(tmp_path: Path) -> None:
    report = run(tmp_path, smoke=True)
    summary = report["summaries"]
    assert isinstance(summary, dict)
    assert summary["support_off"]["answered"] == 3
    assert summary["support_on"]["answered"] == 2
    assert summary["support_on"]["correct_answers"] == 1
    assert summary["support_on"]["false_answers_on_unanswerable"] == 1
    rows = report["results"]
    assert isinstance(rows, list)
    table_error = next(row["arms"] for row in rows if row["case"]["id"] == "table-wrong")
    assert table_error["support_on"]["result"]["reason"] == "contradicted_evidence"
    assert table_error["support_off"]["retrieval"] == table_error["support_on"]["retrieval"]
