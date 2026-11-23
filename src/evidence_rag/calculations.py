"""Exact arithmetic over selected source values, separate from semantic support."""

import re
from collections.abc import Mapping
from fractions import Fraction
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from evidence_rag.evidence import EvidenceUnit

NUMBER = r"[+-]?[0-9]{1,18}(?:\.[0-9]{1,18})?"
UNIT = r"[A-Za-z%][A-Za-z0-9%/_-]{0,31}"
CELL_VALUE = re.compile(rf"({NUMBER})(?:\s+({UNIT}))?")


class CalculationError(ValueError):
    """A fixed, source-free error code safe to expose to local clients."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class TextOperand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: Literal["text"]
    evidence_id: str = Field(min_length=1, max_length=128)
    unit: str = Field(default="", pattern=rf"^(?:{UNIT})?$")


class TableOperand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: Literal["table_cell"]
    evidence_id: str = Field(min_length=1, max_length=128)
    row: str = Field(min_length=1, max_length=128)
    column: str = Field(min_length=1, max_length=128)


Operand = Annotated[TextOperand | TableOperand, Field(discriminator="kind")]


class CalculationRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    operation: Literal["add", "subtract", "multiply", "divide"]
    operands: tuple[Operand, Operand]
    expected_value: str | None = Field(default=None, pattern=rf"^{NUMBER}$")


class ResolvedOperand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    selector: TextOperand | TableOperand
    value: str
    unit: str
    document_id: str
    document_version: str
    page_index: int
    source_text: str


class CalculationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    status: Literal["arithmetic_verified"] = "arithmetic_verified"
    version: Literal["source-arithmetic-v1"] = "source-arithmetic-v1"
    operation: Literal["add", "subtract", "multiply", "divide"]
    operands: tuple[ResolvedOperand, ResolvedOperand]
    result: str
    unit: str
    expected_value: str | None
    matches_expected: bool | None
    claim_support: Literal["not_assessed"] = "not_assessed"
    notice: str = (
        "Only selected source values and arithmetic were checked. This does not establish "
        "that the operation answers the question or that a narrative claim is supported."
    )


def _label(value: str | None) -> str:
    return " ".join((value or "").split()).casefold()


def resolve_operand(selector: TextOperand | TableOperand, unit: EvidenceUnit) -> ResolvedOperand:
    """Reject ambiguous extraction; do not infer units or interpret source conditions."""
    if selector.kind == "table_cell":
        table = unit.table
        if table is None:
            raise CalculationError("calculation_table_missing")
        headers, rows = table.headers, table.rows
        if not table.header_external:
            headers, rows = rows[0], rows[1:]
        columns = [
            index
            for index, header in enumerate(headers)
            if index > 0 and _label(header) == _label(selector.column)
        ]
        matched = [row for row in rows if _label(row[0]) == _label(selector.row)]
        if len(columns) != 1 or len(matched) != 1:
            raise CalculationError("calculation_cell_ambiguous_or_missing")
        cell = (matched[0][columns[0]] or "").strip()
        match = CELL_VALUE.fullmatch(cell)
        if match is None:
            raise CalculationError("calculation_cell_not_a_quantity")
        number, source_unit = match.group(1), match.group(2) or ""
    else:
        source_unit = selector.unit
        if not source_unit:
            match = re.fullmatch(NUMBER, unit.text.strip())
            if match is None:
                raise CalculationError("calculation_dimensionless_text_ambiguous")
            number = match.group()
        else:
            suffix = rf"\s+{re.escape(source_unit)}(?=$|\s|[.,;:!?)\]]+(?=\s|$))"
            candidates = re.findall(
                rf"(?<!\w)[+\-\u2212]?[0-9][0-9.,'_eE/+\-\u2212]*{suffix}", unit.text
            )
            pattern = re.compile(rf"(?<![^\s(=:])({NUMBER}){suffix}")
            matches = list(pattern.finditer(unit.text))
            if len(matches) != 1 or len(candidates) != 1:
                raise CalculationError("calculation_text_quantity_ambiguous_or_missing")
            if re.search(r"[0-9][\s,.'_/:]*$", unit.text[: matches[0].start()]):
                raise CalculationError("calculation_text_quantity_ambiguous_or_missing")
            number = matches[0].group(1)
    return ResolvedOperand(
        selector=selector,
        value=str(Fraction(number)),
        unit=source_unit,
        document_id=unit.document_id,
        document_version=unit.document_version,
        page_index=unit.page_index,
        source_text=unit.text,
    )


def calculate(request: CalculationRequest, units: Mapping[str, EvidenceUnit]) -> CalculationResult:
    """Evaluate two cited quantities with rational arithmetic, never eval or an LLM."""
    resolved = []
    for selector in request.operands:
        if selector.evidence_id not in units:
            raise CalculationError("calculation_evidence_not_supplied")
        unit = units[selector.evidence_id]
        if unit.evidence_id != selector.evidence_id:
            raise CalculationError("calculation_evidence_not_supplied")
        if len(unit.text) > 1200:
            raise CalculationError("calculation_source_truncated")
        resolved.append(resolve_operand(selector, unit))
    left, right = resolved
    if (left.document_id, left.document_version) != (right.document_id, right.document_version):
        raise CalculationError("calculation_version_mismatch")
    first, second = Fraction(left.value), Fraction(right.value)
    if request.operation in ("add", "subtract"):
        if left.unit != right.unit:
            raise CalculationError("calculation_unit_mismatch")
        result = first + second if request.operation == "add" else first - second
        unit_name = left.unit
    elif request.operation == "multiply":
        result = first * second
        unit_name = (
            f"{left.unit}*{right.unit}" if left.unit and right.unit else left.unit or right.unit
        )
    else:
        if not second:
            raise CalculationError("calculation_division_by_zero")
        result = first / second
        if not right.unit:
            unit_name = left.unit
        elif left.unit == right.unit:
            unit_name = ""
        else:
            unit_name = f"({left.unit or '1'})/({right.unit})"
    return CalculationResult(
        operation=request.operation,
        operands=(left, right),
        result=str(result),
        unit=unit_name,
        expected_value=request.expected_value,
        matches_expected=(result == Fraction(request.expected_value))
        if request.expected_value is not None
        else None,
    )
