"""Tests for evaluation and manifest validation."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from evidence_rag.eval.models import DocumentManifest, EvaluationItem
from evidence_rag.eval.validate import (
    DatasetValidationError,
    load_evaluation_jsonl,
    validate_dataset,
)

HASH = "b" * 64
VERSION = f"sha256:{HASH}"


def item_data(**overrides: object) -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema_version": 1,
        "query_id": "q1",
        "question": "What is the fixture answer?",
        "category": "narrative_fact",
        "documents": [{"document_id": "doc1", "document_version": VERSION}],
        "answerable": True,
        "gold_answers": ["answer"],
        "numeric_tolerance": None,
        "gold_evidence": [
            {
                "document_id": "doc1",
                "document_version": VERSION,
                "evidence_id": "ev1",
                "page_index": 0,
                "anchor_precision": "page",
                "bbox": None,
            }
        ],
        "requires_visual_evidence": False,
        "difficulty": "easy",
        "annotator_notes": "Human verified.",
        "ambiguity": "None.",
        "review_status": "verified",
        "split": "development",
    }
    data.update(overrides)
    return data


def test_duplicate_query_ids_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "items.jsonl"
    line = json.dumps(item_data())
    path.write_text(f"{line}\n{line}\n", encoding="utf-8")
    with pytest.raises(DatasetValidationError, match="duplicate query_id"):
        load_evaluation_jsonl(path)


def test_malformed_jsonl_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "items.jsonl"
    path.write_text("{not-json}\n", encoding="utf-8")
    with pytest.raises(DatasetValidationError, match="invalid JSONL item"):
        load_evaluation_jsonl(path)


def test_missing_manifest_provenance_and_hash_are_rejected() -> None:
    entry = {
        "document_id": "doc1",
        "document_version": VERSION,
        "title": "Fixture",
        "license_or_permission": "Owned",
        "acquisition_date": "2026-10-29",
        "redistribution_policy": "Allowed",
        "local_fixture_path": "datasets/fixtures/a.pdf",
    }
    with pytest.raises(ValidationError) as error:
        DocumentManifest.model_validate({"schema_version": 1, "documents": [entry]})
    assert {item["loc"][-1] for item in error.value.errors()} == {"source_url", "sha256"}


def test_manifest_version_must_match_content_hash() -> None:
    entry = {
        "document_id": "doc1",
        "document_version": "sha256:" + "a" * 64,
        "source_url": "repo://fixture.pdf",
        "title": "Fixture",
        "license_or_permission": "Owned",
        "acquisition_date": "2026-10-29",
        "sha256": HASH,
        "redistribution_policy": "Allowed",
        "local_fixture_path": "datasets/fixtures/a.pdf",
    }
    with pytest.raises(ValidationError, match="must equal sha256"):
        DocumentManifest.model_validate({"schema_version": 1, "documents": [entry]})


@pytest.mark.parametrize("split", ["train", "test", "production"])
def test_invalid_splits_are_rejected(split: str) -> None:
    with pytest.raises(ValidationError, match="split"):
        EvaluationItem.model_validate(item_data(split=split))


def test_answerable_item_requires_answer_and_evidence() -> None:
    with pytest.raises(ValidationError, match="gold answer"):
        EvaluationItem.model_validate(item_data(gold_answers=[]))
    with pytest.raises(ValidationError, match="gold evidence"):
        EvaluationItem.model_validate(item_data(gold_evidence=[]))


def test_unanswerable_item_rejects_contradictory_gold_fields() -> None:
    with pytest.raises(ValidationError, match="contradictory gold fields"):
        EvaluationItem.model_validate(item_data(answerable=False))


def test_invalid_page_region_and_numeric_tolerance_are_rejected() -> None:
    invalid_anchor = item_data()
    invalid_anchor["gold_evidence"][0]["page_index"] = -1
    with pytest.raises(ValidationError, match="page_index"):
        EvaluationItem.model_validate(invalid_anchor)
    with pytest.raises(ValidationError, match="numeric_tolerance"):
        EvaluationItem.model_validate(item_data(numeric_tolerance=0))


def write_dataset(tmp_path: Path, items: list[dict[str, Any]]) -> tuple[Path, Path]:
    datasets = tmp_path / "datasets"
    fixture_dir = datasets / "fixtures"
    manifest_dir = datasets / "manifests"
    eval_dir = datasets / "eval"
    fixture_dir.mkdir(parents=True)
    manifest_dir.mkdir()
    eval_dir.mkdir()
    fixture = fixture_dir / "fixture.pdf"
    fixture.write_bytes(b"fixture")
    digest = hashlib.sha256(b"fixture").hexdigest()
    actual_version = f"sha256:{digest}"
    manifest = {
        "schema_version": 1,
        "documents": [
            {
                "document_id": "doc1",
                "document_version": actual_version,
                "source_url": "repo://fixture.pdf",
                "title": "Fixture",
                "license_or_permission": "Owned",
                "acquisition_date": "2026-10-29",
                "sha256": digest,
                "redistribution_policy": "Allowed",
                "local_fixture_path": "datasets/fixtures/fixture.pdf",
            }
        ],
    }
    manifest_path = manifest_dir / "fixtures.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    eval_path = eval_dir / "items.jsonl"
    normalized_items = json.loads(json.dumps(items))
    for item in normalized_items:
        for reference in [*item["documents"], *item["gold_evidence"]]:
            if reference["document_version"] == VERSION:
                reference["document_version"] = actual_version
    eval_path.write_text("\n".join(json.dumps(item) for item in normalized_items), encoding="utf-8")
    return manifest_path, eval_path


def test_unknown_document_versions_are_rejected(tmp_path: Path) -> None:
    item = item_data(documents=[{"document_id": "missing", "document_version": VERSION}])
    item["gold_evidence"] = []
    item["answerable"] = False
    item["gold_answers"] = []
    manifest, evaluation = write_dataset(tmp_path, [item])
    with pytest.raises(DatasetValidationError, match="unknown document version"):
        validate_dataset(manifest, [evaluation])


def test_document_split_conflicts_are_rejected(tmp_path: Path) -> None:
    second = item_data(query_id="q2", split="validation")
    manifest, evaluation = write_dataset(tmp_path, [item_data(), second])
    with pytest.raises(DatasetValidationError, match="document split conflict"):
        validate_dataset(manifest, [evaluation])
