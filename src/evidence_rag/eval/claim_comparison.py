"""Compare paired query pipelines with a fixed saved generator output."""

import argparse
import hashlib
import json
import math
import platform
from collections.abc import Sequence
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Literal

from pydantic import BaseModel, ConfigDict

from evidence_rag.answers import (
    AnswerConfig,
    AnswerResult,
    DraftAnswer,
    GroundedAnswerService,
    ScriptedGenerator,
)
from evidence_rag.documents.models import IngestionState
from evidence_rag.documents.orchestration import DocumentIngestionService
from evidence_rag.documents.parser import PyMuPDFParser
from evidence_rag.documents.rendering import PyMuPDFPageRenderer
from evidence_rag.documents.service import DocumentIntakeService
from evidence_rag.documents.storage import LocalArtifactStore
from evidence_rag.eval.policy_validation import Outcome, metrics
from evidence_rag.evidence import EvidenceUnit
from evidence_rag.policy import MIN_SUPPORT_MARGIN, POLICY_VERSION, AnswerPolicy
from evidence_rag.retrieval.bm25 import INDEX_VERSION, TOKENIZER_VERSION, BM25Index, RankedEvidence
from evidence_rag.semantic import (
    MODEL_NAME,
    MODEL_REVISION,
    PREPROCESSING,
    LocalDeberta,
    SemanticVerifier,
)

DATA = Path("datasets/eval/claim_comparison.jsonl")
SOURCE = Path("src/evidence_rag")


