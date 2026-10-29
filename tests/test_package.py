"""Tests for the public package boundary."""

import subprocess
import sys
from importlib.metadata import version

import evidence_rag


def test_package_exposes_installed_version() -> None:
    """The importable version stays aligned with installed package metadata."""
    assert evidence_rag.__version__ == version("evidence-rag")
    assert evidence_rag.__version__ == "0.1.0"


def test_import_does_not_load_deferred_heavy_dependencies() -> None:
    """The top-level import must remain free of deferred runtime integrations."""
    deferred_modules = ("docling", "fastapi", "qdrant_client", "torch", "transformers")
    probe = (
        "import sys; import evidence_rag; "
        f"assert not set({deferred_modules!r}).intersection(sys.modules)"
    )

    completed = subprocess.run(
        [sys.executable, "-c", probe],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
