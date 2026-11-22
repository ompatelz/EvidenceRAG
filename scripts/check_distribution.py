"""Verify built resources and exercise an installed wheel outside the source tree."""

import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def main() -> None:
    wheels = sorted(Path("dist").glob("evidence_rag-*.whl"))
    if len(wheels) != 1:
        raise SystemExit("Expected exactly one EvidenceRAG wheel in dist")
    with zipfile.ZipFile(wheels[0]) as wheel:
        names = set(wheel.namelist())
        for resource in (
            "sdk.py",
            "cli.py",
            "mcp_server.py",
            "py.typed",
            "ui/inspector.html",
            "ui/app.js",
            "ui/app.css",
            "evidence-rag-agent/SKILL.md",
            "evidence-rag-agent/agents/openai.yaml",
            "evidence-rag-agent/references/tools.md",
        ):
            if f"evidence_rag/{resource}" not in names:
                raise SystemExit(f"Missing packaged resource: {resource}")
        if not any(name.endswith("/entry_points.txt") for name in names):
            raise SystemExit("Missing console entry point metadata")
        if not any(name.endswith("/licenses/LICENSE") for name in names):
            raise SystemExit("Missing packaged license")
    with tempfile.TemporaryDirectory(prefix="evidencerag-wheel-") as directory:
        target = Path(directory)
        # The wheel is this repository's built artifact, not untrusted input.
        with zipfile.ZipFile(wheels[0]) as wheel:
            wheel.extractall(target / "site")
        env = {**os.environ, "PYTHONPATH": str(target / "site")}
        subprocess.run(
            [sys.executable, "-m", "evidence_rag", "--version"],
            cwd=target,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [sys.executable, "-m", "evidence_rag", "export-skill", str(target / "skill")],
            cwd=target,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        if not (target / "skill/references/tools.md").is_file():
            raise SystemExit("Installed skill export failed")
    print("Wheel resources, entry point metadata and installed module smoke passed")


if __name__ == "__main__":
    main()
