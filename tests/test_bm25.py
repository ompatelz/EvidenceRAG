"""Deterministic lexical retrieval and evidence-unit metric checks."""

import io
from pathlib import Path
from typing import Any, cast

import pytest

from evidence_rag.documents.models import EvidenceArtifact
from evidence_rag.documents.parser import PyMuPDFParser
from evidence_rag.documents.storage import LocalArtifactStore
from evidence_rag.eval.bm25_run import run
from evidence_rag.eval.metrics import mean_metrics, score_ranking
from evidence_rag.evidence import AnchorPrecision, ElementType, EvidenceUnit, RepresentationVersions
from evidence_rag.retrieval.bm25 import BM25Index, tokenize


def unit(
    identifier: str, text: str, *, document: str = "doc_a", version: str = "a"
) -> EvidenceUnit:
    digest = version * 64
    return EvidenceUnit(
        evidence_id=identifier,
        document_id=document,
        document_sha256=digest,
        document_version=f"sha256:{digest}",
        page_index=0,
        element_type=ElementType.TEXT,
        text=text,
        anchor_precision=AnchorPrecision.PAGE,
        versions=RepresentationVersions(parser="test", representation="test"),
    )


def test_tokenizer_preserves_numbers_identifiers_and_unicode() -> None:
    assert tokenize("QS-17, F1=0.86; CAFÉ vs cafe\u0301") == (
        "qs-17",
        "f1",
        "0.86",
        "café",
        "vs",
        "café",
    )


def test_exact_identifier_number_scope_and_tie_order() -> None:
    index = BM25Index()
    first = unit("ev_a", "Experiment QS-17 has F1 0.86")
    second = unit("ev_b", "Experiment QS-17 has F1 0.86", document="doc_b", version="b")
    third = unit("ev_c", "Experiment QS-18 has F1 0.75")
    index.rebuild([third, second, first])
    assert [hit.evidence_id for hit in index.search("QS-17").hits] == ["ev_a", "ev_b"]
    assert [hit.evidence_id for hit in index.search("0.86").hits] == ["ev_a", "ev_b"]
    scoped = index.search("QS-17", versions=[("doc_b", "sha256:" + "b" * 64)])
    assert [hit.evidence_id for hit in scoped.hits] == ["ev_b"]
    assert all(hit.document_id == "doc_b" for hit in scoped.hits)


def test_empty_queries_rebuild_upsert_and_deletion() -> None:
    index = BM25Index()
    assert index.search("anything").hits == ()
    original = unit("ev_1", "rareterm")
    index.rebuild([original, original])
    identity = index.index_id
    index.rebuild([original])
    assert index.index_id == identity
    index.upsert([original, original])
    assert index.size == 1
    assert index.search(" ").hits == ()
    assert index.search("missing").hits == ()
    assert index.search("rareterm", k=0).hits == ()
    index.delete_version("doc_a", original.document_version)
    assert index.size == 0
    assert index.search("rareterm").hits == ()
    with pytest.raises(ValueError, match="conflicting"):
        index.rebuild([original, unit("ev_1", "different")])


def test_old_version_is_excluded_before_ranking() -> None:
    index = BM25Index()
    old = unit("ev_old", "QS-17 QS-17", version="a")
    current = unit("ev_current", "QS-17", version="b")
    index.rebuild([old, current])
    result = index.search("QS-17", versions=[("doc_a", current.document_version)])
    assert [hit.evidence_id for hit in result.hits] == ["ev_current"]
    index.delete_version("doc_a", old.document_version)
    assert index.size == 1


def test_persisted_canonical_units_rebuild_without_duplicates(tmp_path: Path) -> None:
    source = Path("datasets/fixtures/retrieval-table.pdf")
    store = LocalArtifactStore(tmp_path, max_upload_bytes=65536, chunk_bytes=4096)
    manifest, duplicate = store.ingest(
        io.BytesIO(source.read_bytes()),
        original_filename=source.name,
        sanitized_filename=source.name,
    )
    assert not duplicate
    parser = PyMuPDFParser()
    parsed = parser.parse(source, manifest)
    artifact = EvidenceArtifact(
        document_id=manifest.document_id,
        document_version=manifest.document_version,
        document_sha256=manifest.document_sha256,
        parser=parser.metadata,
        page_count=parsed.page_count,
        units=list(parsed.units),
        issues=list(parsed.issues),
    )
    store.write_evidence(artifact)
    index = BM25Index()
    selected = [(manifest.document_id, manifest.document_version)]
    index.rebuild_from_store(store, selected)
    first_identity = index.index_id
    assert index.size == len(parsed.units)
    assert any(
        hit.evidence_id == next(u.evidence_id for u in parsed.units if u.table)
        for hit in index.search("0.86", versions=selected).hits
    )
    index.rebuild_from_store(store, selected)
    assert index.size == len(parsed.units)
    assert index.index_id == first_identity


def test_metrics_have_hand_calculable_values() -> None:
    score = score_ranking(["wrong", "gold-a", "gold-b"], {"gold-a", "gold-b"}, k=2)
    assert score.hit_rate == 1
    assert score.recall == 0.5
    assert score.mrr == 0.5
    assert score.ndcg == pytest.approx((1 / 1.584962500721156) / (1 + 1 / 1.584962500721156))
    missed = score_ranking(["wrong"], {"gold-a"}, k=1)
    assert mean_metrics([score, missed]).hit_rate == 0.5
    with pytest.raises(ValueError, match="duplicate"):
        score_ranking(["gold-a", "gold-a"], {"gold-a"}, k=2)


def test_e0_runner_saves_development_and_validation_only(tmp_path: Path) -> None:
    output = tmp_path / "e0.json"
    result = run(
        Path("datasets/manifests/fixtures.json"),
        Path("datasets/eval/phase2_seed.jsonl"),
        output,
    )
    assert output.is_file()
    assert result["counts"] == {"queries": 8, "scored": 6, "index_units": 11}
    rows = cast(list[dict[str, Any]], result["queries"])
    assert {row["split"] for row in rows} == {"development", "validation"}
    assert all(row["split"] != "frozen_test" for row in rows)
    assert all(row["ranking"] is not None for row in rows)
