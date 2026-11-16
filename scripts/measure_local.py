"""Measure the owned Atlas PDF through the local API and cite the served preview."""

import argparse
import json
import os
import platform
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter, process_time

from fastapi.testclient import TestClient

from evidence_rag.answers import FixtureDemoGenerator
from evidence_rag.api import create_app
from evidence_rag.config import AppSettings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--cpu", default=os.environ.get("PROCESSOR_IDENTIFIER") or platform.processor()
    )
    args = parser.parse_args()
    with TemporaryDirectory() as temp:
        root = Path(temp)
        settings = AppSettings(artifact_root=root, demo_answers=True)
        with TestClient(create_app(settings)) as client:
            assert client.get("/ready").status_code == 200
            started, cpu_started = perf_counter(), process_time()
            with Path("datasets/fixtures/atlas-narrative.pdf").open("rb") as pdf:
                ingested = client.post("/api/v1/ingestions", files={"file": pdf})
            ingest_wall_ms = (perf_counter() - started) * 1000
            ingested.raise_for_status()
            document = ingested.json()
            assert document["state"] == "ready"
            query = {key: document[key] for key in ("document_id", "document_sha256")}
            attempts = []
            for question in (
                FixtureDemoGenerator.QUESTION,
                "What is the calibration sampling rate on Neptune?",
            ):
                started = perf_counter()
                response = client.post("/api/v1/query", json={**query, "question": question})
                wall_ms = (perf_counter() - started) * 1000
                response.raise_for_status()
                body = response.json()
                attempts.append({"wall_ms": wall_ms, **body})
            assert attempts[0]["result"]["status"] == "answered"
            assert attempts[1]["result"]["status"] == "insufficient_evidence"
            citation = attempts[0]["result"]["claims"][0]["citations"][0]
            base = f"/api/v1/documents/{query['document_id']}/versions/{query['document_sha256']}"
            anchor = client.get(f"{base}/evidence/{citation['evidence_id']}/anchor")
            anchor.raise_for_status()
            assert anchor.json()["preview_asset_id"] == citation["preview_asset_id"]
            preview = client.get(f"{base}/pages/{citation['page_index']}/preview")
            preview.raise_for_status()
            assert preview.content.startswith(b"\x89PNG")
            args.output.write_text(
                json.dumps(
                    {
                        "platform": platform.platform(),
                        "cpu": args.cpu,
                        "logical_cpus": os.cpu_count(),
                        "concurrency": 1,
                        "cache": "fresh application and artifact store; OS file cache uncontrolled",
                        "transport": "in-process ASGI requests",
                        "ingest_wall_ms": ingest_wall_ms,
                        "cpu_ms": (process_time() - cpu_started) * 1000,
                        "ingestion": document,
                        "queries": attempts,
                        "preview_bytes": len(preview.content),
                        "artifact_bytes": sum(
                            path.stat().st_size for path in root.rglob("*") if path.is_file()
                        ),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )


if __name__ == "__main__":
    main()
