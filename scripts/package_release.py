"""Package the companion skill and hash already-tested Python distributions."""

import argparse
import gzip
import hashlib
import io
import json
import re
import tarfile
import zipfile
from pathlib import Path


def package(dist: Path, git_sha: str, workflow_run: str) -> None:
    if not re.fullmatch(r"[a-f0-9]{40}", git_sha):
        raise ValueError("a full Git commit SHA is required")
    version_source = Path("src/evidence_rag/__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__ = "([0-9]+\.[0-9]+\.[0-9]+)"', version_source)
    if match is None:
        raise ValueError("release version missing")
    version = match[1]
    wheel = dist / f"evidence_rag-{version}-py3-none-any.whl"
    source = dist / f"evidence_rag-{version}.tar.gz"
    if not wheel.is_file() or not source.is_file():
        raise ValueError("the tested wheel and source distribution are required")
    prefix = "evidence_rag/evidence-rag-agent/"
    skill_path = dist / f"evidence-rag-agent-{version}.tar.gz"
    with zipfile.ZipFile(wheel) as archive, skill_path.open("wb") as target:
        members = sorted(name for name in archive.namelist() if name.startswith(prefix))
        required = {
            prefix + name for name in ("SKILL.md", "agents/openai.yaml", "references/tools.md")
        }
        if not required.issubset(members):
            raise ValueError("wheel has incomplete skill resources")
        with (
            gzip.GzipFile(fileobj=target, mode="wb", filename="", mtime=0) as compressed,
            tarfile.open(fileobj=compressed, mode="w") as tar,
        ):
            for name in members:
                relative = name.removeprefix(prefix)
                if ".." in Path(relative).parts or Path(relative).is_absolute():
                    raise ValueError("unsafe skill resource path")
                content = archive.read(name)
                entry = tarfile.TarInfo("evidence-rag-agent/" + relative)
                entry.size = len(content)
                entry.mode = 0o644
                tar.addfile(entry, io.BytesIO(content))
    assets = [wheel, source, skill_path]
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in assets}
    manifest = dist / "release-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": version,
                "git_sha": git_sha,
                "workflow_run": workflow_run,
                "assets_sha256": hashes,
                "license": "AGPL-3.0-only",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    hashes[manifest.name] = hashlib.sha256(manifest.read_bytes()).hexdigest()
    (dist / "SHA256SUMS").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in sorted(hashes.items())),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--git-sha", required=True)
    parser.add_argument("--workflow-run", default="local-verification")
    args = parser.parse_args()
    package(args.dist, args.git_sha, args.workflow_run)
    print("Release assets and SHA256SUMS prepared")


if __name__ == "__main__":
    main()
