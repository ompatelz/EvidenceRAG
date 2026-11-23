"""FastAPI application factory and synchronous evidence-preserving ingestion."""

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from functools import partial
from pathlib import Path
from tempfile import TemporaryFile
from threading import Event
from time import perf_counter
from typing import Annotated, Literal
from uuid import uuid4

from anyio import create_task_group
from fastapi import FastAPI, File, Request, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool
from starlette.middleware.body_limit import RequestBodyLimitMiddleware
from starlette.responses import FileResponse, JSONResponse

from evidence_rag import __version__
from evidence_rag.answers import (
    AnswerConfig,
    AnswerGenerator,
    AnswerResult,
    FixtureDemoGenerator,
    GroundedAnswerService,
    Reason,
)
from evidence_rag.codex_answers import CODEX_TIMEOUT_SECONDS, CodexAnswerGenerator
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
from evidence_rag.documents.models import IngestionStage
from evidence_rag.documents.storage import ArtifactNotFoundError, StorageError
from evidence_rag.openai_answers import TIMEOUT_SECONDS, OpenAIAnswerGenerator
from evidence_rag.openrouter_answers import OpenRouterAnswerGenerator
from evidence_rag.policy import AnswerPolicy
from evidence_rag.retrieval.service import retrieve
from evidence_rag.semantic import LocalDeberta, SemanticVerifier

CallNext = Callable[[Request], Awaitable[Response]]
LOGGER = logging.getLogger("evidence_rag.requests")


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
    requires_visual_evidence: bool = False
    external_answer_consent: Literal["openai", "openrouter", "codex"] | None = None


class QueryResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    result: AnswerResult
    retrieval: tuple[dict[str, object], ...]
    mode: Literal["bm25", "dense", "hybrid", "reranked"]
    retrieval_status: str
    timings_ms: dict[str, float]


