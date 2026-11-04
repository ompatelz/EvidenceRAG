"""Validate raw E0/E1 runs and render the provisional Phase 2 baseline report."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from evidence_rag.eval.metrics import score_ranking
from evidence_rag.eval.runner import (
    CUTOFFS,
    aggregate_rows,
    development_items,
    normalized_text_sha256,
)
from evidence_rag.eval.validate import load_evaluation_jsonl, validate_dataset


def _same(actual: object, expected: object) -> bool:
    """Compare JSON-compatible metric trees within floating-point rounding."""
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            _same(actual[key], expected[key]) for key in actual
        )
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return abs(actual - expected) < 1e-9
    return actual == expected


def validate_run(
    run: dict[str, Any], experiment: str, dataset_hash: str, manifest_hash: str
) -> None:
    """Reject incompatible, leaked, or internally inconsistent saved rankings."""
    if (
        run.get("experiment") != experiment
        or run.get("dataset_sha256") != dataset_hash
        or run.get("manifest_sha256") != manifest_hash
        or run.get("relevance_unit") != "evidence_unit"
        or run.get("config", {}).get("cutoffs") != list(CUTOFFS)
        or not run.get("index_id")
    ):
        raise ValueError(f"{experiment} manifest is incompatible")
    if experiment == "E1" and (
        not run.get("model", {}).get("revision") or not run.get("model", {}).get("dimension")
    ):
        raise ValueError("E1 model identity is incomplete")
    rows = run.get("queries")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{experiment} has no raw queries")
    ids: set[str] = set()
    for row in rows:
        query_id = row["query_id"]
        if query_id in ids or row["split"] not in {"development", "validation"}:
            raise ValueError("duplicate query or frozen-test leakage")
        ids.add(query_id)
        scope = {tuple(pair) for pair in row["scope"]}
        ranking = row["ranking"]
        ranked_ids = [hit["evidence_id"] for hit in ranking]
        if len(set(ranked_ids)) != len(ranked_ids):
            raise ValueError("duplicate evidence ID in saved ranking")
        for rank, hit in enumerate(ranking, 1):
            if hit["rank"] != rank or (hit["document_id"], hit["document_version"]) not in scope:
                raise ValueError("saved ranking violates rank or document scope")
        failure = row.get("failure")
        if failure is not None:
            if row["metrics"] is not None or ranking or failure["query_id"] != query_id:
                raise ValueError("failed query has successful results")
        elif row["answerable"] and not row["requires_visual_evidence"]:
            gold = set(row["gold_evidence_ids"])
            expected = {str(k): vars(score_ranking(ranked_ids, gold, k=k)) for k in CUTOFFS}
            if not _same(row["metrics"], expected):
                raise ValueError("saved per-query metric does not match raw ranking")
        elif row["metrics"] is not None:
            raise ValueError("non-scored query has retrieval metrics")
    expected_groups = aggregate_rows(rows, "split")
    expected_aggregates = {split: group["metrics"] for split, group in expected_groups.items()}
    if not _same(run.get("aggregates"), expected_aggregates):
        raise ValueError("saved aggregate does not match raw rankings")
    if not _same(run.get("per_category"), aggregate_rows(rows, "category")):
        raise ValueError("saved category metric does not match raw rankings")
    expected_failures = [row["failure"] for row in rows if row.get("failure") is not None]
    if run.get("failures") != expected_failures:
        raise ValueError("failure list does not match raw queries")
    expected_status = "partial_failure" if expected_failures else "provisional_unreviewed_labels"
    if run.get("status") != expected_status:
        raise ValueError("run status does not match failures")
    if run.get("counts", {}).get("queries") != len(rows) or run.get("counts", {}).get(
        "scored"
    ) != sum(row["metrics"] is not None for row in rows):
        raise ValueError("saved query counts are inconsistent")


def _first_relevant_rank(row: dict[str, Any]) -> int | None:
    gold = set(row["gold_evidence_ids"])
    return next((hit["rank"] for hit in row["ranking"] if hit["evidence_id"] in gold), None)


def render_report(
    e0: dict[str, Any],
    e1: dict[str, Any],
    *,
    e0_path: Path,
    e1_path: Path,
    seed_path: Path,
    manifest_path: Path,
) -> str:
    """Derive every figure from validated raw run artifacts."""
    dataset_hash = normalized_text_sha256(seed_path)
    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    validate_run(e0, "E0", dataset_hash, manifest_hash)
    validate_run(e1, "E1", dataset_hash, manifest_hash)
    validate_dataset(manifest_path, [seed_path], verify_evidence=True)
    items = load_evaluation_jsonl(seed_path)
    selected = development_items(items)
    expected_ids = [item.query_id for item in selected]
    a_rows = e0["queries"]
    b_rows = e1["queries"]
    if [row["query_id"] for row in a_rows] != expected_ids or [
        row["query_id"] for row in b_rows
    ] != expected_ids:
        raise ValueError("run query IDs do not match the selected evaluation set")
    if e0["corpus_versions"] != e1["corpus_versions"]:
        raise ValueError("E0/E1 corpus versions differ")
    for a, b in zip(a_rows, b_rows, strict=True):
        for field in (
            "query_id",
            "split",
            "category",
            "review_status",
            "answerable",
            "requires_visual_evidence",
            "scope",
            "gold_evidence_ids",
        ):
            if a[field] != b[field]:
                raise ValueError(f"E0/E1 row contract differs: {field}")
    verified = sum(item.review_status.value == "verified" for item in items)
    scored = sum(row["metrics"] is not None for row in a_rows)
    wins: dict[str, list[str]] = {"E0": [], "E1": [], "both_miss_at_5": []}
    for a, b in zip(a_rows, b_rows, strict=True):
        if a["metrics"] is None or b["metrics"] is None:
            continue
        ar, br = _first_relevant_rank(a), _first_relevant_rank(b)
        if ar is None and br is None:
            wins["both_miss_at_5"].append(a["query_id"])
        elif br is None or (ar is not None and ar < br):
            wins["E0"].append(a["query_id"])
        elif ar is None or br < ar:
            wins["E1"].append(a["query_id"])

    lines = [
        "# Phase 2 search baselines — provisional gate report",
        "",
        "## Provenance and reproduction",
        "",
        f"- Dataset SHA-256: `{dataset_hash}`; manifest SHA-256: `{manifest_hash}`.",
        "- Dataset and source text hashes normalize line endings to LF so Windows "
        "and Linux checkouts have the same identity.",
        f"- E0 raw run: `{e0_path.as_posix()}`; run Git SHA `{e0['git_sha_at_run']}`; "
        f"index `{e0['index_id']}`.",
        f"- E0 source SHA-256 `{e0['source_sha256']}`; source uncommitted at run: "
        f"`{str(e0['source_tree_uncommitted_at_run']).lower()}`.",
        f"- E1 raw run: `{e1_path.as_posix()}`; run Git SHA `{e1['git_sha_at_run']}`; "
        f"index `{e1['index_id']}`; model revision `{e1['model']['revision']}`.",
        f"- E1 source SHA-256 `{e1['source_sha256']}`; source uncommitted at run: "
        f"`{str(e1['source_tree_uncommitted_at_run']).lower()}`.",
        "- Both runs use the same canonical evidence units, exact document versions, "
        "query IDs, evidence-unit binary relevance, and K=1/3/5.",
        "- Run `uv run python -m evidence_rag.eval.benchmark --config configs/phase2-e0.json`.",
        "- With the pinned model cached, run "
        "`uv run python -m evidence_rag.eval.benchmark --config configs/phase2-e1.json`. "
        "For the first download, set `download_model` to `true` in a copy of that "
        "config; ordinary CI never downloads model weights.",
        "- Generate this report with `uv run python -m evidence_rag.eval.report`.",
        "- Timings are exploratory single cold-process observations without warmup; "
        "E1 separates query embedding from vector search. They are not latency "
        "benchmarks. Peak memory was not measured.",
        "",
        "## Dataset and gate",
        "",
        f"- {len(items)} candidate questions: {len(selected)} development/validation "
        f"queries and {len(items) - len(selected)} frozen-test queries; {verified} human "
        f"verified. {scored} answerable nonvisual questions are scored in each run.",
        f"- The frozen test was not searched or used for tuning. {len(items) - verified} "
        "labels require owner review.",
        "- **Phase 2 gate: NOT PASSED.** The target is 30-50 human-verified "
        "questions; this pilot has 13 candidate labels and 0 verified. It also "
        "lacks equations and broader external document coverage. The PR remains draft.",
        "",
        "## Aggregate evidence-unit results",
        "",
        "| Split | Method | Scored | Hit@1 | Hit@3 | Recall@3 | MRR@3 | nDCG@3 |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for split in ("development", "validation"):
        for name, run in (("E0", e0), ("E1", e1)):
            metric1 = run["aggregates"][split]["1"]
            metric3 = run["aggregates"][split]["3"]
            denominator = sum(
                row["split"] == split and row["metrics"] is not None for row in run["queries"]
            )
            lines.append(
                f"| {split} | {name} | {denominator} | {metric1['hit_rate']:.3f} | "
                f"{metric3['hit_rate']:.3f} | {metric3['recall']:.3f} | "
                f"{metric3['mrr']:.3f} | {metric3['ndcg']:.3f} |"
            )
    lines += [
        "",
        "## Per-category diagnostics",
        "",
        "Categories with no scored answerable nonvisual questions have no retrieval metric.",
        "",
        "| Category | Method | Scored | Hit@1 | Hit@3 |",
        "|---|---|---:|---:|---:|",
    ]
    for category in sorted(e0["per_category"]):
        for name, run in (("E0", e0), ("E1", e1)):
            group = run["per_category"][category]
            m1 = group["metrics"]["1"]
            m3 = group["metrics"]["3"]
            lines.append(
                f"| {category} | {name} | {group['scored']} | "
                f"{m1['hit_rate']:.3f} | {m3['hit_rate']:.3f} |"
                if m1 and m3
                else f"| {category} | {name} | 0 | — | — |"
            )
    lines += [
        "",
        "## Controlled comparison and failures",
        "",
        f"- E0 wins on first relevant rank: {', '.join(wins['E0']) or 'none observed'}.",
        f"- E1 wins on first relevant rank: {', '.join(wins['E1']) or 'none observed'}.",
        "- Both miss relevant evidence within K=5: "
        f"{', '.join(wins['both_miss_at_5']) or 'none observed'}.",
        "- `p2_atlas_path` places its provisional relevant unit at rank 2 in both "
        "runs. At K=1 this is a ranking failure (taxonomy d); both retrieve it by K=3.",
        "- Unanswerable questions still return candidates; this retrieval-only benchmark "
        "cannot measure abstention (taxonomy g).",
        "- No parser/OCR/layout (a) or indexing/chunking (b) failure can be "
        "established from these eight queries. No relevant-source miss by K=5 (c) "
        "is observed. Interpretation (e), citation support (f), and security (h) "
        "are outside this retrieval evaluation; document/version isolation has "
        "separate tests.",
        "- Visual chart questions stay in the frozen family. Their parsing and "
        "annotation quality cannot be inferred from this run. All provisional "
        "labels could change after source-page review.",
        f"- Recorded query failures: E0={len(e0['failures'])}, "
        f"E1={len(e1['failures'])}; any future partial failures are saved per "
        "query and excluded from scored denominators.",
        "",
        "## Limits",
        "",
        "These figures are diagnostics from a small repository-authored synthetic "
        "pilot, not validated generalization or a portfolio improvement claim. "
        "There are no observed E0 wins, E1 wins, or joint misses at K=5 to "
        "illustrate; creating such examples would misrepresent the saved runs.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--e0", type=Path, default=Path("reports/runs/e0-phase2-pilot.json"))
    parser.add_argument("--e1", type=Path, default=Path("reports/runs/e1-phase2-pilot.json"))
    parser.add_argument("--seed", type=Path, default=Path("datasets/eval/phase2_seed.jsonl"))
    parser.add_argument("--manifest", type=Path, default=Path("datasets/manifests/fixtures.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/baselines.md"))
    args = parser.parse_args()
    e0 = json.loads(args.e0.read_text(encoding="utf-8"))
    e1 = json.loads(args.e1.read_text(encoding="utf-8"))
    report = render_report(
        e0,
        e1,
        e0_path=args.e0,
        e1_path=args.e1,
        seed_path=args.seed,
        manifest_path=args.manifest,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"saved report to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
