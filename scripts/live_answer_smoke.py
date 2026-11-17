"""One explicitly authorized live query over the repository-owned Atlas PDF."""

import argparse
import json
import logging
import re
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from fastapi.testclient import TestClient

from evidence_rag.api import create_app
from evidence_rag.config import AppSettings
from evidence_rag.openai_answers import COST_CEILING_USD, MODEL
from evidence_rag.semantic import LocalDeberta, SemanticVerifier

FIXTURE = Path(__file__).resolve().parents[1] / "datasets/fixtures/atlas-narrative.pdf"
FIXTURE_SHA256 = "b6a8b1d7f3fda491b08adf9aeb1bc40d1b073804ab63045e3cf090ff1dff4aaa"
QUESTION = "Which process stage is immediately upstream of Filter in the calibration flow?"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    consent = parser.add_mutually_exclusive_group(required=True)
    consent.add_argument(
        "--send-atlas-excerpts-to-openai",
        action="store_true",
        help="Authorize transmission of the smoke question, selected Atlas excerpts, and IDs.",
    )
    consent.add_argument("--send-atlas-excerpts-via-codex", action="store_true")
    consent.add_argument("--send-atlas-excerpts-to-openrouter", action="store_true")
    parser.add_argument("--output", type=Path, required=True, help="New redacted JSONL run record.")
    args = parser.parse_args()
    provider: Literal["openai", "openrouter", "codex"] = (
        "codex"
        if args.send_atlas_excerpts_via_codex
        else "openrouter"
        if args.send_atlas_excerpts_to_openrouter
        else "openai"
    )
    logger = logging.getLogger(f"evidence_rag.{provider}")
    question = (
        QUESTION
        if provider == "openai"
        else "What sampling frequency does the Atlas note specify for calibration?"
    )

    if sha256(FIXTURE.read_bytes()).hexdigest() != FIXTURE_SHA256:
        parser.error("the owned Atlas fixture does not match its committed hash")

    with TemporaryDirectory(prefix="evidencerag-live-") as root:
        settings = AppSettings(artifact_root=Path(root), live_answer_provider=provider)
        if provider == "openai" and not settings.openai_api_key:
            parser.error("set EVIDENCERAG_OPENAI_API_KEY in the environment")
        if provider == "openrouter" and not (
            settings.openrouter_api_key and settings.openrouter_model
        ):
            parser.error("set EVIDENCERAG_OPENROUTER_API_KEY and EVIDENCERAG_OPENROUTER_MODEL")
        verifier = SemanticVerifier(LocalDeberta(settings.model_cache_dir))
        (preflight,) = verifier.assess([("The value is 1.", ("The value is 1.",), False)])
        if preflight.status != "assessed":
            parser.error("prepare the pinned offline verifier cache before sending a live request")
        if provider == "openai":
            print(f"OpenAI {MODEL}. Estimated ceiling ${COST_CEILING_USD:.2f}.")
        print(
            f"{provider}: one question. "
            "Sending the question, selected Atlas PDF text excerpts, and citation identifiers.",
            flush=True,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as record:
            handler = logging.StreamHandler(record)
            previous_level = logger.level
            logger.setLevel(logging.INFO)
            logger.addHandler(handler)
            try:
                with TestClient(create_app(settings, semantic_verifier=verifier)) as client:
                    with FIXTURE.open("rb") as pdf:
                        upload = client.post(
                            "/api/v1/ingestions",
                            files={"file": (FIXTURE.name, pdf, "application/pdf")},
                        )
                    upload.raise_for_status()
                    document = upload.json()
                    response = client.post(
                        "/api/v1/query",
                        json={
                            "question": question,
                            "document_id": document["document_id"],
                            "document_sha256": document["document_sha256"],
                            "mode": "bm25",
                            "external_answer_consent": provider,
                        },
                    )
                    response.raise_for_status()
                    result = response.json()["result"]
                    passed = (
                        result["status"] == "answered"
                        and result["answer_source"] == provider
                        and (
                            ("sensor" in result["answer"].casefold())
                            if provider == "openai"
                            else (bool(re.search(r"\b20\s*(?:hertz|hz)\b", result["answer"], re.I)))
                        )
                        and bool(result["claims"])
                        and all(
                            cite["page_index"] == 0
                            and cite["document_id"] == document["document_id"]
                            and cite["document_version"] == f"sha256:{document['document_sha256']}"
                            for claim in result["claims"]
                            for cite in claim["citations"]
                        )
                    )
                    if passed:
                        for claim in result["claims"]:
                            for cite in claim["citations"]:
                                base = (
                                    f"/api/v1/documents/{cite['document_id']}/versions/"
                                    f"{document['document_sha256']}"
                                )
                                anchor = client.get(f"{base}/evidence/{cite['evidence_id']}/anchor")
                                preview = client.get(f"{base}/pages/{cite['page_index']}/preview")
                                passed = (
                                    passed
                                    and anchor.status_code == 200
                                    and preview.content.startswith(b"\x89PNG")
                                )
                    record.write(
                        json.dumps(
                            {
                                "event": "smoke_result",
                                "provider": provider,
                                "status": result["status"],
                                "reason": result["reason"],
                                "policy_version": result["policy_version"],
                                "fixture_sha256": document["document_sha256"],
                                "passed": passed,
                            }
                        )
                        + "\n"
                    )
            finally:
                logger.removeHandler(handler)
                logger.setLevel(previous_level)
                handler.close()
        if not passed:
            raise SystemExit(f"Live smoke withheld or unexpected. See {args.output}.")
        print(f"Live smoke passed. Redacted record saved to {args.output}.")


if __name__ == "__main__":
    main()