class Case(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    document: Literal[
        "atlas-narrative.pdf", "retrieval-table.pdf", "checksum-retry.pdf", "cache-admission.pdf"
    ]
    split: Literal["development", "validation"]
    question: str
    category: str
    answerable: bool
    draft_correct: bool
    claim: str
    cite: str
    expected_page: int | None
    claim_supported: bool
    logits: tuple[float, float, float] | None
    gold: str | None
    review: Literal["needs_human_review", "verified"]


class ArmRun(BaseModel):
    latency_ms: float
    result: AnswerResult
    retrieval: tuple[RankedEvidence, ...]
    citation_support: list[bool]
    page_grounding: list[bool]
    region_grounding: list[bool]


class CaseRun(BaseModel):
    case: Case
    draft: DraftAnswer
    gold_evidence_id: str | None
    arms: dict[str, ArmRun]


class ReplayScorer:
    model = MODEL_NAME
    revision = MODEL_REVISION

    def __init__(self, scores: dict[str, tuple[float, float, float]]) -> None:
        self.scores = scores

    def logits(self, premise: str, claim: str) -> Sequence[float]:
        return self.scores[claim]


def _unit(units: Sequence[EvidenceUnit], token: str) -> EvidenceUnit:
    candidates = [unit for unit in units if token in unit.text]
    if len(candidates) != 1:
        raise ValueError(f"expected one source matching fixture text {token!r}")
    return candidates[0]


def run(root: Path, *, cache_dir: Path | None = None, smoke: bool = False) -> dict[str, object]:
    source = DATA.read_bytes().replace(b"\r\n", b"\n")
    cases = [Case.model_validate_json(line) for line in source.splitlines() if line.strip()]
    if not cases or len({case.id for case in cases}) != len(cases):
        raise ValueError("comparison cases must have unique IDs and be nonempty")
    if smoke:
        cases = [
            case
            for case in cases
            if case.id in {"table-lookup", "table-wrong", "atlas-false-positive"}
        ]
        if len(cases) != 3:
            raise ValueError("missing smoke fixture")
    store = LocalArtifactStore(root, max_upload_bytes=10 * 1024 * 1024, chunk_bytes=65536)
    intake = DocumentIntakeService(store)
    ingestion = DocumentIngestionService(store, PyMuPDFParser(), PyMuPDFPageRenderer())
    scopes = {}
    for document in sorted({case.document for case in cases}):
        with (Path("datasets/fixtures") / document).open("rb") as stream:
            intake_result = intake.accept(stream, document)
        key = intake_result.document_id, intake_result.document_sha256
        ingested = ingestion.ingest(*key, request_id="claim-comparison")
        if ingested.state is not IngestionState.READY:
            raise ValueError(f"{document} is not ready")
        scopes[document] = key
    scorer = (
        LocalDeberta(cache_dir)
        if cache_dir is not None
        else ReplayScorer({case.claim: case.logits for case in cases if case.logits is not None})
    )
    verifier = SemanticVerifier(scorer)
    raw = []
    for case in cases:
        scope = scopes[case.document]
        evidence = store.get_evidence(*scope)
        cited = _unit(evidence.units, case.cite)
        gold = _unit(evidence.units, case.gold) if case.gold is not None else None
        if gold is not None and gold.page_index != case.expected_page:
            raise ValueError(f"gold page mismatch for {case.id}")
        draft = DraftAnswer.model_validate(
            {
                "status": "answered",
                "answer": case.claim,
                "claims": [
                    {
                        "text": case.claim,
                        "citations": [
                            cited.model_dump(
                                include={
                                    "evidence_id",
                                    "document_id",
                                    "document_version",
                                    "page_index",
                                }
                            )
                        ],
                    }
                ],
            }
        )
        generator = ScriptedGenerator({case.question: draft})
        runs: dict[str, ArmRun] = {}
        for enabled in (False, True):
            arm = "support_on" if enabled else "support_off"
            service = GroundedAnswerService(
                store,
                generator,
                AnswerConfig(assess_support=enabled),
                verifier=verifier if enabled else None,
                policy=AnswerPolicy() if enabled else None,
            )
            started = perf_counter()
            manifest = store.get_manifest(*scope)
            artifact = store.get_evidence(*scope)
            pages = store.get_page_manifest(*scope)
            index = BM25Index()
            index.rebuild(artifact.units)
            ranking = index.search(
                case.question, k=5, versions=[(scope[0], manifest.document_version)]
            )
            result = service.answer(case.question, manifest, pages, artifact.units, ranking.hits)
            elapsed = (perf_counter() - started) * 1000
            if cache_dir is not None and any(
                claim.semantic_support
                and claim.semantic_support.status in {"unavailable", "failed"}
                for claim in result.claims
            ):
                raise ValueError("real verifier unavailable or failed during controlled comparison")
            emitted = result.status == "answered"
            reviewed_citations = result.claims[0].citations if emitted else ()
            runs[arm] = ArmRun(
                latency_ms=elapsed,
                result=result,
                retrieval=ranking.hits,
                citation_support=[case.claim_supported for _ in reviewed_citations],
                page_grounding=[
                    citation.page_index == case.expected_page
                    for citation in reviewed_citations
                    if case.expected_page is not None
                ],
                region_grounding=[
                    citation.evidence_id == gold.evidence_id and citation.precision == "region"
                    for citation in reviewed_citations
                    if gold is not None and gold.bbox is not None
                ],
            )
        if runs["support_off"].retrieval != runs["support_on"].retrieval:
            raise ValueError(f"paired ranking changed for {case.id}")
        raw.append(
            CaseRun(
                case=case,
                draft=draft,
                gold_evidence_id=gold.evidence_id if gold else None,
                arms=runs,
            )
        )

    summaries = {}
    for arm in ("support_off", "support_on"):
        outcomes = []
        group_outcomes: dict[str, list[Outcome]] = {}
        latency = []
        judgments: dict[str, list[bool]] = {
            "citation_support": [],
            "page_grounding": [],
            "region_grounding": [],
        }
        for case, row in zip(cases, raw, strict=True):
            output = row.arms[arm]
            outcome = Outcome(
                case.answerable,
                output.result.status == "answered",
                case.draft_correct,
                output.result.reason,
            )
            outcomes.append(outcome)
            group_outcomes.setdefault(case.category, []).append(outcome)
            latency.append(output.latency_ms)
            judgments["citation_support"].extend(output.citation_support)
            judgments["page_grounding"].extend(output.page_grounding)
            judgments["region_grounding"].extend(output.region_grounding)
        summaries[arm] = {
            **metrics(outcomes),
            "categories": {category: metrics(rows) for category, rows in group_outcomes.items()},
            "latency_p50_ms": median(latency),
            "latency_p95_ms": sorted(latency)[math.ceil(0.95 * len(latency)) - 1],
            **{
                metric: {"passed": sum(labels), "scored": len(labels)}
                for metric, labels in judgments.items()
            },
        }
    return {
        "manifest": {
            "dataset_sha256": hashlib.sha256(source).hexdigest(),
            "code_sha256": {
                path.relative_to(SOURCE).as_posix(): hashlib.sha256(
                    path.read_bytes().replace(b"\r\n", b"\n")
                ).hexdigest()
                for path in sorted(SOURCE.rglob("*.py"))
            },
            "case_ids": [case.id for case in cases],
            "documents": {name: sha for name, (_, sha) in scopes.items()},
            "splits": sorted({case.split for case in cases}),
            "retriever": {
                "name": "bm25",
                "index": INDEX_VERSION,
                "tokenizer": TOKENIZER_VERSION,
                "k": 5,
            },
            "generator": {"name": "saved-draft-v1", "prompt": None, "sampling": None},
            "common_answer_config": asdict(AnswerConfig()),
            "arms": {
                "support_off": {"assess_support": False},
                "support_on": {
                    "assess_support": True,
                    "policy": POLICY_VERSION,
                    "margin": MIN_SUPPORT_MARGIN,
                    "verifier": "local-onnx" if cache_dir is not None else "scripted-logits-v1",
                    "model": scorer.model if cache_dir is not None else None,
                    "revision": scorer.revision if cache_dir is not None else None,
                    "preprocessing": PREPROCESSING,
                    "verifier_timeout_ms": verifier.timeout_ms,
                },
            },
            "runtime": {
                "python": platform.python_version(),
                "system": platform.system(),
                "processor": platform.processor(),
                "pymupdf": version("pymupdf"),
                "onnxruntime": version("onnxruntime") if cache_dir is not None else None,
                "tokenizers": version("tokenizers") if cache_dir is not None else None,
            },
        },
        "summaries": summaries,
        "results": [row.model_dump(mode="json") for row in raw],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    with TemporaryDirectory() as directory:
        report = run(Path(directory), cache_dir=args.cache_dir, smoke=args.smoke)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
