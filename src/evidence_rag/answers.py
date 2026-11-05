"""Bounded evidence packs and deterministic citation validation for local QA."""

from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from evidence_rag.documents.models import IngestionManifest, IngestionState, PagePreviewManifest
from evidence_rag.documents.storage import ArtifactNotFoundError, LocalArtifactStore
from evidence_rag.evidence import AnchorPrecision, EvidenceUnit


class RankedCandidate(Protocol):
    @property
    def evidence_id(self) -> str: ...

    @property
    def document_id(self) -> str: ...

    @property
    def document_version(self) -> str: ...

    @property
    def page_index(self) -> int: ...


class PackItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    document_id: str
    document_version: str
    page_index: int
    text: str


class EvidencePack(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    items: tuple[PackItem, ...]
    excluded_ids: tuple[str, ...]


class DraftCitation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    document_id: str
    document_version: str
    page_index: int = Field(ge=0)


class DraftClaim(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(min_length=1, max_length=1000)
    citations: tuple[DraftCitation, ...] = Field(min_length=1, max_length=5)


class DraftAnswer(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["answered", "insufficient_evidence"]
    answer: str | None = Field(default=None, max_length=2000)
    claims: tuple[DraftClaim, ...] = Field(default=(), max_length=8)

    @model_validator(mode="after")
    def check_shape(self) -> "DraftAnswer":
        if self.status == "answered" and (not self.answer or not self.claims):
            raise ValueError("answered response requires answer and claims")
        if self.status == "insufficient_evidence" and (self.answer or self.claims):
            raise ValueError("insufficient response cannot contain claims")
        return self


class Citation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    document_id: str
    document_version: str
    page_index: int
    precision: AnchorPrecision
    preview_asset_id: str | None


class ValidatedClaim(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    citations: tuple[Citation, ...]


class AnswerResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["answered", "insufficient_evidence"]
    reason: Literal[
        "answered",
        "no_relevant_evidence",
        "unsupported_question",
        "generator_unavailable",
        "generation_failed",
        "generation_timeout",
        "malformed_response",
        "invalid_citation",
    ]
    answer: str | None
    claims: tuple[ValidatedClaim, ...]
    supplied_evidence_ids: tuple[str, ...]
    excluded_evidence_ids: tuple[str, ...]


Reason = Literal[
    "answered",
    "no_relevant_evidence",
    "unsupported_question",
    "generator_unavailable",
    "generation_failed",
    "generation_timeout",
    "malformed_response",
    "invalid_citation",
]


class AnswerGenerator(Protocol):
    def generate(self, question: str, pack: EvidencePack) -> Mapping[str, Any] | DraftAnswer: ...


class ScriptedGenerator:
    """Deterministic saved-response generator for tests and owned-fixture demos."""

    def __init__(self, responses: Mapping[str, Mapping[str, Any] | DraftAnswer]) -> None:
        self.responses = responses

    def generate(self, question: str, pack: EvidencePack) -> Mapping[str, Any] | DraftAnswer:
        return self.responses.get(question, {"status": "insufficient_evidence"})


class FixtureDemoGenerator:
    """One explicit owned-fixture answer; no general inference is implied."""

    QUESTION = "What is the calibration sampling rate of the Atlas sensor?"
    DOCUMENT_ID = "doc_cedee38ab4152274426cf3f8"
    DOCUMENT_VERSION = "sha256:b6a8b1d7f3fda491b08adf9aeb1bc40d1b073804ab63045e3cf090ff1dff4aaa"
    EVIDENCE_ID = "ev_db963e2e6b7064f643c914bace118433"

    def generate(self, question: str, pack: EvidencePack) -> Mapping[str, Any]:
        if question != self.QUESTION:
            return {"status": "insufficient_evidence"}
        item = next((unit for unit in pack.items if unit.evidence_id == self.EVIDENCE_ID), None)
        if item is None or (item.document_id, item.document_version, item.page_index) != (
            self.DOCUMENT_ID,
            self.DOCUMENT_VERSION,
            0,
        ):
            return {"status": "insufficient_evidence"}
        if "20 hertz" not in item.text.casefold():
            return {"status": "insufficient_evidence"}
        answer = "The Atlas sensor's calibration sampling rate is 20 hertz."
        return {
            "status": "answered",
            "answer": answer,
            "claims": [
                {
                    "text": answer,
                    "citations": [
                        {
                            "evidence_id": item.evidence_id,
                            "document_id": item.document_id,
                            "document_version": item.document_version,
                            "page_index": item.page_index,
                        }
                    ],
                }
            ],
        }


@dataclass(frozen=True)
class AnswerConfig:
    max_candidates: int = 5
    max_pack_chars: int = 4000
    max_item_chars: int = 1200
    timeout_ms: int = 2000

    def __post_init__(self) -> None:
        if not (1 <= self.max_candidates <= 20):
            raise ValueError("candidate limit must be bounded")
        if self.max_pack_chars < 1 or self.max_item_chars < 1 or self.timeout_ms < 1:
            raise ValueError("answer budgets and timeout must be positive")


def build_pack(
    hits: Sequence[RankedCandidate],
    units: Mapping[str, EvidenceUnit],
    *,
    document_id: str,
    document_version: str,
    config: AnswerConfig,
) -> EvidencePack:
    """Keep ranked, authorized text within both per-item and total budgets."""
    items: list[PackItem] = []
    excluded: list[str] = []
    remaining = config.max_pack_chars
    seen: set[str] = set()
    for hit in hits:
        if hit.evidence_id in seen:
            continue
        seen.add(hit.evidence_id)
        unit = units.get(hit.evidence_id)
        if unit is None or (
            hit.document_id,
            hit.document_version,
            unit.document_id,
            unit.document_version,
        ) != (document_id, document_version, document_id, document_version):
            raise ValueError("retrieved evidence is not in the authorized document version")
        if unit.page_index != hit.page_index:
            raise ValueError("retrieved evidence page mismatch")
        if len(items) >= config.max_candidates or remaining <= 0:
            excluded.append(hit.evidence_id)
            continue
        text = unit.text[: min(config.max_item_chars, remaining)]
        if not text:
            excluded.append(hit.evidence_id)
            continue
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
    return EvidencePack(items=tuple(items), excluded_ids=tuple(excluded))


class GroundedAnswerService:
    def __init__(
        self,
        store: LocalArtifactStore,
        generator: AnswerGenerator | None,
        config: AnswerConfig | None = None,
    ) -> None:
        self.store = store
        self.generator = generator
        self.config = config or AnswerConfig()

    def answer(
        self,
        question: str,
        manifest: IngestionManifest,
        pages: PagePreviewManifest,
        units: Sequence[EvidenceUnit],
        hits: Sequence[RankedCandidate],
    ) -> AnswerResult:
        if manifest.state is not IngestionState.READY:
            raise ValueError("document version is not ready")
        if (pages.document_id, pages.document_version) != (
            manifest.document_id,
            manifest.document_version,
        ):
            raise ValueError("preview manifest version mismatch")
        unit_map = {unit.evidence_id: unit for unit in units}
        pack = build_pack(
            hits,
            unit_map,
            document_id=manifest.document_id,
            document_version=manifest.document_version,
            config=self.config,
        )

        def insufficient(reason: Reason) -> AnswerResult:
            return AnswerResult(
                status="insufficient_evidence",
                reason=reason,
                answer=None,
                claims=(),
                supplied_evidence_ids=tuple(item.evidence_id for item in pack.items),
                excluded_evidence_ids=pack.excluded_ids,
            )

        if not pack.items:
            return insufficient("no_relevant_evidence")
        if self.generator is None:
            return insufficient("generator_unavailable")
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="answer-generator")
        future = pool.submit(self.generator.generate, question, pack)
        try:
            raw = future.result(timeout=self.config.timeout_ms / 1000)
        except FutureTimeout:
            future.cancel()
            return insufficient("generation_timeout")
        except Exception:
            return insufficient("generation_failed")
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        try:
            draft = DraftAnswer.model_validate(raw)
        except ValidationError:
            return insufficient("malformed_response")
        if draft.status == "insufficient_evidence":
            return insufficient("unsupported_question")
        supplied = {item.evidence_id for item in pack.items}
        validated: list[ValidatedClaim] = []
        try:
            for claim in draft.claims:
                citations = []
                for ref in claim.citations:
                    if ref.evidence_id not in supplied:
                        raise ValueError("citation was not supplied")
                    unit = unit_map[ref.evidence_id]
                    if (ref.document_id, ref.document_version, ref.page_index) != (
                        unit.document_id,
                        unit.document_version,
                        unit.page_index,
                    ) or (unit.document_id, unit.document_version) != (
                        manifest.document_id,
                        manifest.document_version,
                    ):
                        raise ValueError("citation provenance mismatch")
                    if unit.page_index >= len(pages.pages):
                        raise ValueError("citation page missing")
                    if unit.anchor_precision is AnchorPrecision.UNAVAILABLE:
                        raise ValueError("citation location unavailable")
                    try:
                        self.store.preview_path(
                            manifest.document_id, manifest.document_sha256, unit.page_index
                        )
                    except ArtifactNotFoundError as exc:
                        raise ValueError("citation preview missing") from exc
                    preview = pages.pages[unit.page_index]
                    citations.append(
                        Citation(
                            evidence_id=unit.evidence_id,
                            document_id=unit.document_id,
                            document_version=unit.document_version,
                            page_index=unit.page_index,
                            precision=unit.anchor_precision,
                            preview_asset_id=preview.asset_id,
                        )
                    )
                validated.append(ValidatedClaim(text=claim.text, citations=tuple(citations)))
        except (ValueError, KeyError):
            return insufficient("invalid_citation")
        return AnswerResult(
            status="answered",
            reason="answered",
            answer=draft.answer,
            claims=tuple(validated),
            supplied_evidence_ids=tuple(sorted(supplied)),
            excluded_evidence_ids=pack.excluded_ids,
        )
