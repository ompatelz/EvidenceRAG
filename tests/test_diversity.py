"""Page diversity changes selection only, with version-aware keys and bounded output."""

from pathlib import Path

import pymupdf

from evidence_rag.retrieval.bm25 import RankedEvidence
from evidence_rag.retrieval.diversity import select_candidates
from evidence_rag.sdk import CollectionSearchRequest, DocumentRef, EvidenceRAG


def hit(index: int, page: int, version: str = "version") -> RankedEvidence:
    return RankedEvidence(
        evidence_id=f"ev_{index}",
        document_id="doc_test",
        document_version=version,
        page_index=page,
        rank=index,
        score=1 / index,
        anchor_precision="page",
        bbox=None,
    )


def test_page_spread_preserves_scores_and_fills_when_only_one_page_matches() -> None:
    hits = [hit(i, 0) for i in range(1, 6)] + [hit(6, 1), hit(7, 2)]
    assert select_candidates(hits, diversify_pages=False) == tuple(hits[:5])
    selected = select_candidates(hits, diversify_pages=True)
    assert [h.rank for h in selected] == [1, 2, 6, 7, 3]
    assert select_candidates(hits[:5], diversify_pages=True) == tuple(hits[:5])
    assert selected[2].score == hits[5].score


def test_page_identity_includes_document_version() -> None:
    hits = [hit(i, 0) for i in range(1, 4)] + [hit(4, 0, "other")]
    assert [h.rank for h in select_candidates(hits, diversify_pages=True)] == [1, 2, 4, 3]


def test_actual_collection_reports_pool_selection_and_packing(tmp_path: Path) -> None:
    pdf = tmp_path / "manual.pdf"
    with pymupdf.open() as document:  # type: ignore[no-untyped-call]
        for page_index in range(3):
            page = document.new_page()
            for index in range(7 if page_index == 0 else 1):
                page.insert_text(
                    (30, 60 + 65 * index),
                    f"Retry timeout policy. Manual page {page_index}, rule {index}.",
                )
        document.save(pdf)
    engine = EvidenceRAG(tmp_path / "artifacts")
    result = engine.ingest(pdf)
    ref = DocumentRef(document_id=result.document_id, document_sha256=result.document_sha256)
    request = CollectionSearchRequest(
        documents=(ref,), question="retry timeout policy", candidate_limit=20, diversify_pages=True
    )
    response = engine.search_collection(request)
    assert response.coverage.candidates == 9 and response.coverage.packed == 5
    assert response.coverage.packed_pages == 3 and response.coverage.text_characters <= 4000
    assert len(response.ranking) == 9 and len(response.pack.excluded_ids) == 4
    assert {hit.selected_rank for hit in response.ranking if hit.packed} == {1, 2, 3, 4, 5}
    assert {item.page_index for item in response.pack.items} == {0, 1, 2}
    assert response.candidate_limit == 20 and response.diversify_pages is True
