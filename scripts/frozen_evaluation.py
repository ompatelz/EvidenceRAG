"""Record and execute the one-shot local held-out retrieval and abstention check."""

import argparse
import hashlib
import json
import os
import platform
import subprocess
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any

from fastapi.testclient import TestClient

from evidence_rag.api import QueryResponse, create_app
from evidence_rag.config import AppSettings
from evidence_rag.eval.metrics import score_ranking
from evidence_rag.eval.models import EvaluationItem, EvaluationSplit
from evidence_rag.eval.runner import CUTOFFS
from evidence_rag.eval.validate import load_evaluation_jsonl, load_manifest

SEED = Path("datasets/eval/phase2_seed.jsonl")
MANIFEST = Path("datasets/manifests/fixtures.json")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, timeout=10).strip()


def freeze() -> dict[str, Any]:
    """Hash inputs without parsing or exposing evaluation labels."""
    if git("status", "--porcelain"):
        raise ValueError("record and execute the freeze from a clean worktree")
    fixtures = load_manifest(MANIFEST)
    paths = [Path("uv.lock"), MANIFEST, *(Path(d.local_fixture_path) for d in fixtures.documents)]
    return {
        "git_commit": git("rev-parse", "HEAD"),
        "sha256": {
            **{p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            SEED.as_posix(): hashlib.sha256(SEED.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        },
        "config": {
            "split": EvaluationSplit.FROZEN_TEST.value,
            "mode": "bm25",
            "k": list(CUTOFFS),
            "relevance": "exact canonical evidence unit within the selected version",
            "visual": "flagged by label; record explicit refusal; exclude from retrieval metrics",
            "labels": "report review status; unreviewed label metrics are provisional",
            "generator": "disabled; no answer correctness or citation support score",
            "models_prompts_thresholds": "none used; optional semantic verification is disabled",
            "concurrency": 1,
            "cache": "fresh application and artifact store; OS file cache uncontrolled",
            "transport": "in-process ASGI; stage and request wall time",
        },
        "host": {
            "platform": platform.platform(),
            "processor": os.environ.get("PROCESSOR_IDENTIFIER") or platform.processor(),
            "logical_cpus": os.cpu_count(),
            "python": platform.python_version(),
        },
    }


def diagnostic(item: EvaluationItem, response: QueryResponse) -> dict[str, Any] | None:
    if not item.answerable or item.requires_visual_evidence:
        return None
    ranked = [str(hit["evidence_id"]) for hit in response.retrieval]
    expected = {ref.evidence_id for ref in item.gold_evidence if ref.evidence_id}
    return {str(k): asdict(score_ranking(ranked, expected, k=k)) for k in CUTOFFS}


def execute() -> list[dict[str, Any]]:
    items = [i for i in load_evaluation_jsonl(SEED) if i.split is EvaluationSplit.FROZEN_TEST]
    if not items:
        raise ValueError("no frozen-test items")
    corpus = {
        (doc.document_id, doc.document_version): doc for doc in load_manifest(MANIFEST).documents
    }
    with (
        TemporaryDirectory() as root,
        TestClient(
            create_app(
                AppSettings(
                    artifact_root=Path(root),
                    demo_answers=False,
                    semantic_verifier=False,
                    abstention_policy="off",
                )
            )
        ) as client,
    ):
        rows: list[dict[str, Any]] = []
        ingested: set[tuple[str, str]] = set()
        for item in items:
            row: dict[str, Any] = {
                "query_id": item.query_id,
                "category": item.category,
                "review_status": item.review_status.value,
                "answerable": item.answerable,
                "requires_visual_evidence": item.requires_visual_evidence,
            }
            try:
                if len(item.documents) != 1:
                    raise ValueError("the serving API supports one version per query")
                ref = item.documents[0]
                identity = (ref.document_id, ref.document_version)
                entry = corpus[identity]
                if identity not in ingested:
                    path = Path(entry.local_fixture_path)
                    with path.open("rb") as source:
                        result = client.post("/api/v1/ingestions", files={"file": source})
                    result.raise_for_status()
                    info = result.json()
                    if (info["document_id"], info["document_version"], info["state"]) != (
                        *identity,
                        "ready",
                    ):
                        raise ValueError("ingestion did not publish the expected ready version")
                    row["ingestion"] = info
                    ingested.add(identity)
                started = perf_counter()
                result = client.post(
                    "/api/v1/query",
                    json={
                        "question": item.question,
                        "document_id": ref.document_id,
                        "document_sha256": entry.sha256,
                        "mode": "bm25",
                        "requires_visual_evidence": item.requires_visual_evidence,
                    },
                )
                row["request_wall_ms"] = (perf_counter() - started) * 1000
                result.raise_for_status()
                response = QueryResponse.model_validate(result.json())
                row["response"] = response.model_dump(mode="json")
                row["candidate_label_metrics"] = diagnostic(item, response)
            except Exception as exc:
                row["failure"] = type(exc).__name__
            rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("--record", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    current = freeze()
    if args.action == "freeze":
        with args.record.open("x", encoding="utf-8") as record:
            json.dump(current, record, indent=2)
        return
    if args.output is None or json.loads(args.record.read_text(encoding="utf-8")) != current:
        parser.error("run requires a matching freeze record and a fresh output path")
    with args.output.open("x", encoding="utf-8") as output:
        payload: dict[str, Any] = {"freeze": current, "status": "started", "rows": []}
        json.dump(payload, output, indent=2)
        output.flush()
        try:
            rows = execute()
            payload["rows"] = rows
            payload["status"] = "completed"
            if any(row.get("failure") for row in rows):
                payload["status"] = "partial_failure"
        except Exception as exc:
            payload.update(status="failed", failure=type(exc).__name__)
            raise
        finally:
            output.seek(0)
            json.dump(payload, output, indent=2)
            output.truncate()
    if payload["status"] != "completed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