def create_app(
    settings: AppSettings | None = None,
    *,
    answer_generator: AnswerGenerator | None = None,
    semantic_verifier: SemanticVerifier | None = None,
    openai_generator: OpenAIAnswerGenerator | None = None,
    openrouter_generator: OpenRouterAnswerGenerator | None = None,
    codex_generator: CodexAnswerGenerator | None = None,
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
        ocr_enabled=resolved_settings.ocr_enabled,
        tessdata=resolved_settings.ocr_tessdata,
        ocr_language=resolved_settings.ocr_language,
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
    if semantic_verifier is None and resolved_settings.semantic_verifier:
        semantic_verifier = SemanticVerifier(LocalDeberta(resolved_settings.model_cache_dir))
    policy = AnswerPolicy() if resolved_settings.abstention_policy == "grounding-v1" else None
    answer_service = GroundedAnswerService(
        artifact_store, chosen_generator, verifier=semantic_verifier, policy=policy
    )
    live_provider = resolved_settings.live_answer_provider
    live_generator: OpenAIAnswerGenerator | OpenRouterAnswerGenerator | CodexAnswerGenerator | None
    live_generator = None
    if live_provider == "openai":
        key = resolved_settings.openai_api_key
        live_generator = openai_generator or OpenAIAnswerGenerator(
            key.get_secret_value() if key else None
        )
    elif live_provider == "openrouter":
        key = resolved_settings.openrouter_api_key
        live_generator = openrouter_generator or OpenRouterAnswerGenerator(
            key.get_secret_value() if key else None, resolved_settings.openrouter_model
        )
    elif live_provider == "codex":
        live_generator = codex_generator or CodexAnswerGenerator(resolved_settings.codex_executable)
    live_policy = AnswerPolicy()
    live_service = GroundedAnswerService(
        artifact_store,
        None,
        config=AnswerConfig(
            timeout_ms=int(
                (CODEX_TIMEOUT_SECONDS if live_provider == "codex" else TIMEOUT_SECONDS) * 1000
            )
        ),
        verifier=(
            semantic_verifier or SemanticVerifier(LocalDeberta(resolved_settings.model_cache_dir))
        )
        if live_generator is not None
        else None,
        policy=live_policy,
    )
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
        started = perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        route = request.scope.get("route")
        LOGGER.info(
            json.dumps(
                {
                    "event": "request_completed",
                    "request_id": request.state.request_id,
                    "route": getattr(route, "path", None),
                    "status": response.status_code,
                    "elapsed_ms": round((perf_counter() - started) * 1000, 3),
                    **getattr(request.state, "query_summary", {}),
                }
            )
        )
        return response

    @app.exception_handler(IntakeError)
    async def intake_error_handler(request: Request, exc: IntakeError) -> JSONResponse:
        """Return bounded errors without leaking private storage details."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {"code": exc.code, "message": exc.message},
                "request_id": request.state.request_id,
            },
        )

    @app.get("/health", response_model=HealthResponse, tags=["operations"])
    def health() -> HealthResponse:
        """Report process liveness without checking future dependencies."""
        return HealthResponse(version=__version__)

    @app.get("/api/v1/capabilities", tags=["operations"])
    def capabilities() -> dict[str, bool]:
        return {
            "fixture_demo_answers": resolved_settings.demo_answers,
            "openai_answers": live_provider == "openai",
            "openrouter_answers": live_provider == "openrouter",
            "codex_answers": live_provider == "codex",
        }

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
        try:
            resolved_settings.artifact_root.mkdir(parents=True, exist_ok=True)
            with TemporaryFile(dir=resolved_settings.artifact_root):
                pass
        except OSError:
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
                "Cache-Control": "private, no-cache",
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
    async def query_document(request: QueryRequest, http_request: Request) -> QueryResponse:
        if request.external_answer_consent != live_provider or live_generator is None:
            return await run_in_threadpool(run_query, request, http_request)
        cancelled = Event()

        async def watch_disconnect() -> None:
            while True:
                if (await http_request.receive())["type"] == "http.disconnect":
                    cancelled.set()
                    return

        async with create_task_group() as group:
            group.start_soon(watch_disconnect)
            try:
                result = await run_in_threadpool(run_query, request, http_request, cancelled)
            finally:
                cancelled.set()
                group.cancel_scope.cancel()
        return result

    def run_query(
        request: QueryRequest, http_request: Request, cancelled: Event | None = None
    ) -> QueryResponse:
        """Search a ready exact version and return a checked answer or abstention."""
        total_started = perf_counter()
        wants_live = request.external_answer_consent is not None
        service = live_service if wants_live else answer_service
        selected_policy = live_policy if wants_live else policy

        def record(result: QueryResponse) -> QueryResponse:
            http_request.state.query_summary = {
                "mode": result.mode,
                "outcome": result.result.reason or result.result.status,
                "stage_ms": result.timings_ms,
            }
            return result

        def without_ranking(reason: Reason) -> QueryResponse:
            return record(
                QueryResponse(
                    result=service.abstain(reason),
                    retrieval=(),
                    mode=request.mode,
                    retrieval_status=reason,
                    timings_ms={"total": (perf_counter() - total_started) * 1000},
                )
            )

        try:
            manifest = artifact_store.get_manifest(request.document_id, request.document_sha256)
        except ArtifactNotFoundError as exc:
            raise IntakeError("document_not_found", "Document version not found.", 404) from exc
        if manifest.state is not IngestionState.READY:
            if selected_policy and manifest.state in (
                IngestionState.FAILED,
                IngestionState.PARTIAL,
            ):
                reason: Reason = (
                    "indexing_failed"
                    if manifest.failure_stage
                    in (IngestionStage.PERSISTENCE, IngestionStage.RENDERING)
                    else "parsing_failed"
                )
                return without_ranking(reason)
            raise IntakeError("document_not_ready", "Document version is not ready.", 409)
        if request.requires_visual_evidence:
            return without_ranking("unsupported_modality")
        try:
            evidence = artifact_store.get_evidence(request.document_id, request.document_sha256)
            pages = artifact_store.get_page_manifest(request.document_id, request.document_sha256)
        except (ArtifactNotFoundError, StorageError) as exc:
            if selected_policy:
                return without_ranking("indexing_failed")
            raise IntakeError(
                "ready_artifacts_missing", "Ready document artifacts are missing.", 409
            ) from exc
        try:
            hits, timings, retrieval_status = retrieve(
                request.question, request.mode, evidence.units, manifest, resolved_settings
            )
        except IntakeError as exc:
            if selected_policy and exc.code == "retrieval_failed":
                return without_ranking("indexing_failed")
            raise
        timings["retrieval_total"] = (perf_counter() - total_started) * 1000
        try:
            started = perf_counter()
            generate = (
                partial(live_generator.generate_cancellable, cancelled=cancelled)
                if request.external_answer_consent == live_provider
                and live_generator is not None
                and cancelled is not None
                else None
            )
            answer = service.answer(
                request.question,
                manifest,
                pages,
                evidence.units,
                hits,
                generate=generate,
                cancelled=cancelled,
            )
            if generate is not None:
                answer = answer.model_copy(update={"answer_source": live_provider})
            elif not wants_live and isinstance(chosen_generator, FixtureDemoGenerator):
                answer = answer.model_copy(update={"answer_source": "atlas_demo"})
            timings["answer"] = (perf_counter() - started) * 1000
        except ValueError as exc:
            if selected_policy:
                return without_ranking("indexing_failed")
            raise IntakeError(
                "evidence_mismatch", "Document evidence is inconsistent.", 409
            ) from exc
        timings["total"] = (perf_counter() - total_started) * 1000
        return record(
            QueryResponse(
                result=answer,
                retrieval=tuple(asdict(hit) for hit in hits),
                mode=request.mode,
                retrieval_status=retrieval_status,
                timings_ms=timings,
            )
        )

    return app
