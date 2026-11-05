"""FastAPI application factory and synchronous evidence-preserving ingestion."""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import FastAPI, File, Request, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.body_limit import RequestBodyLimitMiddleware
from starlette.responses import FileResponse, JSONResponse

from evidence_rag import __version__
from evidence_rag.answers import (
    AnswerGenerator,
    AnswerResult,
    FixtureDemoGenerator,
    GroundedAnswerService,
    RankedCandidate,
)
from evidence_rag.config import AppSettings
from evidence_rag.documents import (
    DocumentIngestionResponse,
    DocumentIngestionService,
    DocumentIngestionStatusResponse,
    DocumentIntakeResponse,
    DocumentIntakeService,
    DocumentMetadataResponse,
    DocumentParseResponse,
    DocumentParsingService,
    DocumentRenderingService,
    DocumentRenderResponse,
    DocumentStatusResponse,
    EvidenceAnchorResponse,
    EvidenceArtifact,
    IngestionMode,
    IngestionState,
    IntakeError,
    LocalArtifactStore,
    PagePreviewManifest,
    PyMuPDFPageRenderer,
    PyMuPDFParser,
)
from evidence_rag.documents.storage import ArtifactNotFoundError
from evidence_rag.retrieval.bm25 import BM25Index

CallNext = Callable[[Request], Awaitable[Response]]


class HealthResponse(BaseModel):
    """Stable liveness response."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"] = "ok"
    version: str


class ReadinessResponse(BaseModel):
    """Stable readiness response."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ready", "not_ready"]


