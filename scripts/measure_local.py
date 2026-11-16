"""Measure the owned Atlas PDF through the local API and cite the served preview."""

import argparse
import json
import os
import platform
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter, process_time

from fastapi.testclient import TestClient
from httpx2 import Client

from evidence_rag.answers import FixtureDemoGenerator
from evidence_rag.api import create_app
from evidence_rag.config import AppSettings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--cpu", default=os.environ.get("PROCESSOR_IDENTIFIER") or platform.processor()
    )
    parser.add_argument("--base-url", help="URL of a running fixture-enabled local instance")
    args = parser.parse_args()
    if args.base_url:
        with Client(base_url=args.base_url, timeout=10, trust_env=False) as client:
            report = run_demo(client)
        report.update(transport="HTTP", cache="server and OS cache uncontrolled")
        write_report(args.output, args.cpu, report)
        return
    with TemporaryDirectory() as temp:
        root = Path(temp)
        settings = AppSettings(artifact_root=root, demo_answers=True)
        with TestClient(create_app(settings)) as client:
            cpu_started = process_time()
            report = run_demo(client)
            cpu_ms = (process_time() - cpu_started) * 1000
        report.update(
            cache="fresh application and artifact store; OS file cache uncontrolled",
            transport="in-process ASGI requests",
            cpu_ms=cpu_ms,
            artifact_bytes=sum(path.stat().st_size for path in root.rglob("*") if path.is_file()),
        )
    write_report(args.output, args.cpu, report)


def write_report(output: Path, cpu: str, report: dict[str, object]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "platform": platform.platform(),
                "cpu": cpu,
                "logical_cpus": os.cpu_count(),
                "concurrency": 1,
                **report,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def run_demo(client: Client) -> dict[str, object]:
    for route in ("/health", "/ready", "/inspector", "/inspector/app.css", "/inspector/app.js"):
        client.get(route).raise_for_status()
    assert client.get("/api/v1/capabilities").json()["fixture_demo_answers"] is True
    started = perf_counter()
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
    assert "20 hertz" in attempts[0]["result"]["answer"]
    assert attempts[1]["result"]["status"] == "insufficient_evidence"
    assert attempts[1]["result"]["reason"] == "unsupported_question"
    citation = attempts[0]["result"]["claims"][0]["citations"][0]
    base = f"/api/v1/documents/{query['document_id']}/versions/{query['document_sha256']}"
    anchor = client.get(f"{base}/evidence/{citation['evidence_id']}/anchor")
    anchor.raise_for_status()
    source = anchor.json()
    assert source["preview_asset_id"] == citation["preview_asset_id"]
    assert source["page_index"] == citation["page_index"]
    assert source["precision"] == "region"
    assert source["display_bbox"] is not None
    preview = client.get(f"{base}/pages/{citation['page_index']}/preview")
    preview.raise_for_status()
    assert preview.content.startswith(b"\x89PNG")
    return {
        "ingest_wall_ms": ingest_wall_ms,
        "ingestion": document,
        "queries": attempts,
        "citation_anchor": source,
        "preview_bytes": len(preview.content),
    }


if __name__ == "__main__":
    main()
