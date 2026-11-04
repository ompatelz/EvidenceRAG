"""Run pinned CPU MiniLM E1 against the same provisional E0 evaluation slice."""

import argparse
import hashlib
import json
import os
import platform
import subprocess
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
from typing import Any

from huggingface_hub import snapshot_download
from qdrant_client import QdrantClient

from evidence_rag.eval.corpus import load_canonical_units
from evidence_rag.eval.models import EvaluationItem
from evidence_rag.eval.runner import CUTOFFS, aggregate_rows, development_items, evaluate_queries
from evidence_rag.eval.validate import load_evaluation_jsonl, validate_dataset
from evidence_rag.retrieval.bm25 import RankedEvidence
from evidence_rag.retrieval.dense import (
    INDEX_VERSION,
    MODEL_DIMENSION,
    MODEL_NAME,
    MODEL_REPOSITORY,
    MODEL_REVISION,
    DenseIndex,
    FastEmbedder,
)


def run(
    manifest_path: Path,
    seed_path: Path,
    e0_path: Path,
    output_path: Path,
    *,
    cache_dir: Path,
    download_model: bool = False,
) -> dict[str, Any]:
    """Save raw E1 rankings; refuse E0/E1 evaluation contract drift."""
    validate_dataset(manifest_path, [seed_path], verify_evidence=True)
    items = development_items(load_evaluation_jsonl(seed_path))
    selected = sorted(
        {(ref.document_id, ref.document_version) for item in items for ref in item.documents}
    )
    dataset_hash = hashlib.sha256(seed_path.read_bytes()).hexdigest()
    e0 = json.loads(e0_path.read_text(encoding="utf-8"))
    if (
        e0.get("dataset_sha256") != dataset_hash
        or e0.get("corpus_versions") != [list(pair) for pair in selected]
        or e0.get("config", {}).get("cutoffs") != list(CUTOFFS)
        or e0.get("relevance_unit") != "evidence_unit"
        or [row["query_id"] for row in e0.get("queries", [])] != [item.query_id for item in items]
    ):
        raise ValueError("E0 run is incompatible with the selected E1 dataset and K values")
    cache_dir.mkdir(parents=True, exist_ok=True)
    model_path = snapshot_download(
        repo_id=MODEL_REPOSITORY,
        revision=MODEL_REVISION,
        cache_dir=str(cache_dir),
        local_files_only=not download_model,
        allow_patterns=["*.json", "*.onnx", "vocab.txt"],
    )
    embedder = FastEmbedder(model_path)
    started = perf_counter()
    units, parser_metadata = load_canonical_units(manifest_path, selected)
    corpus_preparation_ms = (perf_counter() - started) * 1000
    client = QdrantClient(":memory:")
    try:
        index = DenseIndex(client, embedder)
        started = perf_counter()
        index.rebuild(units)
        embedding_and_index_ms = (perf_counter() - started) * 1000

        def search(
            item: EvaluationItem, scope: list[tuple[str, str]]
        ) -> tuple[Sequence[RankedEvidence], dict[str, float]]:
            result = index.search(item.question, k=max(CUTOFFS), versions=scope)
            return result.hits, {
                "embedding_ms": result.embedding_ms,
                "vector_search_ms": result.vector_search_ms,
            }

        rows, failures = evaluate_queries(items, search)
        splits = aggregate_rows(rows, "split")
        aggregates = {split: data["metrics"] for split, data in splits.items()}
        source_hash = hashlib.sha256()
        for path in (
            Path(__file__),
            Path(__file__).with_name("corpus.py"),
            Path(__file__).with_name("metrics.py"),
            Path(__file__).with_name("runner.py"),
            Path(__file__).parents[1] / "retrieval/dense.py",
        ):
            source_hash.update(path.read_bytes())
        payload: dict[str, Any] = {
            "experiment": "E1",
            "status": "partial_failure" if failures else "provisional_unreviewed_labels",
            "git_sha_at_run": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip(),
            "source_tree_uncommitted_at_run": bool(
                subprocess.check_output(
                    [
                        "git",
                        "status",
                        "--porcelain",
                        "--",
                        "src/evidence_rag",
                        "pyproject.toml",
                        "uv.lock",
                    ],
                    text=True,
                ).strip()
            ),
            "source_sha256": source_hash.hexdigest(),
            "dataset_sha256": dataset_hash,
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "corpus_versions": selected,
            "index_id": index.index_id,
            "index_version": INDEX_VERSION,
            "parser": parser_metadata,
            "config": {
                "cutoffs": CUTOFFS,
                "batch_size": embedder.batch_size,
                "normalization": "L2",
                "device": "CPU",
                "scope": "exact document/version",
            },
            "model": {
                "name": MODEL_NAME,
                "repository": MODEL_REPOSITORY,
                "revision": MODEL_REVISION,
                "license": "Apache-2.0",
                "dimension": MODEL_DIMENSION,
                "document_encoding": "FastEmbed.embed",
                "query_encoding": "FastEmbed.query_embed",
                "model_file_bytes": (Path(model_path) / "model.onnx").stat().st_size,
            },
            "backend": {
                "qdrant": "local-memory",
                "qdrant_client": version("qdrant-client"),
                "fastembed": version("fastembed"),
                "onnxruntime": version("onnxruntime"),
            },
            "relevance_unit": "evidence_unit",
            "metric_denominator": "answerable nonvisual candidate questions only",
            "counts": {
                "queries": len(rows),
                "scored": sum(row["metrics"] is not None for row in rows),
                "index_units": index.size,
            },
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "processor": platform.processor(),
                "logical_cpus": os.cpu_count(),
                "peak_memory": "not measured",
            },
            "timing": {
                "corpus_preparation_ms": corpus_preparation_ms,
                "embedding_and_index_ms": embedding_and_index_ms,
                "assumption": "single cold process; no warmup; exploratory only",
            },
            "aggregates": aggregates,
            "per_category": aggregate_rows(rows, "category"),
            "failures": failures,
            "seed": None,
            "queries": rows,
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return payload
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("datasets/manifests/fixtures.json"))
    parser.add_argument("--seed", type=Path, default=Path("datasets/eval/phase2_seed.jsonl"))
    parser.add_argument("--e0", type=Path, default=Path("reports/runs/e0-phase2-pilot.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/runs/e1-phase2-pilot.json"))
    parser.add_argument("--cache-dir", type=Path, default=Path("tmp/hf-model-cache"))
    parser.add_argument("--download-model", action="store_true")
    args = parser.parse_args()
    result = run(
        args.manifest,
        args.seed,
        args.e0,
        args.output,
        cache_dir=args.cache_dir,
        download_model=args.download_model,
    )
    print(f"saved E1: {result['counts']} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
