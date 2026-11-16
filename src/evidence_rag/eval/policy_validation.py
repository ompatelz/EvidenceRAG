"""Evaluate abstention decisions against synthetic validation-only signals."""

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from evidence_rag.grounding import RuleSupport
from evidence_rag.policy import POLICY_VERSION, AnswerPolicy
from evidence_rag.semantic import SemanticResult

FIXTURES = Path("datasets/eval/policy_validation.jsonl")
MARGINS = (0.0, 0.5, 1.0, 2.0)


class Signals(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_support: RuleSupport
    semantic_support: SemanticResult | None = None


class ValidationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    split: Literal["validation"]
    category: str
    answerable: bool
    draft_correct: bool
    signal: Signals
    evidence_available: bool
    requires_visual: bool
    failure: Literal["parsing_failed", "indexing_failed"] | None


@dataclass(frozen=True)
class Outcome:
    answerable: bool
    answered: bool
    correct: bool
    reason: str


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def metrics(outcomes: list[Outcome]) -> dict[str, int | float | None]:
    answered = sum(item.answered for item in outcomes)
    correct = sum(item.answered and item.correct for item in outcomes)
    answerable = sum(item.answerable for item in outcomes)
    false_answers = sum(item.answered and not item.answerable for item in outcomes)
    false_abstentions = sum(not item.answered and item.answerable for item in outcomes)
    return {
        "queries": len(outcomes),
        "answered": answered,
        "correct_answers": correct,
        "answerable": answerable,
        "coverage": _rate(answered, len(outcomes)),
        "false_answers_on_unanswerable": false_answers,
        "false_answer_rate_on_unanswerable": _rate(false_answers, len(outcomes) - answerable),
        "false_abstentions": false_abstentions,
        "false_abstention_rate": _rate(false_abstentions, answerable),
        "selective_accuracy": _rate(correct, answered),
    }


def run(fixtures: Path = FIXTURES) -> dict[str, object]:
    source = fixtures.read_bytes().replace(b"\r\n", b"\n")
    cases = [
        ValidationCase.model_validate_json(line) for line in source.splitlines() if line.strip()
    ]
    if not cases or len({case.id for case in cases}) != len(cases):
        raise ValueError("validation cases must have unique IDs and be nonempty")
    settings = []
    rankable = []
    for margin in (*MARGINS, "always_answer", "always_abstain"):
        policy = AnswerPolicy(min_margin=margin) if isinstance(margin, float) else None
        by_category: dict[str, list[Outcome]] = {}
        outcomes = []
        decisions = []
        for case in cases:
            reason: str
            if policy is not None:
                reason = policy.decide(
                    [case.signal],
                    evidence_available=case.evidence_available,
                    requires_visual=case.requires_visual,
                    failure=case.failure,
                )
                answered = reason == "answered"
            else:
                reason = str(margin)
                answered = margin == "always_answer"
            outcome = Outcome(case.answerable, answered, case.draft_correct, reason)
            by_category.setdefault(case.category, []).append(outcome)
            outcomes.append(outcome)
            decisions.append(
                {
                    "id": case.id,
                    "decision": reason,
                    "answered": answered,
                    "correct_answer_emitted": answered and case.draft_correct,
                }
            )
        settings.append(
            {
                "setting": margin,
                "metrics": metrics(outcomes),
                "categories": {category: metrics(rows) for category, rows in by_category.items()},
                "decisions": decisions,
            }
        )
        if isinstance(margin, float):
            wrong = sum(item.answered and not item.correct for item in outcomes)
            correct = sum(item.answered and item.correct for item in outcomes)
            rankable.append((wrong, -correct, margin))
    selected = min(rankable)[2]
    return {
        "split": "validation",
        "signal_source": "scripted synthetic cases, no model inference",
        "input_sha256": hashlib.sha256(source).hexdigest(),
        "policy_version": POLICY_VERSION,
        "selection_rule": (
            "minimize wrong answers, then maximize correct answers, then lower margin"
        ),
        "selected_margin": selected,
        "inputs": [case.model_dump(mode="json") for case in cases],
        "settings": settings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(run(), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
