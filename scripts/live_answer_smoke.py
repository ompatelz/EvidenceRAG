"""One explicitly authorized live query over the repository-owned Atlas PDF."""

import argparse
import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from evidence_rag.api import create_app
from evidence_rag.config import AppSettings
from evidence_rag.openai_answers import COST_CEILING_USD, LOGGER, MODEL
from evidence_rag.semantic import LocalDeberta, SemanticVerifier

FIXTURE = Path(__file__).resolve().parents[1] / "datasets/fixtures/atlas-narrative.pdf"
QUESTION = "Which process stage is immediately upstream of Filter in the calibration flow?"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--send-atlas-excerpts-to-openai",
        action="store_true",
        help="Authorize transmission of the smoke question, selected Atlas excerpts, and IDs.",
    )
    parser.add_argument("--output", type=Path, required=True, help="New redacted JSONL run record.")
    args = parser.parse_args()
    if not args.send_atlas_excerpts_to_openai:
        parser.error("explicit consent required: --send-atlas-excerpts-to-openai")

    with TemporaryDirectory(prefix="evidencerag-live-") as root:
        settings = AppSettings(artifact_root=Path(root), live_answer_provider="openai")
        if not settings.openai_api_key or not settings.openai_api_key.get_secret_value().strip():
            parser.error("set EVIDENCERAG_OPENAI_API_KEY in the environment")
        verifier = SemanticVerifier(LocalDeberta(settings.model_cache_dir))
        (preflight,) = verifier.assess([("The value is 1.", ("The value is 1.",), False)])
        if preflight.status != "assessed":
            parser.error("prepare the pinned offline verifier cache before sending a paid request")
        print(
            f"OpenAI {MODEL}. One request, estimated ceiling ${COST_CEILING_USD:.2f}. "
            "Sending the question, selected Atlas PDF text excerpts, and citation identifiers.",
            flush=True,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as record:
            handler = logging.StreamHandler(record)
            previous_level = LOGGER.level
            LOGGER.setLevel(logging.INFO)
            LOGGER.addHandler(handler)
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
                            "question": QUESTION,
                            "document_id": document["document_id"],
                            "document_sha256": document["document_sha256"],
                            "mode": "bm25",
                            "external_answer_consent": "openai",
                        },
                    )
                    response.raise_for_status()
                    result = response.json()["result"]
                    passed = (
                        result["status"] == "answered"
                        and result["answer_source"] == "openai"
                        and "sensor" in result["answer"].casefold()
                        and all(
                            cite["page_index"] == 0
                            and cite["document_id"] == document["document_id"]
                            and cite["document_version"] == f"sha256:{document['document_sha256']}"
                            for claim in result["claims"]
                            for cite in claim["citations"]
                        )
                    )
                    record.write(
                        json.dumps(
                            {
                                "event": "smoke_result",
                                "status": result["status"],
                                "reason": result["reason"],
                                "policy_version": result["policy_version"],
                                "passed": passed,
                            }
                        )
                        + "\n"
                    )
            finally:
                LOGGER.removeHandler(handler)
                LOGGER.setLevel(previous_level)
                handler.close()
        if not passed:
            raise SystemExit(f"Live smoke withheld or unexpected. See {args.output}.")
        print(f"Live smoke passed. Redacted record saved to {args.output}.")


if __name__ == "__main__":
    main()
