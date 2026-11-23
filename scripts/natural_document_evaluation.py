"""Opt-in natural-PDF retrieval evaluation; no answer-quality or agent-gain claim."""

import argparse
import hashlib
import json
import tempfile
import urllib.request
from pathlib import Path

from evidence_rag.sdk import CollectionSearchRequest, DocumentRef, EvidenceRAG

SOURCE = "https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf"
DOWNLOAD = "https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=936225"
# Zero-based relevant page alternatives, audited against the official PDF by an
# agent. Development probes only; these are not human-approved gold judgments.
PROBES = [
    ("versioning", "How are major and minor changes to the framework version numbered?", [2]),
    ("voluntary", "Is the framework voluntary and limited to a particular sector?", [6]),
    ("functions", "Which four functions organize the AI risk management core?", [7, 24]),
    ("security", "How do resilience and security differ for an AI system?", [19]),
    ("safety", "Which practices improve safe operation of AI systems?", [18]),
    ("validity", "How does validation relate to requirements for intended use?", [17]),
]


def run(pdf: Path) -> dict[str, object]:
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="evidencerag-natural-") as work:
        engine = EvidenceRAG(Path(work) / "artifacts")
        ingested = engine.ingest(pdf)
        if ingested.state != "ready":
            raise ValueError("natural PDF did not reach ready state")
        if ingested.page_count != 48:
            raise ValueError("expected the 48-page AI RMF 1.0 source; inspect source changes")
        document = DocumentRef(
            document_id=ingested.document_id, document_sha256=ingested.document_sha256
        )
        rows = []
        for identifier, question, relevant in PROBES:
            variants = {}
            for contextual in (False, True):
                result = engine.search_collection(
                    CollectionSearchRequest(
                        documents=(document,),
                        question=question,
                        contextual_indexing=contextual,
                    )
                )
                variants[str(contextual).lower()] = {
                    "pages": [i.page_index for i in result.pack.items],
                    "page_hit_at_5": any(i.page_index in relevant for i in result.pack.items),
                    "pack": result.pack.model_dump(mode="json"),
                    "search_ms": result.search_ms,
                }
            rows.append(
                {
                    "question_id": identifier,
                    "question": question,
                    "relevant_page_alternatives": relevant,
                    "variants": variants,
                }
            )
        return {
            "source_url": SOURCE,
            "source_sha256": digest,
            "page_count": ingested.page_count,
            "label_provenance": "agent source audit; human review pending",
            "scope": "development page-retrieval probes; no generated answers",
            "rows": rows,
            "provider_calls": 0,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--expected-sha256", help="Require a previously frozen source fingerprint")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if (args.pdf is None) == (not args.download):
        parser.error("select exactly one of --pdf and --download")
    with tempfile.TemporaryDirectory(prefix="evidencerag-source-") as work:
        pdf = args.pdf
        if args.download:
            pdf = Path(work) / "NIST.AI.100-1.pdf"
            request = urllib.request.Request(
                DOWNLOAD,
                headers={
                    "User-Agent": "EvidenceRAG/0.4.0 (+https://github.com/ompatelz/EvidenceRAG)",
                    "Accept": "application/pdf",
                },
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                content = response.read(10 * 1024 * 1024 + 1)
            if len(content) > 10 * 1024 * 1024 or not content.startswith(b"%PDF-"):
                raise ValueError("invalid or oversized official source PDF")
            pdf.write_bytes(content)
        assert pdf is not None
        if (
            args.expected_sha256
            and hashlib.sha256(pdf.read_bytes()).hexdigest() != args.expected_sha256
        ):
            raise ValueError("natural source fingerprint changed")
        record = run(pdf)
        record["download_url"] = DOWNLOAD if args.download else None
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as target:
            target.write(json.dumps(record, indent=2) + "\n")
    rows = record["rows"]
    assert isinstance(rows, list)
    summary = {
        "source_sha256": record["source_sha256"],
        "pages": record["page_count"],
        "queries": len(rows),
        "record": str(args.output),
    }
    print("::notice title=Natural PDF retrieval::" + json.dumps(summary))


if __name__ == "__main__":
    main()
