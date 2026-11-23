"""Local, provider-free application boundary for Python, CLI, and agent tools."""

from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from evidence_rag.answers import (
    AnswerConfig,
    AnswerResult,
    DraftAnswer,
    EvidencePack,
    GroundedAnswerService,
    build_pack,
)
from evidence_rag.assistance import CheckExplanation, connected_units, explain
from evidence_rag.calculations import (
    CalculationError,
    CalculationRequest,
    CalculationResult,
    calculate,
)
from evidence_rag.config import AppSettings
from evidence_rag.doctor import DoctorReport, diagnose
from evidence_rag.documents import (
    DocumentIngestionResponse,
    DocumentIngestionService,
    DocumentIntakeService,
    EvidenceAnchorResponse,
    IngestionMode,
    IngestionState,
    IntakeError,
    LocalArtifactStore,
    PyMuPDFPageRenderer,
    PyMuPDFParser,
)
from evidence_rag.documents.models import (
    DocumentIngestionStatusResponse,
    EvidenceArtifact,
    IngestionManifest,
    PagePreviewManifest,
)
from evidence_rag.documents.service import DocumentRenderingService
from evidence_rag.documents.storage import ArtifactNotFoundError, StorageError
from evidence_rag.evidence import AnchorPrecision, EvidenceUnit
from evidence_rag.policy import AnswerPolicy
from evidence_rag.recipes import CalculationRecipe, RecipeResult, calculate_recipe
from evidence_rag.retrieval.bm25 import BM25Index
from evidence_rag.retrieval.service import RetrievalMode, retrieve
from evidence_rag.semantic import LocalDeberta, SemanticVerifier


