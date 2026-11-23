"""Verify built resources and exercise an installed wheel outside the source tree."""

import argparse
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true", help="Install wheel in a fresh uv venv")
    args = parser.parse_args()
    wheels = sorted(Path("dist").glob("evidence_rag-*.whl"))
    if len(wheels) != 1:
        raise SystemExit("Expected exactly one EvidenceRAG wheel in dist")
    with zipfile.ZipFile(wheels[0]) as wheel:
        names = set(wheel.namelist())
        for resource in (
            "sdk.py",
            "calculations.py",
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
        if args.install:
            venv = target / "venv"
            subprocess.run(["uv", "venv", str(venv), "--python", sys.executable], check=True)
            interpreter = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            console = venv / ("Scripts/evidence-rag.exe" if os.name == "nt" else "bin/evidence-rag")
            subprocess.run(
                ["uv", "pip", "install", "--python", str(interpreter), str(wheels[0].resolve())],
                check=True,
            )
            clean_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
            subprocess.run([str(console), "--version"], cwd=target, env=clean_env, check=True)
            subprocess.run(
                [str(console), "export-skill", str(target / "installed-skill")],
                cwd=target,
                env=clean_env,
                check=True,
                capture_output=True,
                text=True,
            )
            fixture = Path("datasets/fixtures/atlas-narrative.pdf").resolve()
            subprocess.run(
                [
                    str(console),
                    "--artifact-root",
                    str(target / "artifacts"),
                    "ingest",
                    str(fixture),
                ],
                cwd=target,
                env=clean_env,
                check=True,
                capture_output=True,
                text=True,
            )
    print("Wheel resources, entry point metadata and installed module smoke passed")


if __name__ == "__main__":
    main()
