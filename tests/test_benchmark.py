"""Contract, partial-failure, and report tests that require no model download."""

import copy
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from evidence_rag.eval.benchmark import BenchmarkConfig
from evidence_rag.eval.models import EvaluationItem
from evidence_rag.eval.report import render_report, validate_run
from evidence_rag.eval.runner import aggregate_rows, evaluate_queries
from evidence_rag.eval.validate import load_evaluation_jsonl
from evidence_rag.retrieval.bm25 import RankedEvidence

SEED = Path("datasets/eval/phase2_seed.jsonl")
MANIFEST = Path("datasets/manifests/fixtures.json")
E0 = Path("reports/runs/e0-phase2-pilot.json")
E1 = Path("reports/runs/e1-phase2-pilot.json")


def _runs() -> tuple[dict[str, Any], dict[str, Any]]:
    return json.loads(E0.read_text(encoding="utf-8")), json.loads(E1.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "change",
    [
        {"splits": ["development", "frozen_test"]},
        {"cutoffs": [1, 2, 5]},
        {"retriever": "E2"},
        {"unrecognized_option": True},
    ],
)
def test_benchmark_rejects_malformed_or_frozen_config(change: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        BenchmarkConfig.model_validate({"retriever": "E0", "output": "tmp/run.json", **change})


def test_benchmark_rejects_overwriting_e0_with_e1() -> None:
    with pytest.raises(ValidationError, match="overwrite"):
        BenchmarkConfig(retriever="E1", output=E0)


def test_partial_query_failure_is_saved_and_excluded_from_metrics() -> None:
    items = load_evaluation_jsonl(SEED)

    def search(
        item: EvaluationItem, scope: list[tuple[str, str]]
    ) -> tuple[Sequence[RankedEvidence], dict[str, float]]:
        if item.query_id == "p2_atlas_rate":
            raise ConnectionError("private document text must not appear in the saved error")
        return [], {"search_ms": 0.1}

    rows, failures = evaluate_queries(items, search)
    assert len(rows) == 8
    assert failures == [
        {"query_id": "p2_atlas_rate", "stage": "retrieval", "error_type": "ConnectionError"}
    ]
    assert rows[0]["metrics"] is None
    assert "private document text" not in str(rows)
    assert aggregate_rows(rows, "split")["development"]["scored"] == 2


def test_category_aggregation_uses_scored_query_denominator() -> None:
    def metric(hit: float) -> dict[str, dict[str, float]]:
        return {
            str(k): {"hit_rate": hit, "recall": hit, "mrr": hit, "ndcg": hit} for k in (1, 3, 5)
        }

    rows: list[dict[str, Any]] = [
        {"category": "table", "metrics": metric(1.0), "failure": None},
        {"category": "table", "metrics": metric(0.0), "failure": None},
        {"category": "table", "metrics": None, "failure": {"error_type": "TimeoutError"}},
    ]
    group = aggregate_rows(rows, "category")["table"]
    assert (group["queries"], group["scored"], group["failures"]) == (3, 2, 1)
    assert group["metrics"]["3"]["hit_rate"] == 0.5


def test_saved_runs_recompute_and_report_factual_absences() -> None:
    e0, e1 = _runs()
    report = render_report(e0, e1, e0_path=E0, e1_path=E1, seed_path=SEED, manifest_path=MANIFEST)
    assert "Phase 2 gate: NOT PASSED" in report
    assert "E0 wins on first relevant rank: none observed" in report
    assert "E1 wins on first relevant rank: none observed" in report
    assert "Both miss relevant evidence within K=5: none observed" in report
    assert "0 human verified" in report


def test_report_rejects_tampered_metric_and_frozen_row() -> None:
    e0, _ = _runs()
    dataset_hash = e0["dataset_sha256"]
    manifest_hash = e0["manifest_sha256"]
    altered = copy.deepcopy(e0)
    altered["queries"][0]["metrics"]["1"]["hit_rate"] = 0.0
    with pytest.raises(ValueError, match="per-query metric"):
        validate_run(altered, "E0", dataset_hash, manifest_hash)
    altered = copy.deepcopy(e0)
    altered["queries"][0]["split"] = "frozen_test"
    with pytest.raises(ValueError, match="frozen-test leakage"):
        validate_run(altered, "E0", dataset_hash, manifest_hash)


def test_report_rejects_cross_document_hit() -> None:
    e0, _ = _runs()
    altered = copy.deepcopy(e0)
    altered["queries"][0]["ranking"][0]["document_id"] = "unrelated"
    with pytest.raises(ValueError, match="scope"):
        validate_run(altered, "E0", e0["dataset_sha256"], e0["manifest_sha256"])