class DocumentRef(BaseModel):
    """Explicit document selection; never infer a version from a filename."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    document_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class SearchRequest(DocumentRef):
    question: str = Field(min_length=1, max_length=500)
    mode: RetrievalMode = "bm25"
    requires_visual_evidence: bool = False


class RetrievalResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document: DocumentRef
    mode: RetrievalMode
    status: str
    pack: EvidencePack
    ranking: tuple[dict[str, object], ...]
    timings_ms: dict[str, float]
    truncated_evidence_ids: tuple[str, ...] = ()
    content_trust: Literal["untrusted_document_data"] = "untrusted_document_data"


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    evidence: EvidenceUnit
    anchor: EvidenceAnchorResponse
    text_truncated: bool
    original_text_chars: int
    content_trust: Literal["untrusted_document_data"] = "untrusted_document_data"


class SourceCalculationResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document: DocumentRef
    calculation: CalculationResult
    anchors: tuple[EvidenceAnchorResponse, ...]
    content_trust: Literal["untrusted_document_data"] = "untrusted_document_data"


class SourceRecipeResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document: DocumentRef
    calculation: RecipeResult
    anchors: tuple[EvidenceAnchorResponse, ...]
    content_trust: Literal["untrusted_document_data"] = "untrusted_document_data"


class DocumentList(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    documents: tuple[DocumentIngestionStatusResponse, ...]
    next_offset: int | None
    skipped_invalid_records: int = 0


class PageEvidenceResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document: DocumentRef
    page_index: int
    pack: EvidencePack
    truncated_evidence_ids: tuple[str, ...]
    next_offset: int | None
    content_trust: Literal["untrusted_document_data"] = "untrusted_document_data"


class CollectionSearchRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    documents: tuple[DocumentRef, ...] = Field(min_length=1, max_length=20)
    question: str = Field(min_length=1, max_length=500)
    contextual_indexing: bool = True


class CollectionSearchResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    documents: tuple[DocumentRef, ...]
    pack: EvidencePack
    search_ms: float
    index_reused: bool
    status: str
    conflict_assessment: Literal["not_assessed"] = "not_assessed"
    truncated_evidence_ids: tuple[str, ...] = ()
    content_trust: Literal["untrusted_document_data"] = "untrusted_document_data"


class ScopedDraft(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document: DocumentRef
    evidence_ids: tuple[str, ...] = Field(max_length=5)
    draft: DraftAnswer


class CollectionDraftRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    question: str = Field(min_length=1, max_length=500)
    sources: tuple[ScopedDraft, ...] = Field(min_length=1, max_length=20)


class CollectionCheckResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    documents: tuple[DocumentRef, ...]
    checks: tuple[CheckExplanation, ...]
    conflicting_claim_texts: tuple[str, ...]
    notice: str = (
        "Conflicts are observed support/contradiction signals for identical claim text. "
        "No absence-of-conflict, publication-date or latest-source judgment is implied."
    )
    content_trust: Literal["untrusted_document_data"] = "untrusted_document_data"


class EvidenceRAG:
    """Embed ingestion, retrieval and draft checks without an HTTP server or LLM calls.

    Own one instance per local process. External-generation settings are ignored:
    the caller's agent supplies drafts. Semantic support requires a cached model
    or an explicitly injected verifier; otherwise natural-language drafts abstain.
    """

    def __init__(
        self,
        artifact_root: str | Path | None = None,
        *,
        settings: AppSettings | None = None,
        verifier: SemanticVerifier | None = None,
    ) -> None:
        if artifact_root is not None and settings is not None:
            raise ValueError("supply artifact_root or settings, not both")
        self.settings = settings or (
            AppSettings(artifact_root=Path(artifact_root))
            if artifact_root is not None
            else AppSettings()
        )
        self.store = LocalArtifactStore(
            self.settings.artifact_root,
            max_upload_bytes=self.settings.max_upload_bytes,
            chunk_bytes=self.settings.upload_chunk_bytes,
        )
        parser = PyMuPDFParser(
            max_pages=self.settings.max_pdf_pages,
            max_units=self.settings.max_evidence_units,
            ocr_enabled=self.settings.ocr_enabled,
            tessdata=self.settings.ocr_tessdata,
            ocr_language=self.settings.ocr_language,
        )
        renderer = PyMuPDFPageRenderer(
            dpi=self.settings.render_dpi,
            max_pages=self.settings.max_pdf_pages,
            max_page_pixels=self.settings.max_render_pixels_per_page,
            max_total_pixels=self.settings.max_render_pixels_total,
        )
        self._ingestion = DocumentIngestionService(self.store, parser, renderer)
        self._rendering = DocumentRenderingService(self.store, renderer)
        self._config = AnswerConfig()
        self._collection_cache: tuple[str, BM25Index] | None = None
        if verifier is None and self.settings.semantic_verifier:
            verifier = SemanticVerifier(LocalDeberta(self.settings.model_cache_dir))
        self._answers = GroundedAnswerService(
            self.store, None, config=self._config, verifier=verifier, policy=AnswerPolicy()
        )

    def ingest(self, path: str | Path) -> DocumentIngestionResponse:
        """Ingest a caller-selected local PDF. No directory scan or URL fetch."""
        pdf = Path(path)
        with pdf.open("rb") as stream:
            intake = DocumentIntakeService(self.store).accept(stream, pdf.name)
        return self._ingestion.ingest(
            intake.document_id,
            intake.document_sha256,
            request_id=f"sdk_{uuid4().hex}",
            duplicate=intake.duplicate,
        )

    def retry(self, document: DocumentRef) -> DocumentIngestionResponse:
        """Explicitly retry a failed or interrupted ingestion."""
        return self._ingestion.ingest(
            document.document_id,
            document.document_sha256,
            request_id=f"sdk_{uuid4().hex}",
            mode=IngestionMode.RETRY,
        )

    @property
    def verifier_configured(self) -> bool:
        """Configuration only; a cached model may still fail to load."""
        return self._answers.verifier is not None

    def status(self, document: DocumentRef) -> DocumentIngestionStatusResponse:
        return DocumentIngestionStatusResponse.from_manifest(
            self.store.get_manifest(document.document_id, document.document_sha256)
        )

    def documents(self, *, offset: int = 0, limit: int = 20) -> DocumentList:
        """List only this store's document metadata, never scan source directories."""
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError("invalid catalog pagination")
        rows = []
        skipped = 0
        # Identifiers are derived from path components and checked by the store.
        for path in sorted(self.store.root.glob("documents/doc_*/versions/*/manifest.json")):
            try:
                document = DocumentRef(
                    document_id=path.parent.parent.parent.name,
                    document_sha256=path.parent.name,
                )
                manifest = self.store.get_manifest(document.document_id, document.document_sha256)
            except (ValueError, OSError, ArtifactNotFoundError, StorageError):
                skipped += 1
                continue
            rows.append(DocumentIngestionStatusResponse.from_manifest(manifest))
        return DocumentList(
            documents=tuple(rows[offset : offset + limit]),
            next_offset=offset + limit if len(rows) > offset + limit else None,
            skipped_invalid_records=skipped,
        )

    def _ready(
        self, document: DocumentRef
    ) -> tuple[IngestionManifest, EvidenceArtifact, PagePreviewManifest]:
        manifest = self.store.get_manifest(document.document_id, document.document_sha256)
        if manifest.state is not IngestionState.READY:
            raise IntakeError("document_not_ready", "Document version is not ready.", 409)
        evidence = self.store.get_evidence(document.document_id, document.document_sha256)
        pages = self.store.get_page_manifest(document.document_id, document.document_sha256)
        if (evidence.document_version, pages.document_version) != (
            manifest.document_version,
            manifest.document_version,
        ):
            raise ValueError("document artifact version mismatch")
        return manifest, evidence, pages

    def search(self, request: SearchRequest) -> RetrievalResponse:
        """Return bounded source text and rankings, without generating an answer."""
        document = DocumentRef(
            document_id=request.document_id, document_sha256=request.document_sha256
        )
        manifest, evidence, _ = self._ready(document)
        if request.requires_visual_evidence:
            return RetrievalResponse(
                document=document,
                mode=request.mode,
                status="unsupported_modality",
                pack=EvidencePack(items=(), excluded_ids=()),
                ranking=(),
                timings_ms={},
            )
        lexical = self._cached_index(evidence.units, False)[0] if request.mode == "bm25" else None
        hits, timings, status = retrieve(
            request.question, request.mode, evidence.units, manifest, self.settings, lexical
        )
        units = {unit.evidence_id: unit for unit in evidence.units}
        pack = build_pack(
            hits,
            units,
            document_id=manifest.document_id,
            document_version=manifest.document_version,
            config=self._config,
        )
        return RetrievalResponse(
            document=document,
            mode=request.mode,
            status=status if pack.items else "no_relevant_evidence",
            pack=pack,
            ranking=tuple(asdict(hit) for hit in hits),
            timings_ms=timings,
            truncated_evidence_ids=tuple(
                item.evidence_id for item in pack.items if item.text != units[item.evidence_id].text
            ),
        )

    def page_evidence(
        self, document: DocumentRef, page_index: int, *, offset: int = 0, limit: int = 5
    ) -> PageEvidenceResponse:
        """Read bounded page context, preserving canonical IDs and document scope."""
        manifest, artifact, _ = self._ready(document)
        if not 0 <= page_index < manifest.page_count or offset < 0 or not 1 <= limit <= 5:
            raise ValueError("invalid page or pagination")
        ordered = sorted(
            (unit for unit in artifact.units if unit.page_index == page_index),
            key=lambda unit: (unit.reading_order or 0, unit.evidence_id),
        )
        selected = ordered[offset : offset + limit]
        units = {unit.evidence_id: unit for unit in selected}
        pack = build_pack(
            selected,
            units,
            document_id=manifest.document_id,
            document_version=manifest.document_version,
            config=self._config,
        )
        consumed = len(pack.items)
        return PageEvidenceResponse(
            document=document,
            page_index=page_index,
            pack=pack,
            truncated_evidence_ids=tuple(
                item.evidence_id for item in pack.items if item.text != units[item.evidence_id].text
            ),
            next_offset=offset + consumed
            if consumed and offset + consumed < len(ordered)
            else None,
        )

    def evidence(self, document: DocumentRef, evidence_id: str) -> EvidenceResponse:
        """Fetch a canonical unit and its source anchor in the exact selected version."""
        _, artifact, _ = self._ready(document)
        unit = next((unit for unit in artifact.units if unit.evidence_id == evidence_id), None)
        if unit is None:
            raise ValueError("evidence ID is not in the selected document version")
        truncated = len(unit.text) > 4000
        return EvidenceResponse(
            text_truncated=truncated,
            original_text_chars=len(unit.text),
            evidence=unit.model_copy(update={"text": unit.text[:4000], "table": None})
            if truncated
            else unit,
            anchor=self._rendering.anchor(
                document.document_id, document.document_sha256, evidence_id
            ),
        )

    def check_draft(
        self,
        document: DocumentRef,
        question: str,
        evidence_ids: Sequence[str],
        draft: DraftAnswer,
    ) -> AnswerResult:
        """Check an agent's draft using existing grounding; never call a provider.

        IDs must be in the selected version. The supplied pack is reconstructed
        with the same character budgets as search; excluded/truncated passages
        cannot silently gain support from text the agent was not supplied.
        """
        SearchRequest(**document.model_dump(), question=question)
        if len(evidence_ids) > self._config.max_candidates:
            raise ValueError("supply at most five evidence IDs")
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("duplicate evidence IDs")
        manifest, artifact, pages = self._ready(document)
        units = {unit.evidence_id: unit for unit in artifact.units}
        if any(evidence_id not in units for evidence_id in evidence_ids):
            raise ValueError("evidence ID is not in the selected document version")
        hits = [units[evidence_id] for evidence_id in evidence_ids]
        return self._answers.answer(
            question, manifest, pages, artifact.units, hits, generate=lambda _q, _p: draft
        )

    def calculate(
        self, document: DocumentRef, request: CalculationRequest
    ) -> SourceCalculationResponse:
        """Check source values and exact arithmetic, not a narrative interpretation."""
        _, artifact, _ = self._ready(document)
        units = {unit.evidence_id: unit for unit in artifact.units}
        result = calculate(request, units)
        anchors = []
        for evidence_id in dict.fromkeys(item.evidence_id for item in request.operands):
            anchor = self._rendering.anchor(
                document.document_id, document.document_sha256, evidence_id
            )
            if anchor.precision is AnchorPrecision.UNAVAILABLE:
                raise CalculationError("calculation_source_location_unavailable")
            self.store.preview_path(
                document.document_id, document.document_sha256, anchor.page_index
            )
            anchors.append(anchor)
        return SourceCalculationResponse(
            document=document, calculation=result, anchors=tuple(anchors)
        )

    def doctor(self) -> DoctorReport:
        return diagnose(self.settings)

    def calculate_recipe(
        self,
        document: DocumentRef,
        request: CalculationRecipe,
    ) -> SourceRecipeResponse:
        _, artifact, _ = self._ready(document)
        result = calculate_recipe(request, {u.evidence_id: u for u in artifact.units})
        anchors = []
        for evidence_id in dict.fromkeys(s.selector.evidence_id for s in result.sources):
            source = self.evidence(document, evidence_id)
            if source.anchor.precision is AnchorPrecision.UNAVAILABLE:
                raise CalculationError("calculation_source_location_unavailable")
            self.store.preview_path(
                document.document_id, document.document_sha256, source.anchor.page_index
            )
            anchors.append(source.anchor)
        return SourceRecipeResponse(document=document, calculation=result, anchors=tuple(anchors))

    def explain_check(
        self,
        document: DocumentRef,
        question: str,
        evidence_ids: Sequence[str],
        draft: DraftAnswer,
    ) -> CheckExplanation:
        return explain(self.check_draft(document, question, evidence_ids, draft), draft)

    def check_collection(self, request: CollectionDraftRequest) -> CollectionCheckResponse:
        if len(
            {(s.document.document_id, s.document.document_sha256) for s in request.sources}
        ) != len(request.sources):
            raise ValueError("duplicate collection versions")
        checks = tuple(
            self.explain_check(s.document, request.question, s.evidence_ids, s.draft)
            for s in request.sources
        )
        signals: dict[str, set[str]] = {}
        for checked in checks:
            for diagnostic in checked.diagnostics:
                key = " ".join(diagnostic.text.split())
                signals.setdefault(key, set()).add(diagnostic.reason)
        return CollectionCheckResponse(
            documents=tuple(s.document for s in request.sources),
            checks=checks,
            conflicting_claim_texts=tuple(
                text
                for text, reasons in signals.items()
                if {"answered", "contradicted_evidence"} <= reasons
                or "conflicting_evidence" in reasons
            ),
        )

    def context(
        self,
        document: DocumentRef,
        evidence_id: str,
        *,
        radius: int = 1,
    ) -> PageEvidenceResponse:
        manifest, artifact, _ = self._ready(document)
        selected = connected_units(artifact.units, evidence_id, radius)
        units = {u.evidence_id: u for u in selected}
        pack = build_pack(
            selected,
            units,
            document_id=manifest.document_id,
            document_version=manifest.document_version,
            config=self._config,
        )
        return PageEvidenceResponse(
            document=document,
            page_index=selected[0].page_index,
            pack=pack,
            truncated_evidence_ids=tuple(
                i.evidence_id for i in pack.items if i.text != units[i.evidence_id].text
            ),
            next_offset=None,
        )

    def search_collection(self, request: CollectionSearchRequest) -> CollectionSearchResponse:
        """One shared BM25 ranking over only explicitly selected ready versions.

        A bounded process cache is keyed by the full evidence content and indexing
        option. Source-derived section headings affect indexing only; returned
        excerpts and citations remain canonical. Date and conflict judgments are
        deliberately left to the calling agent inspecting the returned sources.
        """
        from evidence_rag.answers import PackItem

        if len(set((d.document_id, d.document_sha256) for d in request.documents)) != len(
            request.documents
        ):
            raise ValueError("duplicate collection versions")
        units = {}
        for document in request.documents:
            _, artifact, _ = self._ready(document)
            for unit in artifact.units:
                if unit.evidence_id in units:
                    raise ValueError("collection evidence ID collision")
                units[unit.evidence_id] = unit
        index, reused = self._cached_index(tuple(units.values()), request.contextual_indexing)
        ranking = index.search(request.question, k=5)
        items = []
        remaining = self._config.max_pack_chars
        for hit in ranking.hits:
            unit = units[hit.evidence_id]
            text = unit.text[: min(remaining, self._config.max_item_chars)]
            if not text:
                break
            items.append(
                PackItem(
                    evidence_id=unit.evidence_id,
                    document_id=unit.document_id,
                    document_version=unit.document_version,
                    page_index=unit.page_index,
                    text=text,
                )
            )
            remaining -= len(text)
        return CollectionSearchResponse(
            documents=request.documents,
            pack=EvidencePack(
                items=tuple(items),
                excluded_ids=tuple(
                    h.evidence_id
                    for h in ranking.hits
                    if h.evidence_id not in {i.evidence_id for i in items}
                ),
            ),
            search_ms=ranking.search_ms,
            index_reused=reused,
            status="ok" if items else "no_relevant_evidence",
            truncated_evidence_ids=tuple(
                i.evidence_id for i in items if i.text != units[i.evidence_id].text
            ),
        )

    def _cached_index(
        self,
        units: Sequence[EvidenceUnit],
        contextual: bool,
    ) -> tuple[BM25Index, bool]:
        import hashlib

        if len(units) > self.settings.max_evidence_units:
            raise ValueError("collection exceeds configured evidence-unit limit")
        indexed = [
            u.model_copy(
                update={
                    "text": (u.section_title + "\n" + u.text)
                    if contextual and u.section_title
                    else u.text
                }
            )
            for u in units
        ]
        fingerprint = hashlib.sha256(
            "\n".join(u.model_dump_json() for u in indexed).encode()
        ).hexdigest()
        reused = self._collection_cache is not None and self._collection_cache[0] == fingerprint
        if reused:
            assert self._collection_cache is not None
            index = self._collection_cache[1]
        else:
            index = BM25Index()
            index.rebuild(indexed)
            self._collection_cache = (fingerprint, index)
        return index, reused
