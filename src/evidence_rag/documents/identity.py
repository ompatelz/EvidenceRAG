"""Deterministic, path-independent document identity helpers."""

import hashlib
import re
import unicodedata
from pathlib import PurePosixPath

_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._ -]+")
_REPEATED_SEPARATORS = re.compile(r"[ _.-]{2,}")
_WINDOWS_RESERVED = {
    "aux",
    "com1",
    "com2",
    "com3",
    "com4",
    "com5",
    "com6",
    "com7",
    "com8",
    "com9",
    "con",
    "lpt1",
    "lpt2",
    "lpt3",
    "lpt4",
    "lpt5",
    "lpt6",
    "lpt7",
    "lpt8",
    "lpt9",
    "nul",
    "prn",
}


def sanitize_filename(filename: str | None) -> str:
    """Return a bounded display name with no directory semantics."""
    supplied = filename or "document.pdf"
    normalized = unicodedata.normalize("NFKD", supplied).replace("\\", "/")
    basename = PurePosixPath(normalized).name
    ascii_name = basename.encode("ascii", "ignore").decode("ascii")
    cleaned = _UNSAFE_FILENAME.sub("_", ascii_name)
    cleaned = _REPEATED_SEPARATORS.sub("_", cleaned).strip(" ._-")
    if not cleaned:
        cleaned = "document"
    stem = cleaned.rsplit(".", maxsplit=1)[0].casefold()
    if stem in _WINDOWS_RESERVED:
        cleaned = f"document_{cleaned}"
    if not cleaned.casefold().endswith(".pdf"):
        cleaned = f"{cleaned}.pdf"
    if len(cleaned) > 128:
        cleaned = f"{cleaned[:124].rstrip(' ._-')}.pdf"
    return cleaned


def logical_document_id(sanitized_filename: str) -> str:
    """Derive the local logical-document identity from its canonical display name."""
    canonical = sanitized_filename.casefold().encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    return f"doc_{digest[:24]}"
