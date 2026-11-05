"""Evaluate versioned RRF on the same development/validation corpus as E0 and E1."""

import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path
from time import perf_counter
from typing import Any

from huggingface_hub import snapshot_download
from qdrant_client import QdrantClient

from evidence_rag.eval.corpus import load_canonical_units
from evidence_rag.eval.runner import (
    CUTOFFS,
    aggregate_rows,
    development_items,
    evaluate_queries,
    normalized_text_sha256,
)
from evidence_rag.eval.validate import load_evaluation_jsonl, validate_dataset
from evidence_rag.retrieval.bm25 import BM25Index
from evidence_rag.retrieval.dense import MODEL_REPOSITORY, MODEL_REVISION, DenseIndex, FastEmbedder
from evidence_rag.retrieval.hybrid import FUSION_VERSION, HybridConfig, HybridRetriever


def run(
    manifest_path: Path,
    seed_path: Path,
    e0_path: Path,
    e1_path: Path,
    output_path: Path,
    *,
    cache_dir: Path,
    configurations: tuple[HybridConfig, ...],
) -> dict[str, Any]:
    """Save all trials and choose one configuration using validation only."""
    validate_dataset(manifest_path, [seed_path], verify_evidence=True)
    items = development_items(load_evaluation_jsonl(seed_path))
    selected = sorted(
        {(ref.document_id, ref.document_version) for item in items for ref in item.documents}
    )
    dataset_hash = normalized_text_sha256(seed_path)
    baselines = [json.loads(path.read_text(encoding="utf-8")) for path in (e0_path, e1_path)]
    for baseline in baselines:
        if (
            baseline.get("dataset_sha256") != dataset_hash
            or baseline.get("corpus_versions") != [list(pair) for pair in selected]
            or baseline.get("config", {}).get("cutoffs") != list(CUTOFFS)
            or baseline.get("relevance_unit") != "evidence_unit"
            or [row["query_id"] for row in baseline.get("queries", [])]
            != [item.query_id for item in items]
        ):
            raise ValueError("baseline is incompatible with hybrid evaluation")
    model_path = snapshot_download(
        repo_id=MODEL_REPOSITORY,
        revision=MODEL_REVISION,
        cache_dir=str(cache_dir),
        local_files_only=True,
        allow_patterns=["*.json", "*.onnx", "vocab.txt"],
    )
    started = perf_counter()
    units, parser = load_canonical_units(manifest_path, selected)
    preparation_ms = (perf_counter() - started) * 1000
    bm25 = BM25Index()
    bm25.rebuild(units)
    client = QdrantClient(":memory:")
    try:
        dense = DenseIndex(client, FastEmbedder(model_path))
        dense.rebuild(units)
        trials: list[dict[str, Any]] = []
        for config in configurations:
            retriever = HybridRetriever(bm25, dense, config)

            def search(
                item: Any, scope: list[tuple[str, str]], _retriever: HybridRetriever = retriever
            ) -> tuple[Any, dict[str, float]]:
                result = _retriever.search(item.question, versions=scope)
                return result.hits, {
                    "bm25_ms": result.bm25_ms,
                    "embedding_ms": result.embedding_ms,
                    "vector_search_ms": result.vector_search_ms,
                    "fusion_ms": result.fusion_ms,
                    "total_ms": result.bm25_ms
                    + result.embedding_ms
                    + result.vector_search_ms
                    + result.fusion_ms,
                }

            rows, failures = evaluate_queries(items, search)
            trials.append(
                {
                    "config": {
                        "rrf_k": config.rrf_k,
                        "prefetch": config.prefetch,
                        "final_k": config.final_k,
                    },
                    "aggregates": aggregate_rows(rows, "split"),
                    "per_category": aggregate_rows(rows, "category"),
                    "failures": failures,
                    "queries": rows,
                }
            )
        if not trials:
            raise ValueError("at least one configuration is required")

        # Choose by validation nDCG@5, then MRR@5; deterministic first-listed tie.
        def quality(trial: dict[str, Any]) -> tuple[float, float]:
            metrics = trial["aggregates"]["validation"]["metrics"]["5"]
            if metrics is None:
                raise ValueError("validation contains no scored questions")
            return metrics["ndcg"], metrics["mrr"]

        eligible = [trial for trial in trials if not trial["failures"]]
        if not eligible:
            raise ValueError("every hybrid trial failed")
        selected_trial = max(eligible, key=quality)
        source_hash = hashlib.sha256()
        for path in (
            Path(__file__),
            Path(__file__).with_name("runner.py"),
            Path(__file__).with_name("metrics.py"),
            Path(__file__).with_name("corpus.py"),
            Path(__file__).parents[1] / "retrieval/hybrid.py",
        ):
            source_hash.update(path.read_bytes())
        payload: dict[str, Any] = {
            "experiment": "E2",
            "status": "provisional_unreviewed_labels",
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
            "relevance_unit": "evidence_unit",
            "metric_denominator": "answerable nonvisual candidate questions only",
            "fusion_version": FUSION_VERSION,
            "bm25_index_id": bm25.index_id,
            "dense_index_id": dense.index_id,
            "model_revision": MODEL_REVISION,
            "parser": parser,
            "cutoffs": CUTOFFS,
            "counts": {
                "queries": len(items),
                "scored": sum(row["metrics"] is not None for row in selected_trial["queries"]),
                "index_units": len(units),
            },
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "processor": platform.processor(),
                "logical_cpus": os.cpu_count(),
            },
            "timing": {
                "corpus_preparation_ms": preparation_ms,
                "assumption": "single cold process; no warmup; exploratory only",
            },
            "selection": {
                "criterion": "validation nDCG@5, then MRR@5; first-listed tie",
                "selected_config": selected_trial["config"],
            },
            "trials": trials,
            "baseline_artifacts": [str(e0_path), str(e1_path)],
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return payload
    finally:
        client.close()
