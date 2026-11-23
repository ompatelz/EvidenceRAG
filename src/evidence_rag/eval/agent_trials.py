"""Matched three-arm evaluation records; unknown judgments and costs stay unknown."""

from collections import defaultdict
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentTrial(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    question_id: str
    repeat: int = Field(ge=0)
    arm: Literal["direct", "tools", "tools_skill"]
    model: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    configuration_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    corpus_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    code_commit: str = Field(pattern=r"^[a-f0-9]{40}$")
    skill_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    status: Literal["answered", "abstained", "failed"]
    answer: str | None = None
    answerable: bool | None = None
    correct: bool | None = None
    supported: bool | None = None
    reviewer: str | None = None
    reviewer_type: Literal["human", "agent", "unreviewed"] = "unreviewed"
    tool_calls: int = Field(ge=0)
    elapsed_ms: float = Field(ge=0, allow_inf_nan=False)
    tokens: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0, allow_inf_nan=False)


def summarize_trials(trials: list[AgentTrial]) -> dict[str, object]:
    """Require matched inputs and repeated arm completeness before comparisons."""
    if not trials:
        raise ValueError("no agent trials")
    groups: dict[tuple[str, int], list[AgentTrial]] = defaultdict(list)
    for trial in trials:
        groups[(trial.question_id, trial.repeat)].append(trial)
        if trial.status != "answered" and trial.answer:
            raise ValueError("withheld answer cannot be an emitted answer")
        if trial.status == "answered" and not trial.answer:
            raise ValueError("answered trial requires emitted text")
        if trial.arm == "tools_skill" and trial.skill_sha256 is None:
            raise ValueError("skill trial requires exact skill hash")
        if trial.reviewer_type != "unreviewed" and not trial.reviewer:
            raise ValueError("judgments require reviewer provenance")
        if trial.status != "answered" and (trial.correct is True or trial.supported is True):
            raise ValueError("withheld output cannot count as a correct supported answer")
    for group in groups.values():
        if len(group) != 3 or {t.arm for t in group} != {"direct", "tools", "tools_skill"}:
            raise ValueError("incomplete or duplicate comparison arms")
        if (
            len(
                {
                    (t.model, t.revision, t.configuration_sha256, t.corpus_sha256, t.code_commit)
                    for t in group
                }
            )
            != 1
        ):
            raise ValueError("comparison inputs are not matched")
        if len({t.answerable for t in group if t.answerable is not None}) > 1:
            raise ValueError("inconsistent answerability judgments")
    arms = {}
    for arm in ("direct", "tools", "tools_skill"):
        rows = [t for t in trials if t.arm == arm]
        human = [t for t in rows if t.reviewer_type == "human"]
        answerable = [t for t in human if t.answerable is True]
        unanswerable = [t for t in human if t.answerable is False]
        emitted = [t for t in human if t.status == "answered"]
        arms[arm] = {
            "trials": len(rows),
            "human_answerable_judgments": len(answerable),
            "human_correct_final_answers": sum(
                t.status == "answered" and t.correct is True for t in answerable
            ),
            "human_false_abstentions": sum(t.status == "abstained" for t in answerable),
            "human_unanswerable_judgments": len(unanswerable),
            "human_false_answers_on_unanswerable": sum(
                t.status == "answered" for t in unanswerable
            ),
            "human_emitted_support_judgments": sum(t.supported is not None for t in emitted),
            "human_supported_emitted_answers": sum(t.supported is True for t in emitted),
            "tool_calls": sum(t.tool_calls for t in rows),
            "mean_elapsed_ms": sum(t.elapsed_ms for t in rows) / len(rows),
            "observed_tokens": sum(t.tokens for t in rows if t.tokens is not None),
            "token_observations": sum(t.tokens is not None for t in rows),
            "observed_cost_usd": sum(t.cost_usd for t in rows if t.cost_usd is not None),
            "cost_observations": sum(t.cost_usd is not None for t in rows),
        }
    return {
        "matched_question_repeats": len(groups),
        "arms": arms,
        "notice": "Only human judgments enter quality counts; missing telemetry is not zero cost.",
    }