class QueryRequest(BaseModel):
    """One local single-user exact-version question."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=500)
    document_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    document_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    mode: Literal["bm25", "dense", "hybrid", "reranked"] = "bm25"


class QueryResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    result: AnswerResult
    retrieval: tuple[dict[str, object], ...]
    mode: Literal["bm25", "dense", "hybrid", "reranked"]
    retrieval_status: str
    timings_ms: dict[str, float]


def create_app(
    settings: AppSettings | None = None, *, answer_generator: AnswerGenerator | None = None
) -> FastAPI:
    """Construct an isolated application using explicit settings."""
    resolved_settings = settings or AppSettings()
    app = FastAPI(
        title=resolved_settings.app_name,
        version=__version__,
        description="Evidence-first document ingestion and local cited-query API",
    )
    app.state.settings = resolved_settings
    artifact_store = LocalArtifactStore(
        resolved_settings.artifact_root,
        max_upload_bytes=resolved_settings.max_upload_bytes,
        chunk_bytes=resolved_settings.upload_chunk_bytes,
    )
    intake_service = DocumentIntakeService(artifact_store)
    parser = PyMuPDFParser(
        max_pages=resolved_settings.max_pdf_pages,
        max_units=resolved_settings.max_evidence_units,
    )
    renderer = PyMuPDFPageRenderer(
        dpi=resolved_settings.render_dpi,
        max_pages=resolved_settings.max_pdf_pages,
        max_page_pixels=resolved_settings.max_render_pixels_per_page,
        max_total_pixels=resolved_settings.max_render_pixels_total,
    )
    parsing_service = DocumentParsingService(artifact_store, parser)
    rendering_service = DocumentRenderingService(artifact_store, renderer)
    ingestion_service = DocumentIngestionService(artifact_store, parser, renderer)
    chosen_generator = answer_generator or (
        FixtureDemoGenerator() if resolved_settings.demo_answers else None
    )
    answer_service = GroundedAnswerService(artifact_store, chosen_generator)
    app.state.intake_service = intake_service
    app.state.parsing_service = parsing_service
    app.state.rendering_service = rendering_service
    app.state.ingestion_service = ingestion_service
    app.state.answer_service = answer_service
    app.add_middleware(
        RequestBodyLimitMiddleware,
        max_body_size=(
            resolved_settings.max_upload_bytes + resolved_settings.multipart_overhead_bytes
        ),
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next: CallNext) -> Response:
        """Assign one generated trace ID without trusting caller input."""
        request.state.request_id = f"req_{uuid4().hex}"
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(IntakeError)
    async def intake_error_handler(_request: Request, exc: IntakeError) -> JSONResponse:
        """Return bounded errors without leaking private storage details."""
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.get("/health", response_model=HealthResponse, tags=["operations"])
    def health() -> HealthResponse:
        """Report process liveness without checking future dependencies."""
        return HealthResponse(version=__version__)

    @app.get("/api/v1/capabilities", tags=["operations"])
    def capabilities() -> dict[str, bool]:
        return {"fixture_demo_answers": resolved_settings.demo_answers}

    ui_root = Path(__file__).parent / "ui"

    @app.get("/inspector", response_class=FileResponse, tags=["inspector"])
    def inspector() -> FileResponse:
        return FileResponse(ui_root / "inspector.html", media_type="text/html")

    @app.get("/inspector/app.css", response_class=FileResponse, tags=["inspector"])
    def inspector_css() -> FileResponse:
        return FileResponse(ui_root / "app.css", media_type="text/css")

    @app.get("/inspector/app.js", response_class=FileResponse, tags=["inspector"])
    def inspector_js() -> FileResponse:
        return FileResponse(ui_root / "app.js", media_type="text/javascript")

    @app.get(
        "/ready",
        response_model=ReadinessResponse,
        tags=["operations"],
        responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
    )
    def ready(response: Response) -> ReadinessResponse:
        """Report whether required local application configuration is usable."""
        if not resolved_settings.ready:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return ReadinessResponse(status="not_ready")
        return ReadinessResponse(status="ready")

    @app.post(
        "/api/v1/documents",
        response_model=DocumentIntakeResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            status.HTTP_200_OK: {"model": DocumentIntakeResponse},
            status.HTTP_400_BAD_REQUEST: {"description": "Invalid or corrupted PDF"},
            status.HTTP_413_CONTENT_TOO_LARGE: {"description": "Upload limit exceeded"},
        },
        tags=["documents"],
    )
    def upload_document(
        response: Response,
        file: Annotated[UploadFile, File(description="PDF document to accept")],
    ) -> DocumentIntakeResponse:
        """Accept one bounded PDF without parsing its page content."""
        try:
            result = intake_service.accept(file.file, file.filename)
        finally:
            file.file.close()
        if result.duplicate:
            response.status_code = status.HTTP_200_OK
        return result

    @app.post(
        "/api/v1/ingestions",
        response_model=DocumentIngestionResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["documents"],
    )
    def ingest_uploaded_document(
        request: Request,
        response: Response,
        file: Annotated[UploadFile, File(description="PDF document to ingest synchronously")],
    ) -> DocumentIngestionResponse:
        """Accept and fully ingest one bounded PDF in the current request."""
        try:
            accepted = intake_service.accept(file.file, file.filename)
        finally:
            file.file.close()
        result = ingestion_service.ingest(
            accepted.document_id,
            accepted.document_sha256,
            request_id=request.state.request_id,
            duplicate=accepted.duplicate,
        )
        if accepted.duplicate:
            response.status_code = status.HTTP_200_OK
        if result.state in {IngestionState.PARTIAL, IngestionState.FAILED}:
            response.status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        return result

    @app.get(
        "/api/v1/documents/{document_id}/versions/{document_sha256}",
        response_model=DocumentMetadataResponse,
        tags=["documents"],
    )
    def document_metadata(document_id: str, document_sha256: str) -> DocumentMetadataResponse:
        """Return safe metadata for one exact accepted byte version."""
        return intake_service.metadata(document_id, document_sha256)

    @app.get(
        "/api/v1/documents/{document_id}/versions/{document_sha256}/status",
        response_model=DocumentStatusResponse,
        tags=["documents"],
    )
    def document_status(document_id: str, document_sha256: str) -> DocumentStatusResponse:
        """Return the truthful lifecycle state for one version."""
        return intake_service.status(document_id, document_sha256)

    @app.get(
        "/api/v1/documents/{document_id}/versions/{document_sha256}/ingestion",
        response_model=DocumentIngestionStatusResponse,
        tags=["documents"],
    )
    def ingestion_status(document_id: str, document_sha256: str) -> DocumentIngestionStatusResponse:
        """Return stage, attempts, timings, counts, and safe failure details."""
        return ingestion_service.status(document_id, document_sha256)

    @app.post(
        "/api/v1/documents/{document_id}/versions/{document_sha256}/ingest",
        response_model=DocumentIngestionResponse,
        tags=["documents"],
    )
    def ingest_existing_version(
        request: Request, document_id: str, document_sha256: str
    ) -> DocumentIngestionResponse:
        """Complete a received version without re-uploading its source bytes."""
        return ingestion_service.ingest(
            document_id,
            document_sha256,
            request_id=request.state.request_id,
        )

    @app.post(
        "/api/v1/documents/{document_id}/versions/{document_sha256}/retry",
        response_model=DocumentIngestionResponse,
        tags=["documents"],
    )
    def retry_ingestion(
        request: Request, document_id: str, document_sha256: str
    ) -> DocumentIngestionResponse:
        """Retry a failed, partial, or interrupted synchronous attempt."""
        return ingestion_service.ingest(
            document_id,
            document_sha256,
            request_id=request.state.request_id,
            mode=IngestionMode.RETRY,
        )

    @app.post(
        "/api/v1/documents/{document_id}/versions/{document_sha256}/reindex",
        response_model=DocumentIngestionResponse,
        tags=["documents"],
    )
    def reindex_document(
        request: Request, document_id: str, document_sha256: str
    ) -> DocumentIngestionResponse:
        """Regenerate derived artifacts for one immutable source version."""
        return ingestion_service.ingest(
            document_id,
            document_sha256,
            request_id=request.state.request_id,
            mode=IngestionMode.REINDEX,
        )

    @app.post(
        "/api/v1/documents/{document_id}/versions/{document_sha256}/parse",
        response_model=DocumentParseResponse,
        tags=["documents"],
    )
    def parse_document(document_id: str, document_sha256: str) -> DocumentParseResponse:
        """Synchronously parse one received version into inspectable evidence."""
        return parsing_service.parse(document_id, document_sha256)

    @app.get(
        "/api/v1/documents/{document_id}/versions/{document_sha256}/evidence",
        response_model=EvidenceArtifact,
        tags=["documents"],
    )
    def document_evidence(document_id: str, document_sha256: str) -> EvidenceArtifact:
        """Return persisted evidence without exposing its private artifact path."""
        return parsing_service.evidence(document_id, document_sha256)

    @app.post(
        "/api/v1/documents/{document_id}/versions/{document_sha256}/render",
        response_model=DocumentRenderResponse,
        tags=["documents"],
    )
    def render_document(document_id: str, document_sha256: str) -> DocumentRenderResponse:
        """Explicitly render bounded, version-scoped PNG page previews."""
        return rendering_service.render(document_id, document_sha256)

    @app.get(
        "/api/v1/documents/{document_id}/versions/{document_sha256}/pages",
        response_model=PagePreviewManifest,
        tags=["documents"],
    )
    def document_pages(document_id: str, document_sha256: str) -> PagePreviewManifest:
        """Return safe preview metadata and opaque page asset identifiers."""
        return rendering_service.pages(document_id, document_sha256)

    @app.get(
        "/api/v1/documents/{document_id}/versions/{document_sha256}/pages/{page_index}/preview",
        response_class=FileResponse,
        tags=["documents"],
    )
    def page_preview(document_id: str, document_sha256: str, page_index: int) -> FileResponse:
        """Return one manifest-backed PNG without exposing its private path."""
        page, path = rendering_service.preview(document_id, document_sha256, page_index)
        return FileResponse(
            path,
            media_type=page.media_type,
            headers={
                "Cache-Control": "private, max-age=31536000, immutable",
                "ETag": f'"sha256:{page.content_sha256}"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.get(
        "/api/v1/documents/{document_id}/versions/{document_sha256}/evidence/{evidence_id}/anchor",
        response_model=EvidenceAnchorResponse,
        tags=["documents"],
    )
    def evidence_anchor(
        document_id: str,
        document_sha256: str,
        evidence_id: str,
    ) -> EvidenceAnchorResponse:
        """Resolve genuine evidence geometry against the rendered page preview."""
        return rendering_service.anchor(document_id, document_sha256, evidence_id)

    @app.post("/api/v1/query", response_model=QueryResponse, tags=["query"])
    def query_document(request: QueryRequest) -> QueryResponse:
        """Search a ready exact version and return a checked answer or abstention."""
        try:
            manifest = artifact_store.get_manifest(request.document_id, request.document_sha256)
        except ArtifactNotFoundError as exc:
            raise IntakeError("document_not_found", "Document version not found.", 404) from exc
        if manifest.state is not IngestionState.READY:
            raise IntakeError("document_not_ready", "Document version is not ready.", 409)
        try:
            evidence = artifact_store.get_evidence(request.document_id, request.document_sha256)
            pages = artifact_store.get_page_manifest(request.document_id, request.document_sha256)
        except ArtifactNotFoundError as exc:
            raise IntakeError(
                "ready_artifacts_missing", "Ready document artifacts are missing.", 409
            ) from exc
        total_started = perf_counter()
        scope = [(manifest.document_id, manifest.document_version)]
        timings: dict[str, float] = {}
        retrieval_status = "ok"
        hits: Sequence[RankedCandidate]
        if request.mode == "bm25":
            started = perf_counter()
            index = BM25Index()
            index.rebuild(evidence.units)
            timings["index_build"] = (perf_counter() - started) * 1000
            ranking = index.search(request.question, k=5, versions=scope)
            hits = ranking.hits
            timings["bm25"] = ranking.search_ms
        else:
            try:
                from huggingface_hub import snapshot_download
                from qdrant_client import QdrantClient

                from evidence_rag.retrieval.dense import (
                    MODEL_REPOSITORY,
                    MODEL_REVISION,
                    DenseIndex,
                    FastEmbedder,
                )
                from evidence_rag.retrieval.hybrid import HybridConfig, HybridRetriever
            except ImportError as exc:
                raise IntakeError(
                    "model_unavailable", "Install the optional local dense dependencies.", 503
                ) from exc
            started = perf_counter()
            try:
                embedding_path = snapshot_download(
                    repo_id=MODEL_REPOSITORY,
                    revision=MODEL_REVISION,
                    cache_dir=str(resolved_settings.model_cache_dir),
                    local_files_only=True,
                    allow_patterns=["*.json", "*.onnx", "vocab.txt"],
                )
            except Exception as exc:
                raise IntakeError(
                    "model_unavailable", "The pinned embedding model is not cached locally.", 503
                ) from exc
            try:
                embedder = FastEmbedder(embedding_path)
            except Exception as exc:
                raise IntakeError(
                    "model_load_failed", "The local embedding model could not load.", 503
                ) from exc
            timings["model_load"] = (perf_counter() - started) * 1000
            client = QdrantClient(":memory:")
            try:
                started = perf_counter()
                dense = DenseIndex(client, embedder)
                dense.rebuild(evidence.units)
                timings["index_build"] = (perf_counter() - started) * 1000
                if request.mode == "dense":
                    result = dense.search(request.question, k=5, versions=scope)
                    hits = result.hits
                    timings["embedding"] = result.embedding_ms
                    timings["vector_search"] = result.vector_search_ms
                else:
                    lexical = BM25Index()
                    lexical.rebuild(evidence.units)
                    hybrid = HybridRetriever(
                        lexical, dense, HybridConfig(rrf_k=60, prefetch=10, final_k=5)
                    ).search(request.question, versions=scope)
                    hits = hybrid.hits
                    timings.update(
                        {
                            "bm25": hybrid.bm25_ms,
                            "embedding": hybrid.embedding_ms,
                            "vector_search": hybrid.vector_search_ms,
                            "fusion": hybrid.fusion_ms,
                        }
                    )
                    if request.mode == "reranked":
                        from evidence_rag.retrieval.rerank import (
                            MODEL_NAME as RERANK_MODEL_NAME,
                        )
                        from evidence_rag.retrieval.rerank import (
                            MODEL_REVISION as RERANK_MODEL_REVISION,
                        )
                        from evidence_rag.retrieval.rerank import (
                            FastEmbedCrossEncoder,
                            OptionalReranker,
                            RerankConfig,
                        )

                        started = perf_counter()
                        try:
                            rerank_path = snapshot_download(
                                repo_id=RERANK_MODEL_NAME,
                                revision=RERANK_MODEL_REVISION,
                                cache_dir=str(resolved_settings.model_cache_dir),
                                local_files_only=True,
                                allow_patterns=[
                                    "config.json",
                                    "tokenizer.json",
                                    "tokenizer_config.json",
                                    "special_tokens_map.json",
                                    "vocab.txt",
                                    "onnx/model.onnx",
                                ],
                            )
                            scorer = FastEmbedCrossEncoder(rerank_path)
                        except Exception as exc:
                            raise IntakeError(
                                "model_unavailable",
                                "The pinned reranker is not cached locally.",
                                503,
                            ) from exc
                        timings["rerank_model_load"] = (perf_counter() - started) * 1000
                        reranker = OptionalReranker(scorer, RerankConfig(enabled=True))
                        try:
                            reranked = reranker.rerank(
                                request.question,
                                hits,
                                {unit.evidence_id: unit for unit in evidence.units},
                                versions=scope,
                            )
                        finally:
                            reranker.close()
                        hits = reranked.hits
                        retrieval_status = reranked.status
                        timings["rerank"] = reranked.rerank_ms
            finally:
                client.close()
        timings["retrieval_total"] = (perf_counter() - total_started) * 1000
        try:
            started = perf_counter()
            answer = answer_service.answer(request.question, manifest, pages, evidence.units, hits)
            timings["answer"] = (perf_counter() - started) * 1000
        except ValueError as exc:
            raise IntakeError(
                "evidence_mismatch", "Document evidence is inconsistent.", 409
            ) from exc
        timings["total"] = (perf_counter() - total_started) * 1000
        return QueryResponse(
            result=answer,
            retrieval=tuple(asdict(hit) for hit in hits),
            mode=request.mode,
            retrieval_status=retrieval_status,
            timings_ms=timings,
        )

    return app
