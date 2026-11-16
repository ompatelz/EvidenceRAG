"""Deterministic checks for explicit numeric claims over cited table cells."""

import re
from collections.abc import Sequence
from fractions import Fraction
from typing import Literal

from evidence_rag.evidence import TableStructure

RuleSupport = Literal["rule_supported", "contradicted", "insufficient", "not_assessed"]

_NUMBER = r"[+-]?[0-9]{1,18}(?:\.[0-9]{1,18})?"
_CELL = r'table_value\("([^"\r\n]+)", "([^"\r\n]+)"\)'
_EXPRESSION = re.compile(rf"{_CELL}(?: ([+-]) {_CELL})? = ({_NUMBER})")


def _label(value: str | None) -> str:
    return " ".join((value or "").split()).casefold()


def _cell_values(tables: Sequence[TableStructure], row: str, column: str) -> set[Fraction]:
    values: set[Fraction] = set()
    for table in tables:
        headers, rows = table.headers, table.rows
        if not table.header_external:
            headers, rows = rows[0], rows[1:]
        columns = [
            index for index, header in enumerate(headers) if index > 0 and _label(header) == column
        ]
        matching_rows = [cells for cells in rows if _label(cells[0]) == row]
        if not columns or not matching_rows:
            continue
        if len(columns) != 1 or len(matching_rows) != 1:
            return set()
        value = (matching_rows[0][columns[0]] or "").strip()
        if not re.fullmatch(_NUMBER, value):
            return set()
        values.add(Fraction(value))
    return values


def assess_table_claim(
    claim: str, tables: Sequence[TableStructure], *, truncated_table: bool
) -> RuleSupport:
    """Check exactly a cell lookup, or addition or subtraction of two cells."""
    match = _EXPRESSION.fullmatch(claim)
    if not match:
        return "insufficient" if claim.startswith("table_value(") else "not_assessed"
    if truncated_table:
        return "insufficient"
    row, column, operation, other_row, other_column, expected = match.groups()
    left = _cell_values(tables, _label(row), _label(column))
    right = (
        _cell_values(tables, _label(other_row), _label(other_column))
        if operation
        else {Fraction(0)}
    )
    if len(left) > 1 or len(right) > 1:
        return "contradicted"
    if not left or not right:
        return "insufficient"
    first, second = next(iter(left)), next(iter(right))
    actual = first - second if operation == "-" else first + second
    return "rule_supported" if actual == Fraction(expected) else "contradicted"
