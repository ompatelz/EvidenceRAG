"""Regenerate the current retrieval baseline and reranker ablation."""

import argparse
import json
from pathlib import Path
from typing import Any

from evidence_rag.eval.benchmark import BenchmarkConfig, run
from evidence_rag.eval.owner_review import SNAPSHOT
from evidence_rag.eval.report import render_report
from evidence_rag.eval.rerank_run import run as run_rerank
from evidence_rag.eval.runner import aggregate_rows
from evidence_rag.retrieval.rerank import RerankConfig

MANIFEST = Path("datasets/manifests/answer-benchmark.json")


def render_ablation(rows_by_method: dict[str, list[dict[str, Any]]], raw_dir: Path) -> str:
    """Render paired retrieval results for all candidates and the verified subset."""
    lines = [
        "# Answer benchmark retrieval ablation",
        "",
        "These development and validation diagnostics use a shared corpus and evidence-unit "
        "relevance. Frozen queries were excluded. Live answers and claim judgments are pending.",
        "",
        "| Method | Cohort | Split | Scored / total | Hit@3 | Recall@3 | nDCG@5 |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    expected: list[str] | None = None
    for method, rows in rows_by_method.items():
        ids = [row["query_id"] for row in rows]
        if expected is None:
            expected = ids
        if (
            ids != expected
            or len(set(ids)) != len(ids)
            or any(
                row["split"] not in {"development", "validation"} or row["failure"] for row in rows
            )
        ):
            raise ValueError("incompatible or failed retrieval arm")
        verified = [row for row in rows if row["review_status"] == "verified"]
        cohorts = (
            [("Owner verified", verified)]
            if len(verified) == len(rows)
            else [("All candidates", rows), ("Owner verified", verified)]
        )
        for cohort, members in cohorts:
            groups = aggregate_rows(members, "split")
            for split in ("development", "validation"):
                group = groups.get(split)
                if group and (m3 := group["metrics"]["3"]):
                    m5 = group["metrics"]["5"]
                    lines.append(
                        f"| {method} | {cohort} | {split} | "
                        f"{group['scored']} / {group['queries']} | "
                        f"{m3['hit_rate']:.3f} | {m3['recall']:.3f} | {m5['ndcg']:.3f} |"
                    )
                else:
                    total = group["queries"] if group else 0
                    lines.append(f"| {method} | {cohort} | {split} | 0 / {total} | — | — | — |")
    lines += [
        "",
        f"Raw outputs are in [{raw_dir.name}]({raw_dir.name}/).",
        "",
        "Only answerable nonvisual examples enter the scored denominator. The synthetic "
        "sample supports descriptive figures for these families.",
        "The reranker comparison uses E2's fixed candidate settings. It measures rankings only.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path("tmp/hf-model-cache"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    raw_dir = args.output_dir / "runs"
    e0_path = raw_dir / "e0.json"
    e1_path = raw_dir / "e1.json"
    e2_path = raw_dir / "e2.json"
    common = {
        "manifest": MANIFEST,
        "seed": SNAPSHOT,
        "e0_baseline": e0_path,
        "e1_baseline": e1_path,
        "model_cache": args.cache_dir,
    }
    e0 = run(BenchmarkConfig(retriever="E0", output=e0_path, **common))
    e1 = run(BenchmarkConfig(retriever="E1", output=e1_path, **common))
    baseline = render_report(
        *(json.loads(path.read_text(encoding="utf-8")) for path in (e0_path, e1_path)),
        e0_path=e0_path,
        e1_path=e1_path,
        seed_path=SNAPSHOT,
        manifest_path=MANIFEST,
    )
    (args.output_dir / "baselines.md").write_text(baseline, encoding="utf-8")

    # Reuse the prior validation-selected settings without another parameter sweep.
    prior = json.loads(Path("reports/runs/e2-hybrid-validation.json").read_text(encoding="utf-8"))
    e2 = run(
        BenchmarkConfig(
            retriever="E2",
            output=e2_path,
            hybrid_configs=(prior["selection"]["selected_config"],),
            **common,
        )
    )
    e3 = run_rerank(
        MANIFEST,
        SNAPSHOT,
        e2_path,
        raw_dir / "e3.json",
        cache_dir=args.cache_dir,
        config=RerankConfig(enabled=True),
    )
    ablation = render_ablation(
        {
            "E0 BM25": e0["queries"],
            "E1 dense": e1["queries"],
            "E2 hybrid": e2["trials"][0]["queries"],
            "E3 reranker": e3["queries"],
        },
        raw_dir,
    )
    (args.output_dir / "retrieval-ablation.md").write_text(ablation, encoding="utf-8")


if __name__ == "__main__":
    main()
