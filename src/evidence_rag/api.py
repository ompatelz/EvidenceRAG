"""FastAPI application factory and operational endpoints."""

from typing import Literal

from fastapi import FastAPI, Response, status
from pydantic import BaseModel, ConfigDict

from evidence_rag import __version__
from evidence_rag.config import AppSettings


class HealthResponse(BaseModel):
    """Stable liveness response."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"] = "ok"
    version: str


class ReadinessResponse(BaseModel):
    """Stable readiness response."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ready", "not_ready"]


def create_app(settings: AppSettings | None = None) -> FastAPI:
    """Construct an isolated application using explicit settings."""
    resolved_settings = settings or AppSettings()
    app = FastAPI(
        title=resolved_settings.app_name,
        version=__version__,
        description="Evidence-first document retrieval API (foundation slice)",
    )
    app.state.settings = resolved_settings

    @app.get("/health", response_model=HealthResponse, tags=["operations"])
    def health() -> HealthResponse:
        """Report process liveness without checking future dependencies."""
        return HealthResponse(version=__version__)

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

    return app
