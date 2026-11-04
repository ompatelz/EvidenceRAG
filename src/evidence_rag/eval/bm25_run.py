"""Run provisional E0 on development and validation candidate labels only."""

import argparse
import hashlib
import json
import platform
import subprocess
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from evidence_rag.eval.corpus import load_canonical_units
from evidence_rag.eval.metrics import mean_metrics, score_ranking
from evidence_rag.eval.models import EvaluationSplit
from evidence_rag.eval.validate import load_evaluation_jsonl, validate_dataset
from evidence_rag.retrieval.bm25 import INDEX_VERSION, TOKENIZER_VERSION, BM25Index


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def run(manifest_path: Path, seed_path: Path, output_path: Path) -> dict[str, object]:
    """Reparse selected PDFs, persist evidence, then benchmark the same units."""
    validate_dataset(manifest_path, [seed_path], verify_evidence=True)
    items = [
        item
        for item in load_evaluation_jsonl(seed_path)
        if item.split in {EvaluationSplit.DEVELOPMENT, EvaluationSplit.VALIDATION}
    ]
    if not items:
        raise ValueError("no development or validation items")
    selected = {(ref.document_id, ref.document_version) for item in items for ref in item.documents}
    index = BM25Index()
    started = perf_counter()
    units, parser_metadata = load_canonical_units(manifest_path, sorted(selected))
    preparation_ms = (perf_counter() - started) * 1000
    index_started = perf_counter()
    index.rebuild(units)
    index_ms = (perf_counter() - index_started) * 1000

    cutoffs = (1, 3, 5)
    rows: list[dict[str, object]] = []
    for item in items:
        scope = sorted((ref.document_id, ref.document_version) for ref in item.documents)
        result = index.search(item.question, k=max(cutoffs), versions=scope)
        ranked_ids = [hit.evidence_id for hit in result.hits]
        gold_ids = {ref.evidence_id for ref in item.gold_evidence if ref.evidence_id}
        metrics = (
            {str(k): asdict(score_ranking(ranked_ids, gold_ids, k=k)) for k in cutoffs}
            if item.answerable and not item.requires_visual_evidence
            else None
        )
        rows.append(
            {
                "query_id": item.query_id,
                "split": item.split.value,
                "category": item.category,
                "review_status": item.review_status.value,
                "answerable": item.answerable,
                "requires_visual_evidence": item.requires_visual_evidence,
                "scope": scope,
                "gold_evidence_ids": sorted(gold_ids),
                "ranking": [asdict(hit) for hit in result.hits],
                "search_ms": result.search_ms,
                "metrics": metrics,
            }
        )
    aggregates: dict[str, dict[str, dict[str, float]]] = {}
    for split in (EvaluationSplit.DEVELOPMENT, EvaluationSplit.VALIDATION):
        split_rows = [row for row in rows if row["split"] == split.value and row["metrics"]]
        aggregates[split.value] = {}
        for k in cutoffs:
            from evidence_rag.eval.metrics import RetrievalMetrics

            scores = [
                RetrievalMetrics(**row["metrics"][str(k)])  # type: ignore[index]
                for row in split_rows
            ]
            aggregates[split.value][str(k)] = asdict(mean_metrics(scores)) if scores else {}

    source_hash = hashlib.sha256()
    for path in (
        Path(__file__),
        Path(__file__).with_name("metrics.py"),
        Path(__file__).with_name("corpus.py"),
        Path(__file__).parents[1] / "retrieval/bm25.py",
    ):
        source_hash.update(path.read_bytes())
    payload: dict[str, object] = {
        "experiment": "E0",
        "status": "provisional_unreviewed_labels",
        "git_sha_at_run": _git("rev-parse", "HEAD"),
        "source_tree_uncommitted_at_run": bool(_git("status", "--porcelain")),
        "source_sha256": source_hash.hexdigest(),
        "dataset_sha256": hashlib.sha256(seed_path.read_bytes()).hexdigest(),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "corpus_versions": sorted(selected),
        "index_id": index.index_id,
        "index_version": INDEX_VERSION,
        "tokenizer_version": TOKENIZER_VERSION,
        "parser": parser_metadata,
        "config": {
            "k1": index.k1,
            "b": index.b,
            "cutoffs": cutoffs,
            "stopwords": "none",
            "scope": "exact document/version",
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
        },
        "timing": {
            "corpus_preparation_ms": preparation_ms,
            "index_build_ms": index_ms,
            "assumption": "single cold process; no warmup; exploratory only",
        },
        "aggregates": aggregates,
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
    parser.add_argument("--output", type=Path, default=Path("reports/runs/e0-phase2-pilot.json"))
    args = parser.parse_args()
    result = run(args.manifest, args.seed, args.output)
    print(f"saved E0: {result['counts']} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
