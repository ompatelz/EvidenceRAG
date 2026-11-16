"""Run the pinned local verifier against the provisional claim audit."""

import argparse
import hashlib
import json
import platform
from importlib.metadata import version
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from evidence_rag.semantic import (
    MODEL_NAME,
    MODEL_REVISION,
    PREPROCESSING,
    LocalDeberta,
    SemanticVerifier,
)

AUDIT = Path("datasets/eval/semantic_audit.jsonl")


class AuditItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    split: Literal["development", "validation"]
    passages: tuple[str, ...] = Field(min_length=1, max_length=5)
    claim: str
    expected: Literal["supported", "contradicted", "insufficient", "uncertain"]
    rationale: str
    review: Literal["needs_human_review", "verified"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = AUDIT.read_bytes().replace(b"\r\n", b"\n")
    items = [AuditItem.model_validate_json(line) for line in source.splitlines() if line.strip()]
    verifier = SemanticVerifier(LocalDeberta(args.cache_dir), timeout_ms=15000)
    results = []
    for item in items:
        (result,) = verifier.assess([(item.claim, item.passages, False)])
        if result.status != "assessed":
            raise SystemExit(f"{item.id}: verifier {result.status}; check the pinned local cache")
        results.append({"audit": item.model_dump(mode="json"), "result": result.model_dump()})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "audit_sha256": hashlib.sha256(source).hexdigest(),
                "model": MODEL_NAME,
                "revision": MODEL_REVISION,
                "preprocessing": PREPROCESSING,
                "threshold": "argmax; exact top-score ties are insufficient",
                "runtime": {
                    "python": platform.python_version(),
                    "system": platform.system(),
                    "onnxruntime": version("onnxruntime"),
                    "tokenizers": version("tokenizers"),
                },
                "results": results,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
