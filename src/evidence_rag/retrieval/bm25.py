"""Small deterministic BM25 index over canonical persisted evidence units."""

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from time import perf_counter

from evidence_rag.documents.storage import LocalArtifactStore
from evidence_rag.evidence import EvidenceUnit

INDEX_VERSION = "bm25-evidence-v1"
TOKENIZER_VERSION = "nfkc-casefold-unicode-id-v1"
_TOKEN = re.compile(r"[^\W_]+(?:[._/-][^\W_]+)*", re.UNICODE)


def tokenize(text: str) -> tuple[str, ...]:
    """Retain Unicode words, decimal numbers, and compound identifiers."""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return tuple(match.group() for match in _TOKEN.finditer(normalized))


@dataclass(frozen=True)
class RankedEvidence:
    """A scored canonical evidence unit with traceable source provenance."""

    evidence_id: str
    document_id: str
    document_version: str
    page_index: int
    rank: int
    score: float
    anchor_precision: str
    bbox: dict[str, float] | None


@dataclass(frozen=True)
class SearchResult:
    """One scoped BM25 ranking and elapsed search time."""

    hits: tuple[RankedEvidence, ...]
    search_ms: float
    index_id: str


class BM25Index:
    """In-memory index rebuilt from versioned evidence artifacts."""

    def __init__(self, *, k1: float = 1.2, b: float = 0.75) -> None:
        if not math.isfinite(k1) or k1 <= 0:
            raise ValueError("k1 must be finite and positive")
        if not math.isfinite(b) or not 0 <= b <= 1:
            raise ValueError("b must be finite and between 0 and 1")
        self.k1 = k1
        self.b = b
        self._units: dict[str, EvidenceUnit] = {}
        self._terms: dict[str, Counter[str]] = {}
        self._lengths: dict[str, int] = {}
        self._index_id = self._compute_identity()

    @property
    def index_id(self) -> str:
        return self._index_id

    @property
    def size(self) -> int:
        return len(self._units)

    def rebuild(self, units: Iterable[EvidenceUnit]) -> None:
        """Replace the entire index, rejecting conflicting repeated IDs."""
        replacement: dict[str, EvidenceUnit] = {}
        for unit in units:
            existing = replacement.get(unit.evidence_id)
            if existing is not None and existing != unit:
                raise ValueError(f"conflicting evidence ID: {unit.evidence_id}")
            replacement[unit.evidence_id] = unit
        self._units = replacement
        self._retokenize()

    def upsert(self, units: Iterable[EvidenceUnit]) -> None:
        """Replace units by stable ID; repeated ingestion never appends a duplicate."""
        for unit in units:
            self._units[unit.evidence_id] = unit
        self._retokenize()

    def delete_version(self, document_id: str, document_version: str) -> None:
        """Remove every unit from one exact document version."""
        self._units = {
            key: unit
            for key, unit in self._units.items()
            if (unit.document_id, unit.document_version) != (document_id, document_version)
        }
        self._retokenize()

    def rebuild_from_store(
        self, store: LocalArtifactStore, versions: Sequence[tuple[str, str]]
    ) -> None:
        """Load only explicitly selected persisted evidence artifacts."""
        units: list[EvidenceUnit] = []
        for document_id, document_version in versions:
            if not document_version.startswith("sha256:"):
                raise ValueError("document version must be content-addressed")
            artifact = store.get_evidence(document_id, document_version[7:])
            if (artifact.document_id, artifact.document_version) != (document_id, document_version):
                raise ValueError("persisted evidence provenance mismatch")
            units.extend(artifact.units)
        self.rebuild(units)

    def search(
        self,
        query: str,
        *,
        k: int = 10,
        versions: Sequence[tuple[str, str]] | None = None,
    ) -> SearchResult:
        """Rank positive lexical matches within exact document/version scope."""
        if k < 0:
            raise ValueError("k must be non-negative")
        started = perf_counter()
        tokens = tokenize(query)
        scope = None if versions is None else set(versions)
        candidates = {
            key: unit
            for key, unit in self._units.items()
            if scope is None or (unit.document_id, unit.document_version) in scope
        }
        if not tokens or not candidates or k == 0:
            return SearchResult((), (perf_counter() - started) * 1000, self.index_id)

        count = len(candidates)
        average_length = sum(self._lengths[key] for key in candidates) / count
        query_terms = sorted(set(tokens))
        document_frequency = {
            term: sum(self._terms[key][term] > 0 for key in candidates) for term in query_terms
        }
        scored: list[tuple[float, EvidenceUnit]] = []
        for key, unit in candidates.items():
            frequency = self._terms[key]
            length = self._lengths[key]
            score = 0.0
            for term in query_terms:
                tf = frequency[term]
                if not tf:
                    continue
                df = document_frequency[term]
                idf = math.log1p((count - df + 0.5) / (df + 0.5))
                denominator = tf + self.k1 * (1 - self.b + self.b * length / average_length)
                score += idf * tf * (self.k1 + 1) / denominator
            if score > 0:
                scored.append((score, unit))
        scored.sort(key=lambda pair: (-pair[0], pair[1].evidence_id))
        hits = tuple(
            RankedEvidence(
                evidence_id=unit.evidence_id,
                document_id=unit.document_id,
                document_version=unit.document_version,
                page_index=unit.page_index,
                rank=rank,
                score=score,
                anchor_precision=unit.anchor_precision.value,
                bbox=unit.bbox.model_dump() if unit.bbox is not None else None,
            )
            for rank, (score, unit) in enumerate(scored[:k], start=1)
        )
        return SearchResult(hits, (perf_counter() - started) * 1000, self.index_id)

    def _retokenize(self) -> None:
        self._terms = {key: Counter(tokenize(unit.text)) for key, unit in self._units.items()}
        self._lengths = {key: sum(terms.values()) for key, terms in self._terms.items()}
        self._index_id = self._compute_identity()

    def _compute_identity(self) -> str:
        entries = [
            unit.model_dump(mode="json")
            for unit in sorted(self._units.values(), key=lambda value: value.evidence_id)
        ]
        payload = json.dumps(
            {
                "version": INDEX_VERSION,
                "tokenizer": TOKENIZER_VERSION,
                "k1": self.k1,
                "b": self.b,
                "units": entries,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(payload).hexdigest()
