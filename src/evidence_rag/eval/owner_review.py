"""Build the current label snapshot from the immutable seed and owner decisions."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from evidence_rag.eval.models import EvaluationItem, ReviewStatus
from evidence_rag.eval.validate import load_evaluation_jsonl

SEED = Path("datasets/eval/phase2_seed.jsonl")
EXPANSION = Path("datasets/eval/expansion_candidates.jsonl")
DECISIONS = Path("datasets/eval/owner_decisions.json")
SNAPSHOT = Path("datasets/eval/reviewed_labels.jsonl")

REVIEWABLE = {
    "question",
    "category",
    "answerable",
    "gold_answers",
    "numeric_tolerance",
    "gold_evidence",
    "requires_visual_evidence",
    "difficulty",
    "annotator_notes",
    "ambiguity",
}


class OwnerDecision(BaseModel):
    """Record the owner's exact reply and its application to one label."""

    model_config = ConfigDict(extra="forbid")

    query_id: str = Field(min_length=1)
    owner_reply: str = Field(min_length=1)
    changes: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(min_length=1)


def apply_decisions(
    items: Sequence[EvaluationItem], decisions: Sequence[OwnerDecision]
) -> list[EvaluationItem]:
    lookup = {item.query_id: item for item in items}
    applied: set[str] = set()
    for decision in decisions:
        query_id = decision.query_id
        if query_id in applied or query_id not in lookup:
            raise ValueError(f"duplicate or unknown owner decision: {query_id}")
        if unexpected := decision.changes.keys() - REVIEWABLE:
            raise ValueError(f"owner decision changes immutable fields: {sorted(unexpected)}")
        prior = lookup[query_id]
        lookup[query_id] = EvaluationItem.model_validate(
            {
                **prior.model_dump(),
                **decision.changes,
                "review_status": ReviewStatus.VERIFIED,
            }
        )
        applied.add(query_id)
    return list(lookup.values())


def snapshot_jsonl() -> str:
    records = json.loads(DECISIONS.read_text(encoding="utf-8"))
    decisions = [OwnerDecision.model_validate(record) for record in records]
    items = load_evaluation_jsonl(SEED) + load_evaluation_jsonl(EXPANSION)
    rows = apply_decisions(items, decisions)
    return "".join(row.model_dump_json() + "\n" for row in rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = snapshot_jsonl()
    if args.check:
        if SNAPSHOT.read_text(encoding="utf-8") != expected:
            parser.error("label snapshot differs from the seed and owner decisions")
    else:
        SNAPSHOT.write_text(expected, encoding="utf-8")


if __name__ == "__main__":
    main()
