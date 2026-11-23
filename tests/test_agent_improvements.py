"""Recovery, collection isolation, arithmetic recipes and explicit visual/OCR limits."""

import json
import os
from pathlib import Path
from typing import Any, Literal

import pymupdf
import pytest
from pydantic import ValidationError

from evidence_rag.answers import DraftAnswer
from evidence_rag.assistance import RecoveryBudget, connected_units
from evidence_rag.calculations import CalculationError
from evidence_rag.cli import main
from evidence_rag.config import AppSettings
from evidence_rag.documents.storage import ArtifactNotFoundError
from evidence_rag.eval.agent_trials import AgentTrial, summarize_trials
from evidence_rag.evidence import EvidenceUnit
from evidence_rag.recipes import CalculationRecipe, calculate_recipe
from evidence_rag.sdk import (
    CollectionDraftRequest,
    CollectionSearchRequest,
    DocumentRef,
    EvidenceRAG,
    SearchRequest,
)
from evidence_rag.semantic import MODEL_NAME, MODEL_REVISION, SemanticVerifier
from evidence_rag.visual import VisualObservation, check_observation, page_image


def unit(identifier: str, text: str, **changes: Any) -> EvidenceUnit:
    return EvidenceUnit.model_validate(
        {
            "evidence_id": identifier,
            "document_id": "doc_test",
            "document_sha256": "a" * 64,
            "document_version": "sha256:" + "a" * 64,
            "page_index": 0,
            "element_type": "text",
            "text": text,
            "anchor_precision": "page",
            "versions": {"parser": "fixture", "representation": "fixture"},
            **changes,
        }
    )


def ingest(engine: EvidenceRAG, name: str) -> DocumentRef:
    result = engine.ingest(Path("datasets/fixtures") / name)
    assert result.state == "ready"
    return DocumentRef(document_id=result.document_id, document_sha256=result.document_sha256)


def test_recovery_ledger_rejects_overspending_and_keeps_prior_state() -> None:
    initial = RecoveryBudget()
    used = initial.consume("search").consume("search").consume("recheck")
    assert initial.searches_used == 0 and used.rechecks_used == 1
    with pytest.raises(ValidationError):
        used.consume("search")
    with pytest.raises(ValidationError):
        used.consume("recheck")


def test_connected_context_includes_heading_relationship_and_cross_page_neighbor() -> None:
    units = [
        unit("ev_h", "Policy", element_type="heading", reading_order=0),
        unit("ev_t", "Table", element_type="table", parser_element_id="table", reading_order=1),
        unit("ev_c", "Table 1. Loan periods", related_element_id="table", reading_order=2),
        unit("ev_f", "Except during holidays.", page_index=1, reading_order=0),
    ]
    result = connected_units(units, "ev_c")
    assert result[0].evidence_id == "ev_c"
    assert {u.evidence_id for u in result} == {"ev_h", "ev_t", "ev_c", "ev_f"}
    with pytest.raises(ValueError):
        connected_units(units, "foreign")
    with pytest.raises(ValueError):
        connected_units(units, "ev_c", 3)


def test_collection_scope_canonical_text_and_cached_index(tmp_path: Path) -> None:
    engine = EvidenceRAG(tmp_path / "artifacts")
    first = ingest(engine, "atlas-narrative.pdf")
    second = ingest(engine, "library-loans.pdf")
    request = CollectionSearchRequest(documents=(first, second), question="calibration Resident")
    result = engine.search_collection(request)
    assert result.status == "ok" and result.index_reused is False
    assert engine.search_collection(request).index_reused is True
    assert {i.document_id for i in result.pack.items} == {first.document_id, second.document_id}
    for item in result.pack.items:
        ref = first if item.document_id == first.document_id else second
        assert engine.evidence(ref, item.evidence_id).evidence.text.startswith(item.text)
    restricted = engine.search_collection(request.model_copy(update={"documents": (first,)}))
    assert all(i.document_id == first.document_id for i in restricted.pack.items)
    assert restricted.index_reused is False
    with pytest.raises(ValueError, match="duplicate"):
        engine.search_collection(request.model_copy(update={"documents": (first, first)}))
    with pytest.raises(ArtifactNotFoundError):
        engine.search_collection(
            request.model_copy(
                update={"documents": (first.model_copy(update={"document_sha256": "0" * 64}),)}
            )
        )


