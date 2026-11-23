# Source-backed calculations

`calculate_evidence` is a local MCP tool, `EvidenceRAG.calculate` is its Python
equivalent, and `evidence-rag calculate` is the CLI. They extract two quantities
from canonical evidence in one exact document version and evaluate one operation
with rational arithmetic. No generator, `eval`, model weights or network request
is involved.

## What is checked

- Each evidence ID belongs to the selected ready document version.
- A table selector resolves exactly one row and one non-label column, whose cell
  is a decimal quantity with an optional explicit unit.
- A text selector finds exactly one quantity in its specified case-sensitive unit.
  Dimensionless text must consist entirely of one decimal number.
- Both source units fit the complete 1200-character evidence-item budget.
- Source page/region anchors and preview assets resolve.
- Addition/subtraction use identical units. Multiplication/division keep formal
  unit expressions; matching units cancel in division. No implicit conversion occurs.
- Arithmetic uses exact fractions. `0.1 + 0.2` returns `3/10`; no float rounding
  or invented decimal precision is hidden.

Use `add`, `subtract`, `multiply` or `divide`. Zero division, unknown/ambiguous
cells, multiple text quantities, missing source evidence and truncated sources
return explicit errors. Values may have an ASCII sign and up to 18 integer and
18 fractional digits. Grouped thousands, exponents, unicode minus signs, currency
prefixes, input fractions and unit conversion are unsupported. Units are literal
ASCII tokens, such as `days`, `ms`, `mW` or `%`; textual units require separating
whitespace. `mW` and `MW` are distinct. The tool does not infer units from headers.

## Python example

Search the document first and take evidence IDs from actual results:

```python
from evidence_rag.calculations import CalculationRequest

request = CalculationRequest.model_validate({
    "operation": "add",
    "expected_value": "35",
    "operands": [
        {"kind": "table_cell", "evidence_id": table_id,
         "row": "Resident", "column": "Loan period"},
        {"kind": "text", "evidence_id": renewal_id, "unit": "days"},
    ],
})
receipt = rag.calculate(document, request)
print(receipt.calculation.result, receipt.calculation.unit)
print(receipt.calculation.matches_expected)
```

On the owned library-loans development fixture this extracts `21 days` from the
Resident table row and `14 days` from the renewal passage. It returns `35`, `days`
and `matches_expected=true`, with both source contexts and their anchors.
Changing the expected value to `34` returns the actual `35` and false. It does
not approve the incorrect candidate. The optional expected value is a decimal
string and is not an operand.

For MCP, pass `document_id`, `document_sha256` and the same structured request
as `calculation`. For the CLI, save the request as UTF-8 JSON and run:

```sh
evidence-rag --artifact-root artifacts calculate --document-id ID --sha256 SHA --calculation calculation.json
```

Request files are bounded to 8 KiB. No free numeric literal operands are accepted.
Operational failure is an error; `matches_expected=false` is a successful
calculation exposing an incorrect candidate, not a verified expected answer.

## What arithmetic does not prove

Every receipt has `claim_support="not_assessed"`. A negated or conditional source
can contain a real number: the tool retains that full context, but cannot decide
that using the number is appropriate. A correct sum can still answer the wrong
question or ignore eligibility, exceptions, time periods or a contradictory source.

The agent must inspect source qualifiers and distinguish calculation from
interpretation. Existing narrative claims still go through `check_draft` and
grounding-v1. Calculator receipts do not create `rule_supported` claims, change
the verifier margin or allow bypassing an abstention. A missing semantic verifier
still withholds natural-language drafts. This feature therefore does not, by
itself, fix the previously observed semantic false abstention or establish an
answer-accuracy gain.

The [deterministic smoke](../reports/runs/source-calculation-v1.json) records a
correct calculation and incorrect-result control from an existing development
PDF. Reproduce it with:

```sh
python scripts/source_calculation_smoke.py --output reports/runs/source-calculation-v1.json --check
```

Regression tests include ambiguity, table conflicts, unit mismatch, formatted
numbers, zero division, foreign versions, malformed payloads, negated context,
exact decimals, CLI JSON and actual cross-page source anchors. No frozen-test
questions were selected or rerun.
