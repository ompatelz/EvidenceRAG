"""Small, injectable application configuration boundary."""

from pydantic import BaseModel, ConfigDict


class AppSettings(BaseModel):
    """Configuration required to construct the Phase 0 application."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    app_name: str = "EvidenceRAG"
    environment: str = "local"
    ready: bool = True
