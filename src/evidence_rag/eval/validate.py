"""Validate committed evaluation JSONL and document manifests."""

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from evidence_rag.eval.models import DocumentManifest, EvaluationItem


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


def validate_dataset(manifest_path: Path, evaluation_paths: Sequence[Path]) -> None:
    """Validate provenance, hashes, references, and document-family split isolation."""
    manifest = load_manifest(manifest_path)
    root = manifest_path.parents[2]
    known: dict[tuple[str, str], str] = {}
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

    all_items: list[EvaluationItem] = []
    query_ids: set[str] = set()
    for path in evaluation_paths:
        for item in load_evaluation_jsonl(path):
            if item.query_id in query_ids:
                raise DatasetValidationError(f"duplicate query_id across files: {item.query_id}")
            query_ids.add(item.query_id)
            all_items.append(item)

    split_by_document: dict[str, str] = {}
    for item in all_items:
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


def main() -> int:
    """CLI entry point for CI and local validation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("evaluation", type=Path, nargs="+")
    args = parser.parse_args()
    try:
        validate_dataset(args.manifest, args.evaluation)
    except DatasetValidationError as exc:
        parser.error(str(exc))
    print(f"validated {len(args.evaluation)} evaluation file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
