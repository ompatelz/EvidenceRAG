"""Reproduce source-backed arithmetic on an existing development PDF, without inference."""

import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from evidence_rag.calculations import CalculationRequest
from evidence_rag.sdk import DocumentRef, EvidenceRAG, SearchRequest

FIXTURE = Path("datasets/fixtures/library-loans.pdf")


def collect() -> dict[str, Any]:
    manifest = json.loads(
        Path("datasets/manifests/answer-benchmark.json").read_text(encoding="utf-8")
    )
    source = next(
        row
        for row in manifest["documents"]
        if row["local_fixture_path"] == str(FIXTURE).replace("\\", "/")
    )
    digest = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    if digest != source["sha256"]:
        raise ValueError("owned development fixture differs from its source manifest")
    with TemporaryDirectory(prefix="evidencerag-calculation-") as temporary:
        engine = EvidenceRAG(Path(temporary) / "artifacts")
        ingested = engine.ingest(FIXTURE)
        document = DocumentRef(
            document_id=ingested.document_id, document_sha256=ingested.document_sha256
        )
        search = engine.search(
            SearchRequest(**document.model_dump(), question="Resident renewal loan period")
        )
        table = next(item for item in search.pack.items if "| Resident |" in item.text)
        renewal = next(item for item in search.pack.items if item.text.startswith("A renewal adds"))
        payload = {
            "operation": "add",
            "expected_value": "35",
            "operands": [
                {
                    "kind": "table_cell",
                    "evidence_id": table.evidence_id,
                    "row": "Resident",
                    "column": "Loan period",
                },
                {"kind": "text", "evidence_id": renewal.evidence_id, "unit": "days"},
            ],
        }
        correct = engine.calculate(document, CalculationRequest.model_validate(payload))
        wrong = engine.calculate(
            document, CalculationRequest.model_validate({**payload, "expected_value": "34"})
        )
        if (
            correct.calculation.matches_expected is not True
            or wrong.calculation.matches_expected is not False
        ):
            raise ValueError("source calculation smoke did not reproduce expected controls")
        return {
            "scope": "source extraction and exact arithmetic, not answer-quality evaluation",
            "fixture": str(FIXTURE).replace("\\", "/"),
            "fixture_sha256": digest,
            "question": "Resident renewal loan period",
            "provider_calls": 0,
            "source_sha256": {
                str(path).replace("\\", "/"): hashlib.sha256(
                    path.read_bytes().replace(b"\r\n", b"\n")
                ).hexdigest()
                for path in [
                    Path("src/evidence_rag/calculations.py"),
                    Path("src/evidence_rag/sdk.py"),
                ]
            },
            "correct_expected_value": correct.model_dump(mode="json"),
            "incorrect_expected_value": wrong.model_dump(mode="json"),
            "narrative_claim_support": "not_assessed; grounding-v1 remains unchanged",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = json.dumps(collect(), indent=2) + "\n"
    if args.check:
        if args.output.read_text(encoding="utf-8") != output:
            raise SystemExit("source arithmetic record differs from the deterministic smoke")
    else:
        with args.output.open("x", encoding="utf-8") as target:
            target.write(output)
    print("Source calculation and incorrect-result control passed")


if __name__ == "__main__":
    main()
