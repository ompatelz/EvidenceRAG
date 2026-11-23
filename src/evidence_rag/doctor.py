"""Offline installation checks with actionable repairs and no model downloads."""

import importlib.util
import tempfile
from contextlib import suppress
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from evidence_rag.config import AppSettings
from evidence_rag.semantic import MODEL_NAME, MODEL_REVISION


class HealthCheck(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    status: Literal["ok", "warning", "error"]
    detail: str
    repair: str | None = None


class DoctorReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    checks: tuple[HealthCheck, ...]
    ready: bool
    network_calls: int = 0


def diagnose(settings: AppSettings) -> DoctorReport:
    checks = []
    for name in ("pymupdf", "pydantic", "mcp", "fastembed", "onnxruntime"):
        present = importlib.util.find_spec(name) is not None
        detail = "available" if present else "not installed"
        if present:
            with suppress(PackageNotFoundError):
                detail = version(name)
        required = name in ("pymupdf", "pydantic")
        checks.append(
            HealthCheck(
                name=name,
                status="ok" if present else "error" if required else "warning",
                detail=detail,
                repair=None
                if present
                else (
                    "python -m pip install mcp==1.30.0"
                    if name == "mcp"
                    else "Install the release wheel with [dense] for optional inference."
                ),
            )
        )
    try:
        settings.artifact_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=settings.artifact_root) as stream:
            stream.write(b"probe")
        storage_ok = True
    except OSError:
        storage_ok = False
    checks.append(
        HealthCheck(
            name="artifact_storage",
            status="ok" if storage_ok else "error",
            detail="writable" if storage_ok else "unavailable",
            repair=None if storage_ok else "Set EVIDENCERAG_ARTIFACT_ROOT to a writable directory.",
        )
    )
    snapshot = settings.model_cache_dir / ("models--" + MODEL_NAME.replace("/", "--"))
    snapshot = snapshot / "snapshots" / MODEL_REVISION
    cached = all((snapshot / p).is_file() for p in ("tokenizer.json", "onnx/model.onnx"))
    checks.append(
        HealthCheck(
            name="semantic_verifier",
            status="ok" if settings.semantic_verifier and cached else "warning",
            detail=(
                "configured with cached files; inference not exercised"
                if settings.semantic_verifier and cached
                else "cached files present; verifier disabled"
                if cached
                else "pinned files missing; natural-language support may be withheld"
            ),
            repair=None
            if settings.semantic_verifier and cached
            else "Follow docs/semantic_support.md and set EVIDENCERAG_SEMANTIC_VERIFIER=true.",
        )
    )
    data = Path(settings.ocr_tessdata) if settings.ocr_tessdata else None
    ocr_ok = data is not None and (data / (settings.ocr_language + ".traineddata")).is_file()
    checks.append(
        HealthCheck(
            name="ocr",
            status="ok" if ocr_ok else "warning",
            detail="local language data present" if ocr_ok else "optional OCR language data absent",
            repair=None
            if ocr_ok
            else "Install Tesseract language data; set EVIDENCERAG_OCR_TESSDATA.",
        )
    )
    return DoctorReport(checks=tuple(checks), ready=not any(c.status == "error" for c in checks))
