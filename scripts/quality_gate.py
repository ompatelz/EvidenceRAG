"""Run the local quality and deterministic data checks with locked dependencies."""

import subprocess
import sys

MANIFEST = "datasets/manifests/fixtures.json"


def main() -> None:
    checks = [
        ["uv", "lock", "--check"],
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "-m", "ruff", "format", "--check", "."],
        [sys.executable, "-m", "mypy"],
        [sys.executable, "-m", "pytest"],
        ["node", "--test", "tests/inspector_ui.test.cjs"],
        [sys.executable, "scripts/generate_fixtures.py", "--check"],
        [
            sys.executable,
            "-m",
            "evidence_rag.eval.validate",
            "--manifest",
            MANIFEST,
            "datasets/eval/fixture_items.jsonl",
        ],
        [
            sys.executable,
            "-m",
            "evidence_rag.eval.validate",
            "--manifest",
            MANIFEST,
            "--verify-evidence",
            "datasets/eval/phase2_seed.jsonl",
        ],
        [sys.executable, "-m", "evidence_rag.eval.benchmark", "--config", "configs/phase2-e0.json"],
        [
            sys.executable,
            "-m",
            "evidence_rag.eval.report",
            "--output",
            "reports/generated/baselines-ci.md",
        ],
        [
            sys.executable,
            "-m",
            "evidence_rag.eval.claim_comparison",
            "--smoke",
            "--output",
            "reports/generated/claim-comparison-ci.json",
        ],
    ]
    for command in checks:
        print("+", subprocess.list2cmdline(command), flush=True)
        subprocess.run(command, check=True, timeout=300)


if __name__ == "__main__":
    main()
