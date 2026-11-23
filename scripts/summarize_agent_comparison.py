"""Summarize matched agent trial JSONL without inventing judgments or telemetry."""

import argparse
import json
from pathlib import Path

from evidence_rag.eval.agent_trials import AgentTrial, summarize_trials


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [
        AgentTrial.model_validate_json(line)
        for line in args.input.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    with args.output.open("x", encoding="utf-8") as target:
        target.write(json.dumps(summarize_trials(rows), indent=2) + "\n")


if __name__ == "__main__":
    main()
