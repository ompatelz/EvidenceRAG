"""Compare optional CPU reranking with saved hybrid candidates, without frozen test."""

import argparse
import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Any

from huggingface_hub import snapshot_download

from evidence_rag.eval.corpus import load_canonical_units
from evidence_rag.eval.models import EvaluationItem
from evidence_rag.eval.runner import (
    CUTOFFS,
    aggregate_rows,
    development_items,
    evaluate_queries,
    normalized_text_sha256,
)
from evidence_rag.eval.validate import load_evaluation_jsonl, validate_dataset
from evidence_rag.retrieval.hybrid import HybridHit
from evidence_rag.retrieval.rerank import (
    MODEL_NAME,
    MODEL_REVISION,
    RERANK_VERSION,
    FastEmbedCrossEncoder,
    OptionalReranker,
    RerankConfig,
)


def run(
    manifest_path: Path,
    seed_path: Path,
    hybrid_path: Path,
    output_path: Path,
    *,
    cache_dir: Path,
    config: RerankConfig,
) -> dict[str, Any]:
    if not config.enabled:
        raise ValueError("real-model evaluation requires enabled reranking")
    validate_dataset(manifest_path, [seed_path], verify_evidence=True)
    items = development_items(load_evaluation_jsonl(seed_path))
    hybrid = json.loads(hybrid_path.read_text(encoding="utf-8"))
    selected = sorted(
        {(ref.document_id, ref.document_version) for item in items for ref in item.documents}
    )
    if (
        hybrid.get("dataset_sha256") != normalized_text_sha256(seed_path)
        or hybrid.get("corpus_versions") != [list(pair) for pair in selected]
        or hybrid.get("relevance_unit") != "evidence_unit"
        or tuple(hybrid.get("cutoffs", ())) != CUTOFFS
        or hybrid.get("model_revision") != "d13954661f83248295ba75c1ed411eef3b7b936e"
    ):
        raise ValueError("hybrid artifact does not match this evaluation contract")
    selected_config = hybrid["selection"]["selected_config"]
    trial = next((t for t in hybrid["trials"] if t["config"] == selected_config), None)
    if trial is None or trial["failures"]:
        raise ValueError("selected hybrid trial is missing or failed")
    baseline_rows = {row["query_id"]: row for row in trial["queries"]}
    if list(baseline_rows) != [item.query_id for item in items]:
        raise ValueError("hybrid query order differs from the evaluation seed")
    units, parser = load_canonical_units(manifest_path, selected)
    unit_map = {unit.evidence_id: unit for unit in units}
    model_path = snapshot_download(
        repo_id=MODEL_NAME,
        revision=MODEL_REVISION,
        cache_dir=str(cache_dir),
        local_files_only=True,
        allow_patterns=[
            "config.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "vocab.txt",
            "onnx/model.onnx",
        ],
    )
    scorer = FastEmbedCrossEncoder(model_path, max_tokens=config.max_pair_tokens)
    reranker = OptionalReranker(scorer, config)
    try:

        def search(
            item: EvaluationItem, scope: list[tuple[str, str]]
        ) -> tuple[Any, dict[str, float | str]]:
            baseline = baseline_rows[item.query_id]
            if baseline["failure"]:
                raise ValueError("saved hybrid query failed")
            hits = tuple(HybridHit(**hit) for hit in baseline["ranking"])
            result = reranker.rerank(item.question, hits, unit_map, versions=scope)
            retrieval_ms = float(baseline["total_ms"])
            return result.hits, {
                "retrieval_ms": retrieval_ms,
                "rerank_ms": result.rerank_ms,
                "total_ms": retrieval_ms + result.rerank_ms,
                "rerank_status": result.status,
            }

        rows, failures = evaluate_queries(items, search)
    finally:
        reranker.close()
    source_hash = hashlib.sha256()
    for path in (
        Path(__file__),
        Path(__file__).with_name("runner.py"),
        Path(__file__).parents[1] / "retrieval/rerank.py",
    ):
        source_hash.update(path.read_bytes())
    payload: dict[str, Any] = {
        "experiment": "E3",
        "status": "partial_failure" if failures else "provisional_unreviewed_labels",
        "git_sha_at_run": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
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
        "dataset_sha256": normalized_text_sha256(seed_path),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "corpus_versions": selected,
        "relevance_unit": "evidence_unit",
        "cutoffs": CUTOFFS,
        "model": {
            "name": MODEL_NAME,
            "revision": MODEL_REVISION,
            "license": "Apache-2.0",
            "backend": "FastEmbed 0.9.1 ONNX CPU",
            "onnx_bytes": (Path(model_path) / "onnx/model.onnx").stat().st_size,
        },
        "rerank_version": RERANK_VERSION,
        "config": {
            "top_n": config.top_n,
            "batch_size": config.batch_size,
            "timeout_ms": config.timeout_ms,
            "max_query_chars": config.max_query_chars,
            "max_passage_chars": config.max_passage_chars,
            "max_pair_tokens": config.max_pair_tokens,
        },
        "hybrid_source": str(hybrid_path),
        "hybrid_config": selected_config,
        "parser": parser,
        "counts": {
            "queries": len(rows),
            "scored": sum(row["metrics"] is not None for row in rows),
            "index_units": len(units),
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "logical_cpus": os.cpu_count(),
        },
        "timing": {
            "assumption": (
                "hybrid retrieval times reused from saved E2 run; "
                "reranking measured separately in this cold process"
            )
        },
        "aggregates": aggregate_rows(rows, "split"),
        "per_category": aggregate_rows(rows, "category"),
        "failures": failures,
        "queries": rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("datasets/manifests/fixtures.json"))
    parser.add_argument("--seed", type=Path, default=Path("datasets/eval/phase2_seed.jsonl"))
    parser.add_argument(
        "--hybrid", type=Path, default=Path("reports/runs/e2-hybrid-validation.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("reports/runs/e3-rerank-validation.json")
    )
    parser.add_argument("--cache-dir", type=Path, default=Path("tmp/hf-model-cache"))
    args = parser.parse_args()
    result = run(
        args.manifest,
        args.seed,
        args.hybrid,
        args.output,
        cache_dir=args.cache_dir,
        config=RerankConfig(enabled=True),
    )
    print(f"saved E3: {result['counts']} to {args.output}")
    return 2 if result["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
