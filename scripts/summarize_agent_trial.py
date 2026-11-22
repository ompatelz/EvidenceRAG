"""Summarize an exploratory three-arm trial from explicit agent source judgments."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ARMS = {"A": "tools_and_skill", "B": "baseline", "C": "tools_only"}


def summarize(root: Path) -> dict[str, Any]:
    questions = json.loads((root / "questions.json").read_text(encoding="utf-8"))
    ids = {row["query_id"] for row in questions}
    eligible = {
        row["query_id"]: row
        for row in (
            json.loads(line)
            for line in Path("datasets/eval/reviewed_labels.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        if row["split"] in ("development", "validation")
    }
    if len(ids) != len(questions) or not ids or not ids.issubset(eligible):
        raise ValueError("trial questions must be unique development/validation IDs")
    if any(row["question"] != eligible[row["query_id"]]["question"] for row in questions):
        raise ValueError("trial questions differ from the reviewed question text")
    audit = json.loads((root / "source-judgments.json").read_text(encoding="utf-8"))
    if audit.get("reviewer_type") != "independent_agent_source_audit" or audit.get(
        "human_verified"
    ):
        raise ValueError("this report requires explicitly labeled agent-only source judgments")
    judgments = audit["judgments"]
    keys = {(row["arm"], row["query_id"]) for row in judgments}
    if len(keys) != len(judgments) or keys != {(arm, qid) for arm in ARMS for qid in ids}:
        raise ValueError("every arm must have exactly one judgment for each question")
    if any(
        len({row["source_has_enough_information"] for row in judgments if row["query_id"] == qid})
        != 1
        for qid in ids
    ):
        raise ValueError("source answerability judgments disagree across arms")
    result: dict[str, Any] = {}
    for blind, name in ARMS.items():
        rows = [row for row in judgments if row["arm"] == blind]
        raw = json.loads((root / f"{name}.json").read_text(encoding="utf-8"))
        responses = raw.get("answers", raw.get("questions", raw.get("results", [])))
        if len(responses) != len(ids) or {row["query_id"] for row in responses} != ids:
            raise ValueError("raw response query set differs from source judgments")
        by_id = {row["query_id"]: row for row in responses}
        for row in rows:
            response = by_id[row["query_id"]]
            if row["emitted"] != (not response["abstained"]) or (
                row["emitted"] != bool(response["answer"])
            ):
                raise ValueError("source judgment and emitted answer disagree")
        answerable = [row for row in rows if row["source_has_enough_information"]]
        absent = [row for row in rows if not row["source_has_enough_information"]]
        emitted = [row for row in rows if row["emitted"]]
        result[name] = {
            "questions": len(rows),
            "correct_final_answers_over_answerable": [
                sum(row["answer_correct"] is True for row in answerable),
                len(answerable),
            ],
            "answerable_coverage": [sum(row["emitted"] for row in answerable), len(answerable)],
            "false_abstentions": [sum(not row["emitted"] for row in answerable), len(answerable)],
            "false_answers_on_unanswerable": [sum(row["emitted"] for row in absent), len(absent)],
            "supported_emitted_answers": [
                sum(row["all_emitted_claims_supported"] is True for row in emitted),
                len(emitted),
            ],
            "correctly_paged_emitted_answers": [
                sum(row["page_citations_correct"] is True for row in emitted),
                len(emitted),
            ],
            "document_operations": raw.get(
                "operation_count", len(raw.get("document_operations", []))
            ),
        }
    paths = [
        root / name
        for name in (
            "questions.json",
            "source-judgments.json",
            "baseline.json",
            "tools_only.json",
            "tools_and_skill.json",
        )
    ]
    return {
        "classification": "exploratory_agent_source_audit_not_a_frozen_accuracy_benchmark",
        "human_verified": False,
        "model_revision_exposed": False,
        "runtime_source_fingerprint_captured": False,
        "arms": result,
        "text_hashing": "UTF-8 with LF line endings",
        "input_sha256": {
            p.name: hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            for p in paths
        },
        "limitations": [
            "Four synthetic development questions; one trial per arm.",
            "Inherited agent model and sampling settings are not fully exposed.",
            "Working-tree changes were underway; loaded-source hashes were not captured.",
            "Latency scopes differ; token usage and provider cost are unobserved.",
            "Independent agent source judgments are not human judgments.",
            "No agent-quality improvement or population-risk conclusion is established.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, default=Path("reports/agent-comparison"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = json.dumps(summarize(args.runs), indent=2) + "\n"
    if args.check:
        if args.output.read_text(encoding="utf-8") != rendered:
            raise SystemExit("trial summary differs from its raw evidence")
    else:
        with args.output.open("x", encoding="utf-8") as target:
            target.write(rendered)
    print("Exploratory trial evidence and summary agree")


if __name__ == "__main__":
    main()
