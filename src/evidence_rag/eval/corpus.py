"""Build both retrieval baselines from identical persisted canonical evidence."""

import io
import tempfile
from collections.abc import Sequence
from pathlib import Path

from evidence_rag.documents.models import EvidenceArtifact
from evidence_rag.documents.parser import PyMuPDFParser
from evidence_rag.documents.storage import LocalArtifactStore
from evidence_rag.eval.validate import load_manifest
from evidence_rag.evidence import EvidenceUnit


def load_canonical_units(
    manifest_path: Path, selected: Sequence[tuple[str, str]]
) -> tuple[list[EvidenceUnit], dict[str, str]]:
    """Parse, persist, and reload only selected immutable document versions."""
    manifest = load_manifest(manifest_path)
    entries = [
        entry
        for entry in manifest.documents
        if (entry.document_id, entry.document_version) in selected
    ]
    if len(entries) != len(set(selected)):
        raise ValueError("selected document version missing from manifest")
    parser = PyMuPDFParser()
    with tempfile.TemporaryDirectory(prefix="evidencerag-corpus-") as directory:
        store = LocalArtifactStore(
            Path(directory), max_upload_bytes=64 * 1024 * 1024, chunk_bytes=64 * 1024
        )
        for entry in entries:
            source = Path(entry.local_fixture_path)
            document, _ = store.ingest(
                io.BytesIO(source.read_bytes()),
                original_filename=source.name,
                sanitized_filename=source.name,
            )
            if (document.document_id, document.document_version) != (
                entry.document_id,
                entry.document_version,
            ):
                raise ValueError("manifest identity does not match ingestion identity")
            parsed = parser.parse(source, document)
            store.write_evidence(
                EvidenceArtifact(
                    document_id=document.document_id,
                    document_version=document.document_version,
                    document_sha256=document.document_sha256,
                    parser=parser.metadata,
                    page_count=parsed.page_count,
                    units=list(parsed.units),
                    issues=list(parsed.issues),
                )
            )
        units = [
            unit
            for document_id, document_version in sorted(selected)
            for unit in store.get_evidence(document_id, document_version[7:]).units
        ]
    return units, parser.metadata.model_dump()
