"""Local signed-in Codex CLI adapter with command and connector tools disabled."""

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic

from evidence_rag.answers import DraftAnswer, EvidencePack, GenerationError
from evidence_rag.openai_answers import (
    INSTRUCTIONS,
    MAX_REQUEST_BYTES,
    MAX_RESPONSE_BYTES,
    check_deadline,
    response_schema,
)

CODEX_TIMEOUT_SECONDS = 45.0
LOGGER = logging.getLogger("evidence_rag.codex")


class CodexAnswerGenerator:
    def __init__(self, executable: Path | None, *, model: str | None = None) -> None:
        self._executable = executable
        self._model = model

    def generate_cancellable(
        self, question: str, pack: EvidencePack, cancelled: Event
    ) -> DraftAnswer:
        started = monotonic()
        deadline = started + CODEX_TIMEOUT_SECONDS
        check_deadline(deadline, cancelled)
        binary = self._executable or shutil.which("codex.exe" if os.name == "nt" else "codex")
        if not binary:
            raise GenerationError("generator_unavailable")
        executable = Path(binary).resolve()
        if not executable.is_file() or (os.name == "nt" and executable.suffix.lower() != ".exe"):
            raise GenerationError("generator_unavailable")
        prompt = (
            INSTRUCTIONS
            + " Return the JSON response directly without using any tools.\n"
            + json.dumps(
                {
                    "question": question,
                    "evidence": [item.model_dump(mode="json") for item in pack.items],
                },
                ensure_ascii=False,
            )
        ).encode()
        if len(prompt) > MAX_REQUEST_BYTES:
            raise GenerationError("generation_budget_exceeded")
        outcome = "generation_failed"
        try:
            draft = self._run(executable, prompt, deadline, cancelled)
            outcome = draft.status
            return draft
        except GenerationError as exc:
            outcome = exc.reason
            raise
        except OSError as exc:
            raise GenerationError("generation_failed") from exc
        finally:
            LOGGER.info(
                json.dumps(
                    {
                        "event": "answer_generation",
                        "provider": "codex",
                        "outcome": outcome,
                        "latency_ms": round((monotonic() - started) * 1000, 3),
                    }
                )
            )

    def _run(
        self, executable: Path, prompt: bytes, deadline: float, cancelled: Event
    ) -> DraftAnswer:
        with TemporaryDirectory(prefix="evidencerag-codex-") as root:
            workdir = Path(root)
            schema, output, request = (workdir / name for name in ("schema.json", "out.json", "in"))
            schema.write_text(json.dumps(response_schema()), encoding="utf-8")
            request.write_bytes(prompt)
            args = [
                str(executable),
                "-a",
                "never",
                "-c",
                'forced_login_method="chatgpt"',
                "-c",
                'web_search="disabled"',
                "-c",
                "mcp_servers={}",
                "exec",
                "--ignore-user-config",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "--ephemeral",
                "--output-schema",
                str(schema),
                "--output-last-message",
                str(output),
            ]
            for feature in (
                "apps",
                "hooks",
                "memories",
                "multi_agent",
                "multi_agent_v2",
                "plugins",
                "remote_plugin",
                "shell_tool",
                "view_image",
            ):
                args.extend(("--disable", feature))
            if self._model is not None:
                args.extend(("--model", self._model))
            args.append("-")
            env = {
                key: value
                for key, value in os.environ.items()
                if not key.upper().startswith(("OPENAI_", "OPENROUTER_", "EVIDENCERAG_"))
                and key.upper() not in {"CODEX_API_KEY", "CODEX_THREAD_ID"}
            }
            with (
                request.open("rb") as stdin,
                subprocess.Popen(
                    args,
                    cwd=workdir,
                    env=env,
                    stdin=stdin,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                ) as process,
            ):
                try:
                    while process.poll() is None:
                        cancelled.wait(min(0.05, check_deadline(deadline, cancelled)))
                    check_deadline(deadline, cancelled)
                finally:
                    if process.poll() is None:
                        process.kill()
                if process.returncode != 0:
                    raise GenerationError("generation_failed")
            try:
                with output.open("rb") as stream:
                    raw = stream.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ValueError("oversized response")
                draft = DraftAnswer.model_validate_json(raw, strict=True)
                if draft.model_dump(exclude_unset=True) != draft.model_dump():
                    raise ValueError("missing required draft fields")
                return draft
            except (OSError, ValueError) as exc:
                raise GenerationError("malformed_response") from exc
