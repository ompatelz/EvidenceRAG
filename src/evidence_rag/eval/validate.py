"""Validate committed evaluation JSONL and document manifests."""

import argparse
import hashlib
import io
import json
import re
import tempfile
from collections.abc import Sequence
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from evidence_rag.documents.parser import PyMuPDFParser
from evidence_rag.documents.storage import LocalArtifactStore
from evidence_rag.eval.models import DocumentManifest, EvaluationItem
from evidence_rag.evidence import AnchorPrecision, EvidenceUnit


class DatasetValidationError(ValueError):
    """Raised when evaluation data is inconsistent or cannot be parsed."""


def load_manifest(path: Path) -> DocumentManifest:
    """Parse and validate one JSON document manifest."""
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
        return DocumentManifest.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise DatasetValidationError(f"invalid manifest {path}: {exc}") from exc


def load_evaluation_jsonl(path: Path) -> list[EvaluationItem]:
    """Parse evaluation records and reject malformed or duplicate query IDs."""
    items: list[EvaluationItem] = []
    seen: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise DatasetValidationError(f"cannot read {path}: {exc}") from exc

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            item = EvaluationItem.model_validate_json(line)
        except ValidationError as exc:
            raise DatasetValidationError(f"invalid JSONL item {path}:{line_number}: {exc}") from exc
        if item.query_id in seen:
            raise DatasetValidationError(f"duplicate query_id: {item.query_id}")
        seen.add(item.query_id)
        items.append(item)
    if not items:
        raise DatasetValidationError(f"no evaluation items found in {path}")
    return items


def _question_key(question: str) -> str:
    return " ".join(re.findall(r"\w+", question.casefold()))


def validate_dataset(
    manifest_path: Path, evaluation_paths: Sequence[Path], *, verify_evidence: bool = False
) -> None:
    """Validate provenance, hashes, references, and document-family split isolation."""
    manifest = load_manifest(manifest_path)
    root = manifest_path.parents[2]
    known: dict[tuple[str, str], str] = {}
    evidence: dict[tuple[str, str, str], EvidenceUnit] = {}
    for entry in manifest.documents:
        key = (entry.document_id, entry.document_version)
        if key in known:
            raise DatasetValidationError(f"duplicate manifest document version: {key}")
        fixture = root / entry.local_fixture_path
        if not fixture.is_file():
            raise DatasetValidationError(f"fixture does not exist: {fixture}")
        actual_hash = hashlib.sha256(fixture.read_bytes()).hexdigest()
        if actual_hash != entry.sha256:
            raise DatasetValidationError(f"fixture hash mismatch: {fixture}")
        known[key] = entry.document_id
        if verify_evidence:
            with tempfile.TemporaryDirectory(prefix="evidencerag-eval-") as directory:
                store = LocalArtifactStore(
                    Path(directory),
                    max_upload_bytes=max(fixture.stat().st_size, 1),
                    chunk_bytes=4096,
                )
                document, _ = store.ingest(
                    io.BytesIO(fixture.read_bytes()),
                    original_filename=fixture.name,
                    sanitized_filename=fixture.name,
                )
                for unit in PyMuPDFParser().parse(fixture, document).units:
                    evidence[(entry.document_id, entry.document_version, unit.evidence_id)] = unit

    all_items: list[EvaluationItem] = []
    query_ids: set[str] = set()
    for path in evaluation_paths:
        for item in load_evaluation_jsonl(path):
            if item.query_id in query_ids:
                raise DatasetValidationError(f"duplicate query_id across files: {item.query_id}")
            query_ids.add(item.query_id)
            all_items.append(item)

    split_by_document: dict[str, str] = {}
    seen_questions: list[tuple[str, str]] = []
    for item in all_items:
        question = _question_key(item.question)
        for prior_id, prior_question in seen_questions:
            if (
                question == prior_question
                or SequenceMatcher(None, question, prior_question, autojunk=False).ratio() >= 0.94
            ):
                raise DatasetValidationError(
                    f"near-duplicate questions: {prior_id} and {item.query_id}"
                )
        seen_questions.append((item.query_id, question))
        declared = {(ref.document_id, ref.document_version) for ref in item.documents}
        evidence_refs = {(ref.document_id, ref.document_version) for ref in item.gold_evidence}
        if not evidence_refs.issubset(declared):
            raise DatasetValidationError(
                f"gold evidence outside declared documents: {item.query_id}"
            )
        for key in declared:
            if key not in known:
                raise DatasetValidationError(f"unknown document version {key}: {item.query_id}")
            document_id = known[key]
            prior_split = split_by_document.setdefault(document_id, item.split.value)
            if prior_split != item.split.value:
                raise DatasetValidationError(
                    "document split conflict for "
                    f"{document_id}: {prior_split} vs {item.split.value}"
                )
        if verify_evidence:
            for ref in item.gold_evidence:
                if ref.evidence_id is None:
                    if not item.requires_visual_evidence:
                        raise DatasetValidationError(
                            f"missing evidence ID for nonvisual item: {item.query_id}"
                        )
                    continue
                matched_unit = evidence.get(
                    (ref.document_id, ref.document_version, ref.evidence_id)
                )
                if matched_unit is None:
                    raise DatasetValidationError(f"unknown evidence ID: {item.query_id}")
                if (
                    matched_unit.page_index != ref.page_index
                    or matched_unit.anchor_precision != ref.anchor_precision
                ):
                    raise DatasetValidationError(f"evidence anchor mismatch: {item.query_id}")
                if ref.anchor_precision is AnchorPrecision.REGION and matched_unit.bbox != ref.bbox:
                    raise DatasetValidationError(f"evidence bbox mismatch: {item.query_id}")


def main() -> int:
    """CLI entry point for CI and local validation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("evaluation", type=Path, nargs="+")
    parser.add_argument("--verify-evidence", action="store_true")
    args = parser.parse_args()
    try:
        validate_dataset(args.manifest, args.evaluation, verify_evidence=args.verify_evidence)
    except DatasetValidationError as exc:
        parser.error(str(exc))
    print(f"validated {len(args.evaluation)} evaluation file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
