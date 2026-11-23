"""Explicit visual handoff to a caller-supplied model; no network transport."""

import base64
import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from evidence_rag.sdk import DocumentRef, EvidenceRAG


class VisualPacket(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document: DocumentRef
    page_index: int
    image_sha256: str
    image_base64: str
    media_type: Literal["image/png"] = "image/png"
    interpretation: Literal["caller_required"] = "caller_required"
    claim_support: Literal["not_assessed"] = "not_assessed"
    content_trust: Literal["untrusted_document_data"] = "untrusted_document_data"


class VisualObservation(BaseModel):
    """A traceable model observation, never promoted to verified source text."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    document: DocumentRef
    page_index: int = Field(ge=0)
    image_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    model: str = Field(min_length=1, max_length=128)
    observation: str = Field(min_length=1, max_length=4000)
    limitations: str = Field(min_length=1, max_length=1000)


def page_image(engine: EvidenceRAG, document: DocumentRef, page_index: int) -> VisualPacket:
    """Return a bounded stored preview only after exact ready-version validation."""
    manifest, _, _ = engine._ready(document)
    if not 0 <= page_index < manifest.page_count:
        raise ValueError("invalid page index")
    path = engine.store.preview_path(document.document_id, document.document_sha256, page_index)
    with path.open("rb") as stream:
        data = stream.read(4 * 1024 * 1024 + 1)
    if len(data) > 4 * 1024 * 1024:
        raise ValueError("visual packet exceeds 4 MiB")
    return VisualPacket(
        document=document,
        page_index=page_index,
        image_sha256=hashlib.sha256(data).hexdigest(),
        image_base64=base64.b64encode(data).decode("ascii"),
    )


def check_observation(engine: EvidenceRAG, observation: VisualObservation) -> dict[str, object]:
    packet = page_image(engine, observation.document, observation.page_index)
    if packet.image_sha256 != observation.image_sha256:
        raise ValueError("observation image version mismatch")
    return {
        "provenance_valid": True,
        "claim_support": "not_assessed",
        "observation": observation.model_dump(mode="json"),
        "notice": "Image identity checked; visual interpretation requires independent review.",
    }
