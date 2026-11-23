"""Source extraction, adversarial arithmetic, and public-interface boundaries."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from evidence_rag.answers import DraftAnswer
from evidence_rag.calculations import CalculationError, CalculationRequest, calculate
from evidence_rag.cli import main
from evidence_rag.evidence import EvidenceUnit, TableStructure
from evidence_rag.sdk import DocumentRef, EvidenceRAG


def text_unit(evidence_id: str, text: str, **changes: Any) -> EvidenceUnit:
    return EvidenceUnit.model_validate(
        {
            "evidence_id": evidence_id,
            "document_id": "doc_fixture",
            "document_sha256": "a" * 64,
            "document_version": "sha256:" + "a" * 64,
            "page_index": 0,
            "element_type": "text",
            "text": text,
            "anchor_precision": "page",
            "versions": {"parser": "fixture-1", "representation": "schema-1"},
            **changes,
        }
    )


def request(
    operation: str = "add",
    expected: str | None = None,
    first_unit: str = "days",
    second_unit: str = "days",
) -> CalculationRequest:
    return CalculationRequest.model_validate(
        {
            "operation": operation,
            "expected_value": expected,
            "operands": [
                {"kind": "text", "evidence_id": "ev_first", "unit": first_unit},
                {"kind": "text", "evidence_id": "ev_second", "unit": second_unit},
            ],
        }
    )


def test_decimal_arithmetic_is_exact_and_wrong_expected_value_is_exposed() -> None:
    units = {
        "ev_first": text_unit("ev_first", "The first delay is 0.1 days."),
        "ev_second": text_unit("ev_second", "The second delay is 0.2 days."),
    }
    result = calculate(request(expected="0.3"), units)
    assert result.result == "3/10" and result.matches_expected is True
    assert result.claim_support == "not_assessed"
    assert calculate(request(expected="0.4"), units).matches_expected is False


@pytest.mark.parametrize(
    ("operation", "answer"), [("subtract", "7"), ("multiply", "294"), ("divide", "3/2")]
)
def test_other_operations_do_not_round(operation: str, answer: str) -> None:
    units = {
        "ev_first": text_unit("ev_first", "21 days"),
        "ev_second": text_unit("ev_second", "14 days"),
    }
    assert calculate(request(operation), units).result == answer


@pytest.mark.parametrize(
    "text",
    [
        "14 days or 28 days",
        "ID P-14 days",
        "1e3 days",
        "14 daily",
        "1,000 days",
        "1 000 days",
        "1'000 days",
        "\u221214 days",
        "1/14 days",
        "$14 days",
        "1,000 days or 14 days",
        "1:14 days",
    ],
)
def test_ambiguous_or_nonliteral_quantities_are_rejected(text: str) -> None:
    with pytest.raises(CalculationError, match="ambiguous_or_missing"):
        calculate(
            request(),
            {
                "ev_first": text_unit("ev_first", text),
                "ev_second": text_unit("ev_second", "1 days"),
            },
        )


def test_unit_mismatch_zero_divisor_truncation_and_foreign_source_fail() -> None:
    first = text_unit("ev_first", "21 days")
    second = text_unit("ev_second", "14 hours")
    with pytest.raises(CalculationError, match="unit_mismatch"):
        calculate(request(second_unit="hours"), {"ev_first": first, "ev_second": second})
    with pytest.raises(CalculationError, match="division_by_zero"):
        calculate(
            request("divide"), {"ev_first": first, "ev_second": text_unit("ev_second", "0 days")}
        )

    with pytest.raises(CalculationError, match="source_truncated"):
        calculate(request(), {"ev_first": text_unit("ev_first", "x" * 1201), "ev_second": second})
    with pytest.raises(CalculationError, match="evidence_not_supplied"):
        calculate(request(), {"ev_first": first})
    with pytest.raises(CalculationError, match="version_mismatch"):
        calculate(
            request(),
            {
                "ev_first": first,
                "ev_second": text_unit(
                    "ev_second", "14 days", document_version="sha256:" + "b" * 64
                ),
            },
        )


@pytest.mark.parametrize("text", ["14 ms^-1", "14 ms\u207b\u00b9", "14 ms.s"])
def test_partial_compound_unit_is_not_treated_as_a_simple_unit(text: str) -> None:
    with pytest.raises(CalculationError, match="ambiguous_or_missing"):
        calculate(
            request(first_unit="ms", second_unit="ms"),
            {
                "ev_first": text_unit("ev_first", text),
                "ev_second": text_unit("ev_second", "1 ms"),
            },
        )


def test_request_rejects_code_and_free_numeric_operands() -> None:
    with pytest.raises(ValidationError):
        request("__import__('os')")
    with pytest.raises(ValidationError):
        CalculationRequest.model_validate(
            {
                "operation": "add",
                "operands": [
                    {"kind": "literal", "value": "21"},
                    {"kind": "literal", "value": "14"},
                ],
            }
        )
    with pytest.raises(ValidationError):
        request(expected="NaN")


def test_table_selection_rejects_duplicate_rows() -> None:
    table = TableStructure(
        row_count=3,
        column_count=2,
        headers=["Role", "Period"],
        rows=[["Role", "Period"], ["Resident", "21 days"], ["Resident", "28 days"]],
    )
    unit = text_unit("ev_first", "table", element_type="table", table=table)
    payload = request().model_dump()
    payload["operands"] = [
        {
            "kind": "table_cell",
            "evidence_id": "ev_first",
            "row": "Resident",
            "column": "Period",
        },
        payload["operands"][1],
    ]
    with pytest.raises(CalculationError, match="ambiguous_or_missing"):
        calculate(
            CalculationRequest.model_validate(payload),
            {"ev_first": unit, "ev_second": text_unit("ev_second", "14 days")},
        )


def test_negated_context_is_preserved_and_never_semantically_approved() -> None:
    text = "This account is not eligible for an extra 14 days."
    result = calculate(
        request(),
        {
            "ev_first": text_unit("ev_first", "21 days"),
            "ev_second": text_unit("ev_second", text),
        },
    )
    assert result.result == "35"
    assert result.operands[1].source_text == text
    assert result.claim_support == "not_assessed"
    assert "does not establish" in result.notice


def setup_loan(engine: EvidenceRAG) -> tuple[DocumentRef, CalculationRequest]:
    ingested = engine.ingest("datasets/fixtures/library-loans.pdf")
    doc = DocumentRef(document_id=ingested.document_id, document_sha256=ingested.document_sha256)
    artifact = engine.store.get_evidence(doc.document_id, doc.document_sha256)
    table = next(unit for unit in artifact.units if unit.table is not None)
    renewal = next(unit for unit in artifact.units if unit.text.startswith("A renewal adds"))
    calculation = CalculationRequest.model_validate(
        {
            "operation": "add",
            "expected_value": "35",
            "operands": [
                {
                    "kind": "table_cell",
                    "evidence_id": table.evidence_id,
                    "row": "Resident",
                    "column": "Loan period",
                },
                {"kind": "text", "evidence_id": renewal.evidence_id, "unit": "days"},
            ],
        }
    )
    return doc, calculation


def test_sdk_cross_page_calculation_does_not_bypass_draft_verification(tmp_path: Path) -> None:
    engine = EvidenceRAG(tmp_path / "artifacts")
    doc, calculation = setup_loan(engine)
    receipt = engine.calculate(doc, calculation)
    assert receipt.calculation.result == "35" and receipt.calculation.unit == "days"
    assert receipt.calculation.matches_expected is True
    assert {anchor.page_index for anchor in receipt.anchors} == {0, 1}
    assert all(anchor.preview_asset_id for anchor in receipt.anchors)
    text = "The renewed loan period is 35 days."
    draft = DraftAnswer.model_validate(
        {
            "status": "answered",
            "answer": text,
            "claims": [
                {
                    "text": text,
                    "citations": [
                        {
                            "evidence_id": anchor.evidence_id,
                            "document_id": anchor.document_id,
                            "document_version": anchor.document_version,
                            "page_index": anchor.page_index,
                        }
                        for anchor in receipt.anchors
                    ],
                }
            ],
        }
    )
    assert (
        engine.check_draft(
            doc, "renewed period", [operand.evidence_id for operand in calculation.operands], draft
        ).reason
        == "verifier_unavailable"
    )
    from evidence_rag.documents.storage import ArtifactNotFoundError

    engine.store.preview_path(doc.document_id, doc.document_sha256, 0).unlink()
    with pytest.raises(ArtifactNotFoundError):
        engine.calculate(doc, calculation)


def test_cli_calculation_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "artifacts"
    doc, request_data = setup_loan(EvidenceRAG(root))
    payload = tmp_path / "calculation.json"
    payload.write_text(request_data.model_dump_json(), encoding="utf-8")
    capsys.readouterr()
    assert (
        main(
            [
                "--artifact-root",
                str(root),
                "calculate",
                "--document-id",
                doc.document_id,
                "--sha256",
                doc.document_sha256,
                "--calculation",
                str(payload),
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["calculation"]["matches_expected"] is True
