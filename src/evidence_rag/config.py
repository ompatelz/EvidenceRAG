"""Small, injectable application configuration boundary."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Configuration required to construct the local application."""

    model_config = SettingsConfigDict(
        frozen=True,
        extra="forbid",
        env_prefix="EVIDENCERAG_",
    )

    app_name: str = "EvidenceRAG"
    environment: str = "local"
    ready: bool = True
    artifact_root: Path = Path("artifacts")
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1, le=1024 * 1024 * 1024)
    upload_chunk_bytes: int = Field(default=64 * 1024, ge=4096, le=1024 * 1024)
    multipart_overhead_bytes: int = Field(default=1024 * 1024, ge=64 * 1024)
    max_pdf_pages: int = Field(default=200, ge=1, le=10_000)
    max_evidence_units: int = Field(default=10_000, ge=1, le=1_000_000)
    render_dpi: int = Field(default=144, ge=36, le=600)
    max_render_pixels_per_page: int = Field(default=20_000_000, ge=1, le=200_000_000)
    max_render_pixels_total: int = Field(default=100_000_000, ge=1, le=1_000_000_000)
