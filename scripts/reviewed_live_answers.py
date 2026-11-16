"""Run the optional, paid OpenAI evaluation on explicitly authorized reviewed rows."""

import argparse
import hashlib
import json
import logging
import subprocess
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from fastapi.testclient import TestClient

from evidence_rag.api import create_app
from evidence_rag.config import AppSettings
from evidence_rag.eval.models import EvaluationItem, EvaluationSplit, ReviewStatus
from evidence_rag.eval.owner_review import SNAPSHOT, snapshot_jsonl
from evidence_rag.eval.runner import normalized_text_sha256
from evidence_rag.eval.validate import load_evaluation_jsonl, load_manifest, validate_dataset
from evidence_rag.openai_answers import (
    COST_CEILING_USD,
    INSTRUCTIONS,
    LOGGER,
    MAX_OUTPUT_TOKENS,
    MAX_RESPONSE_BYTES,
    MODEL,
    PROMPT_VERSION,
    TIMEOUT_SECONDS,
    OpenAIAnswerGenerator,
    send,
)
from evidence_rag.semantic import LocalDeberta, SemanticVerifier

MANIFEST = Path("datasets/manifests/answer-benchmark.json")


def select_items(items: list[EvaluationItem], ids: list[str]) -> list[EvaluationItem]:
    """Reject accidental selection of frozen, pending, or unsupported inputs."""
    eligible = {
        item.query_id: item
        for item in items
        if item.review_status is ReviewStatus.VERIFIED
        and item.split in {EvaluationSplit.DEVELOPMENT, EvaluationSplit.VALIDATION}
        and len(item.documents) == 1
        and not item.requires_visual_evidence
    }
    if not ids or len(ids) != len(set(ids)) or set(ids) - eligible.keys():
        raise ValueError("select unique owner-verified, single-PDF, nonvisual dev/validation IDs")
    return [eligible[query_id] for query_id in ids]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query-id", action="append", required=True)
    parser.add_argument("--send-selected-excerpts-to-openai", action="store_true")
    parser.add_argument("--max-estimated-usd", type=Decimal, required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path("tmp/hf-model-cache"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cap = len(args.query_id) * Decimal(str(COST_CEILING_USD))
    if not args.send_selected_excerpts_to_openai:
        parser.error("explicit permission to send selected excerpts to OpenAI is required")
    if not args.max_estimated_usd.is_finite() or args.max_estimated_usd < cap:
        parser.error(f"the selected requests require an estimated USD {cap} ceiling")
    if SNAPSHOT.read_text(encoding="utf-8") != snapshot_jsonl():
        parser.error("label snapshot differs from its owner decision ledger")
    validate_dataset(MANIFEST, [SNAPSHOT], verify_evidence=True)
    items = select_items(load_evaluation_jsonl(SNAPSHOT), args.query_id)
    entries = {
        (entry.document_id, entry.document_version): entry
        for entry in load_manifest(MANIFEST).documents
    }
    fixtures = []
    for item in items:
        (ref,) = item.documents
        entry = entries[(ref.document_id, ref.document_version)]
        if (
            not entry.local_fixture_path.startswith("datasets/fixtures/")
            or not entry.source_url.startswith("repo://")
            or entry.redistribution_policy != "May be redistributed under CC0-1.0"
        ):
            parser.error("only the checked-in CC0 fixtures are eligible")
        blob = subprocess.check_output(["git", "show", f"HEAD:{entry.local_fixture_path}"])
        if hashlib.sha256(blob).hexdigest() != entry.sha256:
            parser.error("fixture bytes must match the current commit")
        fixtures.append((entry, blob))
    provenance = {
        "event": "manifest",
        "git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "tracked_changes": bool(
            subprocess.check_output(["git", "diff", "HEAD", "--name-only"], text=True).strip()
        ),
        "dataset_sha256": normalized_text_sha256(SNAPSHOT),
        "manifest_sha256": normalized_text_sha256(MANIFEST),
        "corpus": sorted({entry.sha256 for entry, _ in fixtures}),
        "query_ids": args.query_id,
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": hashlib.sha256(INSTRUCTIONS.encode()).hexdigest(),
        "retriever": "bm25",
        "k": 5,
        "reasoning_effort": "none",
        "temperature": 0,
        "output_token_limit": MAX_OUTPUT_TOKENS,
        "timeout_seconds": TIMEOUT_SECONDS,
        "max_attempts_per_query": 1,
        "estimated_ceiling_usd": str(cap),
    }

    with TemporaryDirectory(prefix="evidencerag-reviewed-live-") as directory:
        settings = AppSettings(
            artifact_root=Path(directory),
            live_answer_provider="openai",
            model_cache_dir=args.cache_dir,
        )
        if not settings.openai_api_key or not settings.openai_api_key.get_secret_value().strip():
            parser.error("inject EVIDENCERAG_OPENAI_API_KEY in the environment")
        verifier = SemanticVerifier(LocalDeberta(settings.model_cache_dir))
        (preflight,) = verifier.assess([("The value is 1.", ("The value is 1.",), False)])
        if preflight.status != "assessed":
            parser.error("prepare the pinned offline verifier before sending a paid request")

        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as output:
            output.write(json.dumps(provenance) + "\n")
            output.flush()
            event_stream = StringIO()
            handler = logging.StreamHandler(event_stream)
            previous_level = LOGGER.level
            LOGGER.setLevel(logging.INFO)
            LOGGER.addHandler(handler)
            requests: list[str] = []
            provider_responses: list[str] = []

            def record_transport(
                key: str, body: bytes, deadline: float, cancelled: Event
            ) -> tuple[int, bytes]:
                # Save the exact evidence-pack request. Authentication is a separate header.
                requests.append(body.decode("utf-8"))
                status, raw = send(key, body, deadline, cancelled)
                if status == 200 and len(raw) <= MAX_RESPONSE_BYTES:
                    provider_responses.append(raw.decode("utf-8", errors="replace"))
                return status, raw

            generator = OpenAIAnswerGenerator(
                settings.openai_api_key.get_secret_value(), record_transport
            )
            try:
                with TestClient(
                    create_app(settings, semantic_verifier=verifier, openai_generator=generator)
                ) as client:
                    for item, (entry, blob) in zip(items, fixtures, strict=True):
                        fixture = Path(entry.local_fixture_path)
                        upload = client.post(
                            "/api/v1/ingestions",
                            files={"file": (fixture.name, blob, "application/pdf")},
                        )
                        upload.raise_for_status()
                        if upload.json()["document_sha256"] != entry.sha256:
                            raise ValueError("ingested version differs from approved fixture")
                        event_stream.seek(0)
                        event_stream.truncate()
                        requests.clear()
                        provider_responses.clear()
                        response = client.post(
                            "/api/v1/query",
                            json={
                                "question": item.question,
                                "document_id": entry.document_id,
                                "document_sha256": entry.sha256,
                                "mode": "bm25",
                                "external_answer_consent": "openai",
                            },
                        )
                        output.write(
                            json.dumps(
                                {
                                    "event": "query",
                                    "query_id": item.query_id,
                                    "http_status": response.status_code,
                                    "pack_requests": [json.loads(record) for record in requests],
                                    "provider_events": [
                                        json.loads(line)
                                        for line in event_stream.getvalue().splitlines()
                                    ],
                                    "raw_provider_responses": provider_responses,
                                    "raw_result": response.json(),
                                }
                            )
                            + "\n"
                        )
                        output.flush()
                        response.raise_for_status()
            finally:
                LOGGER.removeHandler(handler)
                LOGGER.setLevel(previous_level)
                handler.close()


if __name__ == "__main__":
    main()