def test_explanation_keeps_unavailable_verifier_abstention(tmp_path: Path) -> None:
    engine = EvidenceRAG(tmp_path / "artifacts")
    ref = ingest(engine, "atlas-narrative.pdf")
    found = engine.search(SearchRequest(**ref.model_dump(), question="calibration sampling"))
    item = next(i for i in found.pack.items if "20 hertz" in i.text)
    text = "Calibration sampling is 20 hertz."
    draft = DraftAnswer.model_validate(
        {
            "status": "answered",
            "answer": text,
            "claims": [
                {
                    "text": text,
                    "citations": [
                        {
                            k: getattr(item, k)
                            for k in (
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
    explanation = engine.explain_check(ref, "calibration sampling", [item.evidence_id], draft)
    assert explanation.result.status == "insufficient_evidence"
    assert explanation.diagnostics[0].reason == "verifier_unavailable"
    assert "doctor" in explanation.diagnostics[0].next_action
    context = engine.context(ref, item.evidence_id)
    assert sum(len(i.text) for i in context.pack.items) <= 4000
    assert context.pack.items[0].evidence_id == item.evidence_id


def recipe(operation: str, **options: Any) -> CalculationRecipe:
    return CalculationRecipe.model_validate(
        {
            "steps": [
                {
                    "operation": operation,
                    "inputs": [
                        {"kind": "text", "evidence_id": "ev_a", "unit": "ms"},
                        {"kind": "text", "evidence_id": "ev_b", "unit": "ms"},
                    ],
                    **options,
                }
            ]
        }
    )


@pytest.mark.parametrize(
    ("operation", "expected", "name"),
    [
        ("add", "3000", "ms"),
        ("subtract", "-1000", "ms"),
        ("multiply", "2000000", "ms*ms"),
        ("divide", "1/2", ""),
        ("percentage", "50", "%"),
        ("percent_change", "100", "%"),
    ],
)
def test_recipe_operations(operation: str, expected: str, name: str) -> None:
    result = calculate_recipe(
        recipe(operation),
        {
            "ev_a": unit("ev_a", "1000 ms"),
            "ev_b": unit("ev_b", "2000 ms"),
        },
    )
    assert (result.result, result.unit, result.claim_support) == (expected, name, "not_assessed")


def test_recipe_conversion_steps_controls_and_invalid_inputs() -> None:
    payload = {
        "steps": [
            {
                "operation": "add",
                "inputs": [
                    {"kind": "text", "evidence_id": "ev_a", "unit": "ms"},
                    {"kind": "text", "evidence_id": "ev_b", "unit": "ms"},
                ],
            },
            {"operation": "convert", "inputs": [{"kind": "step", "index": 0}], "target_unit": "s"},
        ],
        "expected_value": "4",
    }
    result = calculate_recipe(
        CalculationRecipe.model_validate(payload),
        {
            "ev_a": unit("ev_a", "1000 ms"),
            "ev_b": unit("ev_b", "2000 ms"),
        },
    )
    assert result.result == "3" and result.matches_expected is False
    assert result.steps[-1].conversion_factor == "1/1000" and len(result.sources) == 2
    with pytest.raises(CalculationError, match="forward_reference"):
        calculate_recipe(
            CalculationRecipe.model_validate(
                {
                    "steps": [
                        {
                            "operation": "convert",
                            "inputs": [{"kind": "step", "index": 0}],
                            "target_unit": "s",
                        }
                    ]
                }
            ),
            {},
        )
    with pytest.raises(CalculationError, match="unit_mismatch"):
        calculate_recipe(
            CalculationRecipe.model_validate(
                {
                    "steps": [
                        {
                            "operation": "convert",
                            "inputs": [{"kind": "text", "evidence_id": "ev_a", "unit": "ms"}],
                            "target_unit": "kg",
                        }
                    ]
                }
            ),
            {"ev_a": unit("ev_a", "1000 ms")},
        )
    with pytest.raises(CalculationError, match="division_by_zero"):
        calculate_recipe(
            recipe("percentage"),
            {
                "ev_a": unit("ev_a", "1000 ms"),
                "ev_b": unit("ev_b", "0 ms"),
            },
        )
    with pytest.raises(CalculationError, match="version_mismatch"):
        calculate_recipe(
            recipe("add"),
            {
                "ev_a": unit("ev_a", "1000 ms"),
                "ev_b": unit("ev_b", "2000 ms", document_version="foreign"),
            },
        )


def test_count_normalization_preserves_categories_without_relabeling() -> None:
    units = {"ev_a": unit("ev_a", "800 hits"), "ev_b": unit("ev_b", "200 misses")}
    steps = [
        {
            "operation": "convert",
            "target_unit": "count",
            "inputs": [{"kind": "text", "evidence_id": "ev_a", "unit": "hits"}],
        },
        {
            "operation": "convert",
            "target_unit": "count",
            "inputs": [{"kind": "text", "evidence_id": "ev_b", "unit": "misses"}],
        },
        {
            "operation": "add",
            "inputs": [{"kind": "step", "index": 0}, {"kind": "step", "index": 1}],
        },
        {
            "operation": "percentage",
            "inputs": [{"kind": "step", "index": 0}, {"kind": "step", "index": 2}],
        },
    ]
    result = calculate_recipe(CalculationRecipe.model_validate({"steps": steps}), units)
    assert result.result == "80" and result.unit == "%"
    assert [source.unit for source in result.sources] == ["hits", "misses"]
    steps[0]["target_unit"] = "misses"
    with pytest.raises(CalculationError, match="relabel_forbidden"):
        calculate_recipe(CalculationRecipe.model_validate({"steps": steps[:1]}), units)


def test_visual_packet_binds_observation_to_actual_ready_page(tmp_path: Path) -> None:
    engine = EvidenceRAG(tmp_path / "artifacts")
    ref = ingest(engine, "atlas-narrative.pdf")
    image = page_image(engine, ref, 0)
    assert image.claim_support == "not_assessed" and image.interpretation == "caller_required"
    observation = VisualObservation(
        document=ref,
        page_index=0,
        image_sha256=image.image_sha256,
        model="test-only",
        observation="Unverified figure observation",
        limitations="May misread axes",
    )
    assert check_observation(engine, observation)["provenance_valid"] is True
    with pytest.raises(ValueError, match="mismatch"):
        check_observation(engine, observation.model_copy(update={"image_sha256": "0" * 64}))
    with pytest.raises(ValueError):
        page_image(engine, ref, 10_000)


def scanned_pdf(path: Path) -> None:
    with pymupdf.open() as digital:  # type: ignore[no-untyped-call]
        page = digital.new_page(width=500, height=200)
        page.insert_text((30, 80), "Calibration interval is 42 days.", fontsize=22)
        png = page.get_pixmap(dpi=144).tobytes("png")
    with pymupdf.open() as scanned:  # type: ignore[no-untyped-call]
        page = scanned.new_page(width=500, height=200)
        page.insert_image(page.rect, stream=png)
        scanned.save(path)


def test_ocr_missing_language_data_is_explicit(tmp_path: Path) -> None:
    pdf = tmp_path / "scan.pdf"
    scanned_pdf(pdf)
    engine = EvidenceRAG(
        settings=AppSettings(
            artifact_root=tmp_path / "artifacts",
            ocr_enabled=True,
            ocr_tessdata=tmp_path / "missing",
        )
    )
    result = engine.ingest(pdf)
    assert result.state == "failed" and result.failure_reason == "ocr_unavailable"


def test_real_ocr_when_language_data_installed(tmp_path: Path) -> None:
    data = os.environ.get("TESSDATA_PREFIX")
    if not data or not (Path(data) / "eng.traineddata").is_file():
        pytest.skip("Local Tesseract language data absent; hosted package job exercises real OCR")
    pdf = tmp_path / "scan.pdf"
    scanned_pdf(pdf)
    engine = EvidenceRAG(
        settings=AppSettings(
            artifact_root=tmp_path / "artifacts", ocr_enabled=True, ocr_tessdata=Path(data)
        )
    )
    result = engine.ingest(pdf)
    assert result.state == "ready"
    ref = DocumentRef(document_id=result.document_id, document_sha256=result.document_sha256)
    found = engine.search(SearchRequest(**ref.model_dump(), question="calibration interval"))
    assert any("42 days" in item.text for item in found.pack.items)
    assert (
        "ocr-eng"
        in engine.store.get_evidence(
            ref.document_id, ref.document_sha256
        ).parser.representation_version
    )


def test_doctor_cli_reports_optional_gaps_without_network(tmp_path: Path, capsys: Any) -> None:
    assert main(["--artifact-root", str(tmp_path / "artifacts"), "doctor"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["ready"] is True and result["network_calls"] == 0
    assert any(
        c["name"] == "semantic_verifier" and c["status"] == "warning" for c in result["checks"]
    )


def test_matched_agent_evaluation_keeps_unknown_costs_and_judgments_unknown() -> None:
    arm_names: tuple[Literal["direct", "tools", "tools_skill"], ...] = (
        "direct",
        "tools",
        "tools_skill",
    )
    rows = [
        AgentTrial(
            question_id="natural-1",
            repeat=0,
            arm=arm,
            model="model",
            revision="pinned",
            configuration_sha256="a" * 64,
            corpus_sha256="b" * 64,
            code_commit="c" * 40,
            skill_sha256="d" * 64 if arm == "tools_skill" else None,
            status="abstained",
            tool_calls=2,
            elapsed_ms=100,
        )
        for arm in arm_names
    ]
    summary = summarize_trials(rows)
    arms = summary["arms"]
    assert isinstance(arms, dict)
    assert arms["tools_skill"]["cost_observations"] == 0
    assert arms["tools_skill"]["observed_cost_usd"] is None
    assert arms["tools_skill"]["observed_tokens"] is None
    assert arms["tools_skill"]["human_answerable_judgments"] == 0
    with pytest.raises(ValueError, match="incomplete"):
        summarize_trials(rows[:-1])
    with pytest.raises(ValueError, match="not matched"):
        summarize_trials([rows[0].model_copy(update={"corpus_sha256": "e" * 64}), *rows[1:]])


def test_sdk_recipe_and_cli_collection_explanation(tmp_path: Path, capsys: Any) -> None:
    engine = EvidenceRAG(tmp_path / "artifacts")
    ref = ingest(engine, "library-loans.pdf")
    result = engine.search(
        SearchRequest(**ref.model_dump(), question="Resident renewal loan period")
    )
    table = next(i for i in result.pack.items if "| Resident |" in i.text)
    renewal = next(i for i in result.pack.items if i.text.startswith("A renewal adds"))
    payload = {
        "steps": [
            {
                "operation": "add",
                "inputs": [
                    {
                        "kind": "table_cell",
                        "evidence_id": table.evidence_id,
                        "row": "Resident",
                        "column": "Loan period",
                    },
                    {"kind": "text", "evidence_id": renewal.evidence_id, "unit": "days"},
                ],
            }
        ]
    }
    receipt = engine.calculate_recipe(ref, CalculationRecipe.model_validate(payload))
    assert receipt.calculation.result == "35" and len(receipt.anchors) == 2
    request_path = tmp_path / "collection.json"
    request_path.write_text(
        CollectionSearchRequest(documents=(ref,), question="Resident").model_dump_json()
    )
    assert (
        main(
            [
                "--artifact-root",
                str(tmp_path / "artifacts"),
                "search-collection",
                "--request",
                str(request_path),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["pack"]["items"]
    recipe_path = tmp_path / "recipe.json"
    recipe_path.write_text(json.dumps(payload))
    assert (
        main(
            [
                "--artifact-root",
                str(tmp_path / "artifacts"),
                "recipe",
                "--document-id",
                ref.document_id,
                "--sha256",
                ref.document_sha256,
                "--calculation",
                str(recipe_path),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["calculation"]["result"] == "35"


def test_scoped_collection_checks_surface_observed_contradictions(tmp_path: Path) -> None:
    class Scorer:
        model = MODEL_NAME
        revision = MODEL_REVISION

        def logits(self, premise: str, claim: str) -> tuple[float, float, float]:
            return (4, 0, 0) if "40 hertz" in premise else (0, 4, 0)

    engine = EvidenceRAG(tmp_path / "artifacts", verifier=SemanticVerifier(Scorer()))
    sources = []
    claim = "Calibration sampling is 20 hertz."
    for value in (20, 40):
        pdf = tmp_path / f"source-{value}.pdf"
        with pymupdf.open() as document:  # type: ignore[no-untyped-call]
            document.new_page().insert_text((30, 80), f"Calibration sampling is {value} hertz.")
            document.save(pdf)
        ingested = engine.ingest(pdf)
        ref = DocumentRef(
            document_id=ingested.document_id, document_sha256=ingested.document_sha256
        )
        item = engine.search(SearchRequest(**ref.model_dump(), question="calibration")).pack.items[
            0
        ]
        citation = {
            key: getattr(item, key)
            for key in ("evidence_id", "document_id", "document_version", "page_index")
        }
        sources.append(
            {
                "document": ref.model_dump(),
                "evidence_ids": [item.evidence_id],
                "draft": {
                    "status": "answered",
                    "answer": claim,
                    "claims": [{"text": claim, "citations": [citation]}],
                },
            }
        )
    checked = engine.check_collection(
        CollectionDraftRequest.model_validate(
            {
                "question": "What calibration sampling rate is documented?",
                "sources": sources,
            }
        )
    )
    assert checked.conflicting_claim_texts == (claim,)
    assert [check.result.reason for check in checked.checks] == [
        "answered",
        "contradicted_evidence",
    ]
