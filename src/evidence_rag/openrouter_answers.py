"""Bounded text-only OpenRouter Chat Completions adapter."""

import json
import logging
from threading import Event
from time import monotonic

from evidence_rag.answers import DraftAnswer, EvidencePack, GenerationError
from evidence_rag.openai_answers import (
    INSTRUCTIONS,
    MAX_INPUT_TOKENS_ESTIMATE,
    MAX_OUTPUT_TOKENS,
    MAX_REQUEST_BYTES,
    MAX_RESPONSE_BYTES,
    TIMEOUT_SECONDS,
    Transport,
    check_deadline,
    post_json,
    response_schema,
)

LOGGER = logging.getLogger("evidence_rag.openrouter")


def send(key: str, body: bytes, deadline: float, cancelled: Event) -> tuple[int, bytes]:
    return post_json("openrouter.ai", "/api/v1/chat/completions", key, body, deadline, cancelled)


class OpenRouterAnswerGenerator:
    def __init__(self, key: str | None, model: str | None, transport: Transport = send) -> None:
        self._key = key
        self._model = model
        self._transport = transport

    def generate_cancellable(
        self, question: str, pack: EvidencePack, cancelled: Event
    ) -> DraftAnswer:
        started = monotonic()
        deadline = started + TIMEOUT_SECONDS
        check_deadline(deadline, cancelled)
        if not self._key or not self._key.strip() or not self._model:
            raise GenerationError("generator_unavailable")
        body = json.dumps(
            {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": INSTRUCTIONS},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "question": question,
                                "evidence": [item.model_dump(mode="json") for item in pack.items],
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "grounded_answer",
                        "strict": True,
                        "schema": response_schema(),
                    },
                },
                "provider": {
                    "require_parameters": True,
                    "allow_fallbacks": False,
                    "data_collection": "deny",
                    "max_price": {"prompt": 0.25, "completion": 2},
                },
                "temperature": 0,
                "max_tokens": MAX_OUTPUT_TOKENS,
            },
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
        if len(body) > MAX_REQUEST_BYTES:
            raise GenerationError("generation_budget_exceeded")
        outcome = "generation_failed"
        try:
            status, raw = self._transport(self._key, body, deadline, cancelled)
            check_deadline(deadline, cancelled)
            if status == 429:
                raise GenerationError("generation_rate_limited")
            if status != 200:
                raise GenerationError("generation_failed")
            if len(raw) > MAX_RESPONSE_BYTES:
                raise GenerationError("malformed_response")
            try:
                response = json.loads(raw)
                (choice,) = response["choices"]
                if choice["finish_reason"] != "stop":
                    raise ValueError("incomplete completion")
                usage = response["usage"]
                for count, limit in (
                    (usage["prompt_tokens"], MAX_INPUT_TOKENS_ESTIMATE),
                    (usage["completion_tokens"], MAX_OUTPUT_TOKENS),
                ):
                    if type(count) is not int or count < 0:
                        raise ValueError("invalid usage")
                    if count > limit:
                        raise GenerationError("generation_budget_exceeded")
                draft = DraftAnswer.model_validate_json(choice["message"]["content"], strict=True)
                if draft.model_dump(exclude_unset=True) != draft.model_dump():
                    raise ValueError("missing required draft fields")
            except (TypeError, ValueError, KeyError) as exc:
                raise GenerationError("malformed_response") from exc
            outcome = draft.status
            return draft
        except GenerationError as exc:
            outcome = exc.reason
            raise
        finally:
            LOGGER.info(
                json.dumps(
                    {
                        "event": "answer_generation",
                        "provider": "openrouter",
                        "model": self._model,
                        "outcome": outcome,
                        "latency_ms": round((monotonic() - started) * 1000, 3),
                    }
                )
            )
