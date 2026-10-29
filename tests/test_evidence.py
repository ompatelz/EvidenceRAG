"""Tests for the evidence provenance contract."""

from typing import Any

import pytest
from pydantic import ValidationError

from evidence_rag.evidence import EvidenceUnit

SHA256 = "a" * 64


def evidence_data(**overrides: object) -> dict[str, Any]:
    data: dict[str, Any] = {
        "evidence_id": "ev_fixture_001",
        "document_id": "doc_fixture",
        "document_sha256": SHA256,
        "document_version": "sha256-a",
        "page_index": 0,
        "element_type": "text",
        "section_title": "Overview",
        "text": "Evidence is retained before an answer is generated.",
        "anchor_precision": "region",
        "bbox": {"x0": 0.1, "y0": 0.2, "x1": 0.9, "y1": 0.4},
        "coordinate_system": "normalized_top_left",
        "versions": {"parser": "fixture-1", "representation": "schema-1"},
        "asset_ref": "asset:page-preview-001",
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize("element_type", ["text", "table"])
def test_valid_region_evidence(element_type: str) -> None:
    evidence = EvidenceUnit.model_validate(evidence_data(element_type=element_type))
    assert evidence.element_type.value == element_type
    assert evidence.page_index == 0


def test_valid_page_level_evidence_has_no_invented_region() -> None:
    evidence = EvidenceUnit.model_validate(
        evidence_data(anchor_precision="page", bbox=None, coordinate_system=None)
    )
    assert evidence.bbox is None
    assert evidence.anchor_precision.value == "page"


def test_page_index_is_zero_based_and_rejects_negative_values() -> None:
    assert EvidenceUnit.model_validate(evidence_data(page_index=0)).page_index == 0
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        EvidenceUnit.model_validate(evidence_data(page_index=-1))


@pytest.mark.parametrize(
    "bbox",
    [
        {"x0": -0.1, "y0": 0.2, "x1": 0.9, "y1": 0.4},
        {"x0": 0.1, "y0": 0.2, "x1": 1.1, "y1": 0.4},
        {"x0": 0.9, "y0": 0.2, "x1": 0.1, "y1": 0.4},
        {"x0": 0.1, "y0": 0.8, "x1": 0.9, "y1": 0.4},
    ],
)
def test_invalid_bounding_boxes_are_rejected(bbox: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        EvidenceUnit.model_validate(evidence_data(bbox=bbox))


def test_region_precision_requires_bbox() -> None:
    with pytest.raises(ValidationError, match="region precision requires a bounding box"):
        EvidenceUnit.model_validate(evidence_data(bbox=None))


def test_page_precision_rejects_invented_bbox() -> None:
    with pytest.raises(ValidationError, match="must not include region coordinates"):
        EvidenceUnit.model_validate(evidence_data(anchor_precision="page"))


def test_missing_document_hash_is_rejected() -> None:
    data = evidence_data()
    del data["document_sha256"]
    with pytest.raises(ValidationError, match="document_sha256"):
        EvidenceUnit.model_validate(data)


def test_raw_filesystem_asset_reference_is_rejected() -> None:
    with pytest.raises(ValidationError, match="asset_ref"):
        EvidenceUnit.model_validate(evidence_data(asset_ref=r"C:\private\page.png"))


def test_serialization_round_trip_is_stable() -> None:
    evidence = EvidenceUnit.model_validate(evidence_data())
    serialized = evidence.model_dump_json()
    restored = EvidenceUnit.model_validate_json(serialized)
    assert restored == evidence
    assert restored.model_dump(mode="json") == evidence.model_dump(mode="json")
