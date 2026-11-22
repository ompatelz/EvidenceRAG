"""Exercise public interfaces on development fixtures without provider requests."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from evidence_rag.answers import DraftAnswer
from evidence_rag.cli import export_skill, main
from evidence_rag.config import AppSettings
from evidence_rag.documents import IngestionState
from evidence_rag.mcp_server import allowed_pdf
from evidence_rag.sdk import DocumentRef, EvidenceRAG, SearchRequest
from evidence_rag.semantic import MODEL_NAME, MODEL_REVISION, SemanticVerifier


class FixedScorer:
    """Test double for the verifier boundary, not an accuracy evaluation."""

    model = MODEL_NAME
    revision = MODEL_REVISION

    def logits(self, premise: str, claim: str) -> tuple[float, float, float]:
        return (0, 4, 0)


@pytest.fixture
def engine(tmp_path: Path) -> EvidenceRAG:
    return EvidenceRAG(tmp_path / "artifacts")


def ingest_atlas(engine: EvidenceRAG) -> DocumentRef:
    ingested = engine.ingest("datasets/fixtures/atlas-narrative.pdf")
    assert ingested.state is IngestionState.READY
    return DocumentRef(document_id=ingested.document_id, document_sha256=ingested.document_sha256)


def draft_for(engine: EvidenceRAG, document: DocumentRef) -> tuple[DraftAnswer, list[str]]:
    result = engine.search(SearchRequest(**document.model_dump(), question="calibration sampling"))
    item = next(item for item in result.pack.items if "20 hertz" in item.text)
    claim = "The Atlas sensor's calibration sampling rate is 20 hertz."
    return DraftAnswer.model_validate(
        {
            "status": "answered",
            "answer": claim,
            "claims": [
                {
                    "text": claim,
                    "citations": [
                        {
                            "evidence_id": item.evidence_id,
                            "document_id": item.document_id,
                            "document_version": item.document_version,
                            "page_index": item.page_index,
                        }
                    ],
                }
            ],
        }
    ), [item.evidence_id]


def test_embedded_search_fetch_duplicate_and_no_provider(engine: EvidenceRAG) -> None:
    document = ingest_atlas(engine)
    second = engine.ingest("datasets/fixtures/atlas-narrative.pdf")
    assert second.duplicate and second.document_sha256 == document.document_sha256
    result = engine.search(SearchRequest(**document.model_dump(), question="calibration sampling"))
    assert result.status == "ok" and result.pack.items
    assert sum(len(item.text) for item in result.pack.items) <= 4000
    for item in result.pack.items:
        assert len(item.text) <= 1200
        fetched = engine.evidence(document, item.evidence_id)
        assert fetched.anchor.evidence_id == item.evidence_id
        assert fetched.anchor.page_index == item.page_index
        assert fetched.content_trust == "untrusted_document_data"
    assert (
        engine.search(
            SearchRequest(
                **document.model_dump(), question="interpret diagram", requires_visual_evidence=True
            )
        ).status
        == "unsupported_modality"
    )


def test_draft_checks_fail_closed_and_share_grounding(engine: EvidenceRAG, tmp_path: Path) -> None:
    document = ingest_atlas(engine)
    draft, ids = draft_for(engine, document)
    result = engine.check_draft(document, "calibration sampling", ids, draft)
    assert result.reason == "verifier_unavailable"
    assert result.claims[0].citation_status == "valid"
    assert result.answer is None
    checked = EvidenceRAG(
        tmp_path / "artifacts", verifier=SemanticVerifier(FixedScorer())
    ).check_draft(document, "calibration sampling", ids, draft)
    assert checked.status == "answered"
    changed = draft.model_dump()
    changed["claims"][0]["citations"][0]["document_version"] = "sha256:" + "0" * 64
    assert (
        engine.check_draft(
            document, "calibration sampling", ids, DraftAnswer.model_validate(changed)
        ).reason
        == "invalid_citation"
    )
    with pytest.raises(ValueError, match="selected document"):
        engine.check_draft(document, "calibration sampling", ["ev_foreign"], draft)
    with pytest.raises(ValueError, match="duplicate"):
        engine.check_draft(document, "calibration sampling", ids * 2, draft)
    with pytest.raises(ValueError, match="selected document"):
        engine.evidence(document, "ev_foreign")


def test_validation_and_no_implicit_external_generation(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        DocumentRef(document_id="../secret", document_sha256="0" * 64)
    engine = EvidenceRAG(
        settings=AppSettings(
            artifact_root=tmp_path / "artifacts", live_answer_provider="openai", demo_answers=True
        )
    )
    document = ingest_atlas(engine)
    draft, ids = draft_for(engine, document)
    assert (
        engine.check_draft(document, "calibration sampling", ids, draft).reason
        == "verifier_unavailable"
    )


def test_cli_json_roundtrip_and_redacted_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = ["--artifact-root", str(tmp_path / "artifacts")]
    assert main([*base, "ingest", "datasets/fixtures/atlas-narrative.pdf"]) == 0
    ingested = json.loads(capsys.readouterr().out)
    args = ["--document-id", ingested["document_id"], "--sha256", ingested["document_sha256"]]
    assert main([*base, "search", *args, "--question", "calibration sampling"]) == 0
    assert json.loads(capsys.readouterr().out)["pack"]["items"]
    assert main([*base, "evidence", *args, "--evidence-id", "ev_missing"]) == 1
    error = capsys.readouterr()
    assert str(tmp_path) not in error.err
    assert json.loads(error.err)["error"] == "invalid_request_or_artifact"


def test_mcp_ingestion_scope(tmp_path: Path) -> None:
    selected = tmp_path / "selected.pdf"
    selected.write_bytes(b"%PDF-not-an-ingestion-test")
    assert allowed_pdf(tmp_path, "selected.pdf") == selected.resolve()
    for path in ("../selected.pdf", str(selected.resolve()), "https://example.org/doc.pdf"):
        with pytest.raises((ValueError, OSError)):
            allowed_pdf(tmp_path, path)
    with pytest.raises(ValueError, match="disabled"):
        allowed_pdf(None, "selected.pdf")


def test_skill_export_has_complete_resources_and_never_overwrites(tmp_path: Path) -> None:
    destination = export_skill(tmp_path / "evidence-rag-agent")
    assert "name: evidence-rag-agent" in (destination / "SKILL.md").read_text()
    assert (destination / "agents/openai.yaml").is_file()
    assert (destination / "references/tools.md").is_file()
    with pytest.raises(FileExistsError):
        export_skill(destination)


def test_catalog_status_page_context_and_empty_abstention(engine: EvidenceRAG) -> None:
    assert engine.documents().documents == ()
    document = ingest_atlas(engine)
    listed = engine.documents(limit=1)
    assert listed.documents[0].document_id == document.document_id
    assert engine.status(document).state is IngestionState.READY
    assert engine.documents(offset=1).documents == ()
    ids: list[str] = []
    offset = 0
    while True:
        page = engine.page_evidence(document, 0, offset=offset, limit=2)
        ids.extend(item.evidence_id for item in page.pack.items)
        assert sum(len(item.text) for item in page.pack.items) <= 4000
        if page.next_offset is None:
            break
        offset = page.next_offset
    assert len(set(ids)) == len(ids) == listed.documents[0].evidence_count
    with pytest.raises(ValueError):
        engine.page_evidence(document, -1)
    with pytest.raises(ValueError):
        engine.documents(limit=101)
    result = engine.check_draft(
        document, "missing fact", [], DraftAnswer(status="insufficient_evidence")
    )
    assert result.reason == "no_relevant_evidence" and result.answer is None


def test_catalog_reports_invalid_metadata(engine: EvidenceRAG) -> None:
    document = ingest_atlas(engine)
    manifest = (
        engine.store.root
        / "documents"
        / document.document_id
        / "versions"
        / document.document_sha256
        / "manifest.json"
    )
    manifest.write_text("broken JSON", encoding="utf-8")
    result = engine.documents()
    assert not result.documents and result.skipped_invalid_records == 1


def test_cli_uses_environment_root_and_bounds_drafts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("EVIDENCERAG_ARTIFACT_ROOT", str(tmp_path / "environment-store"))
    assert main(["ingest", "datasets/fixtures/atlas-narrative.pdf"]) == 0
    ingested = json.loads(capsys.readouterr().out)
    assert main(["documents"]) == 0
    assert (
        json.loads(capsys.readouterr().out)["documents"][0]["document_id"]
        == ingested["document_id"]
    )
    oversized = tmp_path / "draft.json"
    oversized.write_bytes(b" " * 65537)
    assert (
        main(
            [
                "check",
                "--document-id",
                ingested["document_id"],
                "--sha256",
                ingested["document_sha256"],
                "--question",
                "anything",
                "--draft",
                str(oversized),
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().err)["error"] == "invalid_request_or_artifact"


def test_cli_failed_ingestion_exits_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import pymupdf

    encrypted = tmp_path / "locked.pdf"
    with pymupdf.open() as pdf:  # type: ignore[no-untyped-call]
        pdf.new_page()
        pdf.save(
            encrypted,
            encryption=pymupdf.PDF_ENCRYPT_AES_256,  # type: ignore[attr-defined]
            owner_pw="fixture-owner",
            user_pw="fixture-password",
        )
    assert main(["--artifact-root", str(tmp_path / "artifacts"), "ingest", str(encrypted)]) == 1
    assert json.loads(capsys.readouterr().out)["state"] == "failed"


def test_mcp_rejects_symlink_escape(tmp_path: Path) -> None:
    documents = tmp_path / "documents"
    documents.mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF-fixture")
    try:
        (documents / "linked.pdf").symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is unavailable in this Windows environment")
    with pytest.raises(ValueError, match="outside"):
        allowed_pdf(documents, "linked.pdf")
