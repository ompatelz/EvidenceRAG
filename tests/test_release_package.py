"""Release checksums and standalone skill must describe the actual built wheel."""

import hashlib
import importlib.util
import json
import tarfile
import zipfile
from pathlib import Path
from typing import Any

import pytest


def packaging_module() -> Any:
    spec = importlib.util.spec_from_file_location("package_release", "scripts/package_release.py")
    assert spec is not None and spec.loader is not None
    from importlib.util import module_from_spec

    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_assets_are_deterministic_and_hashed(tmp_path: Path) -> None:
    from evidence_rag import __version__

    wheel = tmp_path / f"evidence_rag-{__version__}-py3-none-any.whl"
    (tmp_path / f"evidence_rag-{__version__}.tar.gz").write_bytes(b"source-distribution")
    resources = {
        "SKILL.md": b"skill",
        "agents/openai.yaml": b"metadata",
        "references/tools.md": b"tools",
    }
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, content in resources.items():
            archive.writestr("evidence_rag/evidence-rag-agent/" + name, content)
    package = packaging_module().package
    package(tmp_path, "a" * 40, "test-run")
    skill = tmp_path / f"evidence-rag-agent-{__version__}.tar.gz"
    original = skill.read_bytes()
    with tarfile.open(skill) as archive:
        assert set(archive.getnames()) == {"evidence-rag-agent/" + n for n in resources}
        member = archive.extractfile("evidence-rag-agent/SKILL.md")
        assert member is not None and member.read() == b"skill"
    manifest = json.loads((tmp_path / "release-manifest.json").read_text())
    assert manifest["assets_sha256"][wheel.name] == hashlib.sha256(wheel.read_bytes()).hexdigest()
    package(tmp_path, "a" * 40, "test-run")
    assert skill.read_bytes() == original
    for line in (tmp_path / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ")
        assert hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == digest
    with pytest.raises(ValueError, match="full Git"):
        package(tmp_path, "not-a-sha", "test-run")
