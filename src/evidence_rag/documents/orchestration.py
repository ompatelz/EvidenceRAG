"""Reliable bounded synchronous orchestration for one immutable PDF version."""

from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from threading import Lock
from time import perf_counter

from evidence_rag.documents.errors import IntakeError
from evidence_rag.documents.lifecycle import IngestionMode, assert_transition
from evidence_rag.documents.models import (
    DocumentIngestionResponse,
    DocumentIngestionStatusResponse,
    EvidenceArtifact,
    IngestionManifest,
    IngestionStage,
    IngestionState,
    ParseIssue,
    StageTiming,
)
from evidence_rag.documents.parser import ParserError, PdfParser
from evidence_rag.documents.rendering import PageRenderer, RenderError
from evidence_rag.documents.storage import (
    ArtifactNotFoundError,
    LocalArtifactStore,
    StorageError,
)
from evidence_rag.documents.telemetry import log_ingestion_event

Clock = Callable[[], float]
Now = Callable[[], datetime]


class DocumentIngestionService:
    """Commit evidence, previews, and ready state through one synchronous workflow."""

    def __init__(
        self,
        store: LocalArtifactStore,
        parser: PdfParser,
        renderer: PageRenderer,
        *,
        clock: Clock = perf_counter,
        now: Now | None = None,
    ) -> None:
        self.store = store
        self.parser = parser
        self.renderer = renderer
        self.clock = clock
        self.now = now or (lambda: datetime.now(UTC))
        self._lock = Lock()

    def ingest(
        self,
        document_id: str,
        document_sha256: str,
        *,
        request_id: str,
        mode: IngestionMode = IngestionMode.INGEST,
        duplicate: bool = False,
    ) -> DocumentIngestionResponse:
        """Run or resume one complete bounded attempt under an in-process lock."""
        with self._lock:
            return self._ingest_locked(
                document_id,
                document_sha256,
                request_id=request_id,
                mode=mode,
                duplicate=duplicate,
            )

    def status(self, document_id: str, document_sha256: str) -> DocumentIngestionStatusResponse:
        try:
            manifest = self.store.get_manifest_or_recover(document_id, document_sha256)
        except ArtifactNotFoundError as exc:
            raise IntakeError("document_not_found", "Document version not found.", 404) from exc
        return DocumentIngestionStatusResponse.from_manifest(manifest)

    def _ingest_locked(
        self,
        document_id: str,
        document_sha256: str,
        *,
        request_id: str,
        mode: IngestionMode,
        duplicate: bool,
    ) -> DocumentIngestionResponse:
        try:
            manifest = self.store.get_manifest_or_recover(document_id, document_sha256)
        except ArtifactNotFoundError as exc:
            raise IntakeError("document_not_found", "Document version not found.", 404) from exc

        if manifest.state is IngestionState.READY:
            if self._ready_artifacts_match(manifest):
                if mode is IngestionMode.REINDEX:
                    pass
                elif mode is IngestionMode.RETRY:
                    raise IntakeError(
                        "retry_not_required",
                        "The document version is already ready.",
                        409,
                    )
                else:
                    return self._response(manifest, duplicate=duplicate)
            else:
                manifest = self._fail(
                    manifest,
                    request_id=request_id,
                    stage=IngestionStage.PERSISTENCE,
                    code="ready_artifact_mismatch",
                    timings=list(manifest.stage_timings),
                    total_start=self.clock(),
                )
                mode = IngestionMode.RETRY

        if manifest.state in {IngestionState.FAILED, IngestionState.PARTIAL}:
            if mode is IngestionMode.INGEST:
                return self._response(manifest, duplicate=duplicate)
        elif manifest.state in {
            IngestionState.VALIDATING,
            IngestionState.PARSING,
            IngestionState.RENDERING,
            IngestionState.PERSISTING,
        }:
            if mode is IngestionMode.INGEST:
                raise IntakeError(
                    "ingestion_in_progress",
                    "A prior ingestion attempt did not reach a terminal state; retry it.",
                    409,
                )
            manifest = self._fail(
                manifest,
                request_id=request_id,
                stage=self._state_stage(manifest.state),
                code="interrupted_attempt",
                timings=list(manifest.stage_timings),
                total_start=self.clock(),
            )
        elif mode is IngestionMode.RETRY and manifest.state is not IngestionState.FAILED:
            raise IntakeError(
                "retry_not_allowed",
                "Retry is available only for failed, partial, or interrupted attempts.",
                409,
            )

        total_start = self.clock()
        timings: list[StageTiming] = []
        manifest = self._transition(
            manifest,
            IngestionState.VALIDATING,
            request_id=request_id,
            timings=timings,
            attempt_count=manifest.attempt_count + 1,
            parser=None,
            renderer=None,
            evidence_count=0,
            page_count=0,
        )
        self._persist(manifest)
        self._log("ingestion_started", manifest, request_id, IngestionStage.VALIDATION)

        validation_start = self.clock()
        try:
            self.store.remove_derived_artifacts(document_id, document_sha256)
            self.store.validate_source_integrity(manifest)
        except (ArtifactNotFoundError, OSError, StorageError):
            timings.append(self._timing(IngestionStage.VALIDATION, validation_start))
            failed = self._fail(
                manifest,
                request_id=request_id,
                stage=IngestionStage.VALIDATION,
                code="source_validation_failed",
                timings=timings,
                total_start=total_start,
            )
            return self._response(failed, duplicate=duplicate)
        timings.append(self._timing(IngestionStage.VALIDATION, validation_start))

        manifest = self._transition(
            manifest,
            IngestionState.PARSING,
            request_id=request_id,
            timings=timings,
            parser=self.parser.metadata,
        )
        self._persist(manifest)
        self._log("stage_started", manifest, request_id, IngestionStage.PARSING)

        parsing_start = self.clock()
        try:
            result = self.parser.parse(self.store.source_path(manifest), manifest)
        except ParserError as exc:
            timings.append(self._timing(IngestionStage.PARSING, parsing_start))
            failed = self._fail(
                manifest,
                request_id=request_id,
                stage=IngestionStage.PARSING,
                code=exc.code,
                timings=timings,
                total_start=total_start,
            )
            return self._response(failed, duplicate=duplicate)
        except Exception:
            timings.append(self._timing(IngestionStage.PARSING, parsing_start))
            failed = self._fail(
                manifest,
                request_id=request_id,
                stage=IngestionStage.PARSING,
                code="parser_unexpected_failure",
                timings=timings,
                total_start=total_start,
            )
            return self._response(failed, duplicate=duplicate)
        timings.append(self._timing(IngestionStage.PARSING, parsing_start))

        issues = list(result.issues)
        if result.successful_pages == 0:
            issues.append(
                ParseIssue(
                    code="all_pages_failed",
                    message="No PDF page could be parsed successfully.",
                )
            )
            failed = self._fail(
                manifest,
                request_id=request_id,
                stage=IngestionStage.PARSING,
                code=issues[0].code,
                timings=timings,
                total_start=total_start,
            )
            return self._response(failed, duplicate=duplicate)
        if not result.units and not issues:
            issues.append(
                ParseIssue(
                    code="empty_extraction",
                    message="The PDF produced no supported evidence units.",
                )
            )

        evidence = EvidenceArtifact(
            document_id=manifest.document_id,
            document_version=manifest.document_version,
            document_sha256=manifest.document_sha256,
            parser=self.parser.metadata,
            page_count=result.page_count,
            units=list(result.units),
            issues=issues,
        )
        manifest = self._transition(
            manifest,
            IngestionState.RENDERING,
            request_id=request_id,
            timings=timings,
            renderer=self.renderer.metadata,
        )
        self._persist(manifest)
        self._log("stage_started", manifest, request_id, IngestionStage.RENDERING)

        rendering_start = self.clock()
        try:
            with self.store.stage_page_previews(document_id, document_sha256) as staging:
                pages = self.renderer.render(self.store.source_path(manifest), manifest, staging)
                if len(pages.pages) != result.page_count:
                    raise RenderError(
                        "page_count_mismatch",
                        "Rendered pages do not match parsed page provenance.",
                    )
                timings.append(self._timing(IngestionStage.RENDERING, rendering_start))
                persistence_start = self.clock()
                manifest = self._transition(
                    manifest,
                    IngestionState.PERSISTING,
                    request_id=request_id,
                    timings=timings,
                )
                self._persist(manifest)
                self._log("stage_started", manifest, request_id, IngestionStage.PERSISTENCE)

                self.store.write_evidence(evidence)
                self.store.publish_page_previews(pages, staging)
                timings.append(self._timing(IngestionStage.PERSISTENCE, persistence_start))
        except RenderError as exc:
            timings.append(self._timing(IngestionStage.RENDERING, rendering_start))
            failed = self._fail(
                manifest,
                request_id=request_id,
                stage=IngestionStage.RENDERING,
                code=exc.code,
                timings=timings,
                total_start=total_start,
            )
            return self._response(failed, duplicate=duplicate)
        except Exception as exc:
            current_stage = (
                IngestionStage.PERSISTENCE
                if manifest.state is IngestionState.PERSISTING
                else IngestionStage.RENDERING
            )
            if current_stage is IngestionStage.RENDERING:
                timings.append(self._timing(IngestionStage.RENDERING, rendering_start))
                failed = self._fail(
                    manifest,
                    request_id=request_id,
                    stage=current_stage,
                    code="renderer_unexpected_failure",
                    timings=timings,
                    total_start=total_start,
                )
                return self._response(failed, duplicate=duplicate)
            timings.append(self._timing(IngestionStage.PERSISTENCE, persistence_start))
            with suppress(ArtifactNotFoundError, OSError, StorageError):
                self.store.remove_derived_artifacts(document_id, document_sha256)
            with suppress(ArtifactNotFoundError, OSError, StorageError):
                self._fail(
                    manifest,
                    request_id=request_id,
                    stage=current_stage,
                    code="artifact_persistence_failed",
                    timings=timings,
                    total_start=total_start,
                )
            raise IntakeError(
                "artifact_persistence_failed",
                "Evidence and previews could not be committed safely.",
                500,
            ) from exc

        timings.append(self._timing(IngestionStage.TOTAL, total_start))
        final_state = IngestionState.PARTIAL if issues else IngestionState.READY
        final_updates: dict[str, object] = {
            "evidence_count": len(evidence.units),
            "page_count": len(pages.pages),
            "stage_timings": timings,
        }
        if final_state is IngestionState.PARTIAL:
            final_updates.update(
                {
                    "failure_reason": issues[0].code,
                    "failure_stage": IngestionStage.PARSING,
                }
            )
        else:
            final_updates["ready_at"] = self.now()
        try:
            final = self._transition(
                manifest,
                final_state,
                request_id=request_id,
                timings=timings,
                **final_updates,
            )
            self._persist(final)
        except Exception as exc:
            with suppress(ArtifactNotFoundError, OSError, StorageError):
                self.store.remove_derived_artifacts(document_id, document_sha256)
            with suppress(Exception):
                self._fail(
                    manifest,
                    request_id=request_id,
                    stage=IngestionStage.PERSISTENCE,
                    code="final_manifest_failed",
                    timings=timings,
                    total_start=total_start,
                )
            raise IntakeError(
                "final_manifest_failed",
                "The final ready manifest could not be committed safely.",
                500,
            ) from exc
        self._log("ingestion_completed", final, request_id, IngestionStage.TOTAL)
        return self._response(final, duplicate=duplicate)

    def _fail(
        self,
        manifest: IngestionManifest,
        *,
        request_id: str,
        stage: IngestionStage,
        code: str,
        timings: list[StageTiming],
        total_start: float,
    ) -> IngestionManifest:
        if not timings or timings[-1].stage is not IngestionStage.TOTAL:
            timings = [*timings, self._timing(IngestionStage.TOTAL, total_start)]
        with suppress(ArtifactNotFoundError, OSError, StorageError):
            self.store.remove_derived_artifacts(manifest.document_id, manifest.document_sha256)
        failed = self._transition(
            manifest,
            IngestionState.FAILED,
            request_id=request_id,
            timings=timings,
            evidence_count=0,
            page_count=0,
            failure_reason=code,
            failure_stage=stage,
        )
        self._persist(failed)
        self._log("ingestion_failed", failed, request_id, stage, error_code=code)
        return failed

    def _transition(
        self,
        manifest: IngestionManifest,
        target: IngestionState,
        *,
        request_id: str,
        timings: list[StageTiming],
        **updates: object,
    ) -> IngestionManifest:
        assert_transition(manifest.state, target)
        payload = manifest.model_dump(mode="python")
        payload.update(
            {
                "state": target,
                "updated_at": self.now(),
                "last_request_id": request_id,
                "stage_timings": timings,
                "ready_at": None,
            }
        )
        if target not in {IngestionState.PARTIAL, IngestionState.FAILED}:
            payload.update({"failure_reason": None, "failure_stage": None})
        payload.update(updates)
        return IngestionManifest.model_validate(payload)

    def _persist(self, manifest: IngestionManifest) -> None:
        try:
            self.store.update_manifest(manifest)
        except (ArtifactNotFoundError, OSError, StorageError) as exc:
            raise IntakeError(
                "manifest_update_failed",
                "The ingestion lifecycle could not be recorded safely.",
                500,
            ) from exc

    def _ready_artifacts_match(self, manifest: IngestionManifest) -> bool:
        try:
            evidence = self.store.get_evidence(manifest.document_id, manifest.document_sha256)
            pages = self.store.get_page_manifest(manifest.document_id, manifest.document_sha256)
            if (
                evidence.parser != manifest.parser
                or pages.renderer != manifest.renderer
                or len(evidence.units) != manifest.evidence_count
                or len(pages.pages) != manifest.page_count
                or evidence.page_count != len(pages.pages)
            ):
                return False
            for page in pages.pages:
                self.store.preview_path(
                    manifest.document_id,
                    manifest.document_sha256,
                    page.page_index,
                )
        except (ArtifactNotFoundError, OSError, StorageError):
            return False
        return True

    def _timing(self, stage: IngestionStage, started: float) -> StageTiming:
        return StageTiming(stage=stage, duration_ms=max(0.0, (self.clock() - started) * 1000))

    def _log(
        self,
        event: str,
        manifest: IngestionManifest,
        request_id: str,
        stage: IngestionStage,
        *,
        error_code: str | None = None,
    ) -> None:
        duration = next(
            (
                timing.duration_ms
                for timing in reversed(manifest.stage_timings)
                if timing.stage is stage
            ),
            None,
        )
        log_ingestion_event(
            event,
            request_id=request_id,
            document_id=manifest.document_id,
            document_sha256=manifest.document_sha256,
            state=manifest.state,
            stage=stage,
            duration_ms=duration,
            error_code=error_code,
        )

    @staticmethod
    def _state_stage(state: IngestionState) -> IngestionStage:
        return {
            IngestionState.VALIDATING: IngestionStage.VALIDATION,
            IngestionState.PARSING: IngestionStage.PARSING,
            IngestionState.RENDERING: IngestionStage.RENDERING,
            IngestionState.PERSISTING: IngestionStage.PERSISTENCE,
        }[state]

    @staticmethod
    def _response(manifest: IngestionManifest, *, duplicate: bool) -> DocumentIngestionResponse:
        status = DocumentIngestionStatusResponse.from_manifest(manifest)
        return DocumentIngestionResponse(**status.model_dump(), duplicate=duplicate)
