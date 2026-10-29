"""Source-safe structured ingestion logging."""

import json
import logging
from typing import Any

from evidence_rag.documents.models import IngestionStage, IngestionState

LOGGER = logging.getLogger("evidence_rag.ingestion")


def log_ingestion_event(
    event: str,
    *,
    request_id: str,
    document_id: str,
    document_sha256: str,
    state: IngestionState,
    stage: IngestionStage | None = None,
    duration_ms: float | None = None,
    error_code: str | None = None,
) -> None:
    """Emit bounded JSON fields without filenames, paths, or extracted text."""
    payload: dict[str, Any] = {
        "document_id": document_id,
        "document_sha256": document_sha256,
        "event": event,
        "request_id": request_id,
        "state": state.value,
    }
    if stage is not None:
        payload["stage"] = stage.value
    if duration_ms is not None:
        payload["duration_ms"] = round(duration_ms, 3)
    if error_code is not None:
        payload["error_code"] = error_code
    LOGGER.info(json.dumps(payload, sort_keys=True, separators=(",", ":")))
